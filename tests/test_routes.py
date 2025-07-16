from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import json

from app.routes import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)


@pytest.mark.asyncio
def test_chat_followup_valid():
    with patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_call_llm.return_value = "Test answer."
        resp = client.post(
            "/chat-followup",
            json={"snapshot_text": "summary", "user_question": "What is GDP?"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Test answer."


@pytest.mark.asyncio
def test_chat_followup_missing_fields():
    resp = client.post(
        "/chat-followup", json={"snapshot_text": "", "user_question": ""}
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.asyncio
def test_chat_followup_llm_error():
    with patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_call_llm.return_value = (
            "Error communicating with LLM: Something went wrong"
        )
        resp = client.post(
            "/chat-followup", json={"snapshot_text": "summary", "user_question": "Q?"}
        )
        assert resp.status_code == 502
        assert "error" in resp.json()


@pytest.mark.asyncio
def test_chat_followup_valid_stateless():
    # Mock Redis get/set and call_llm
    with patch("app.routes.redis_client") as mock_redis, \
         patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_redis.get = AsyncMock(side_effect=["snapshot text", None])
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.set = AsyncMock()
        mock_call_llm.return_value = "Test stateless answer."
        resp = client.post(
            "/chat-followup",
            json={"snapshot_key": "abc123", "user_question": "What is GDP?", "prev_chat_key": None},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Test stateless answer."
        assert "chat_key" in data
        assert data["turn_index"] == 0
        mock_redis.set.assert_called()

@pytest.mark.asyncio
def test_chat_followup_missing_snapshot_key():
    resp = client.post(
        "/chat-followup", json={"snapshot_key": "", "user_question": "What is GDP?"}
    )
    assert resp.status_code == 400
    assert "error" in resp.json()
    assert "snapshot_text" in resp.json()["error"] or "Missing" in resp.json()["error"]

@pytest.mark.asyncio
def test_chat_followup_missing_user_question():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = "snapshot text"
        resp = client.post(
            "/chat-followup", json={"snapshot_key": "abc123", "user_question": ""}
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert "user_question" in resp.json()["error"] or "Missing" in resp.json()["error"]

@pytest.mark.asyncio
def test_chat_followup_redis_error():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Redis is down!")
        resp = client.post(
            "/chat-followup", json={"snapshot_key": "abc123", "user_question": "GDP?"}
        )
        assert resp.status_code == 500
        assert "error" in resp.json()
        assert "Redis" in resp.json()["error"] or "Failed" in resp.json()["error"]

@pytest.mark.asyncio
def test_chat_followup_chat_history():
    # Simulate two previous chat turns in Redis
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get, \
         patch("app.routes.redis_client.exists", new_callable=AsyncMock) as mock_exists, \
         patch("app.routes.redis_client.set", new_callable=AsyncMock) as mock_set, \
         patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        # First two calls to get() return previous chat turns, then None
        prev_turns = [json.dumps({"question": "Q1", "answer": "A1"}), json.dumps({"question": "Q2", "answer": "A2"}), None]
        def get_side_effect(key):
            if key.endswith(":0"): return prev_turns[0]
            if key.endswith(":1"): return prev_turns[1]
            return None
        mock_get.side_effect = get_side_effect
        mock_exists.side_effect = [True, True, False]
        mock_call_llm.return_value = "A3"
        resp = client.post(
            "/chat-followup",
            json={"snapshot_key": "abc123", "user_question": "Q3", "prev_chat_key": "chat:abc123:1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "A3"
        assert data["turn_index"] == 2
        mock_set.assert_called()
