import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import api_router, page_router

app = FastAPI()
app.include_router(api_router, prefix="/api/v1")
app.include_router(page_router)

client = TestClient(app)


# Fix test_chat_followup_valid: provide both required fields and mock Redis
@pytest.mark.asyncio
def test_chat_followup_valid():
    with patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm, \
         patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_redis_get:
        mock_call_llm.return_value = "Test answer."
        mock_redis_get.return_value = "summary"
        resp = client.post(
            "/api/v1/chat-followup",
            json={"snapshot_key": "abc123", "user_question": "What is GDP?"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Test answer."

# Fix test_chat_followup_missing_fields: omit required fields to trigger 422
@pytest.mark.asyncio
def test_chat_followup_missing_fields():
    # Omit snapshot_key
    resp1 = client.post(
        "/api/v1/chat-followup", json={"user_question": "What is GDP?"}
    )
    assert resp1.status_code == 422
    # Omit user_question
    resp2 = client.post(
        "/api/v1/chat-followup", json={"snapshot_key": "abc123"}
    )
    assert resp2.status_code == 422
    # Omit both
    resp3 = client.post(
        "/api/v1/chat-followup", json={}
    )
    assert resp3.status_code == 422

# Fix test_chat_followup_llm_error: provide valid fields, mock Redis, mock LLM error
@pytest.mark.asyncio
def test_chat_followup_llm_error():
    with patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm, \
         patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_redis_get:
        mock_call_llm.return_value = "Error communicating with LLM: Something went wrong"
        mock_redis_get.return_value = "summary"
        resp = client.post(
            "/api/v1/chat-followup", json={"snapshot_key": "abc123", "user_question": "Q?"}
        )
        assert resp.status_code == 502
        assert "error" in resp.json()

# Fix test_chat_followup_valid_stateless: provide valid fields, mock Redis and LLM
@pytest.mark.asyncio
def test_chat_followup_valid_stateless():
    # Mock Redis get/set and call_llm
    with patch("app.routes.redis_client") as mock_redis, \
         patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_redis.get = AsyncMock(side_effect=["summary", None])
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.set = AsyncMock()
        mock_call_llm.return_value = "Test stateless answer."
        resp = client.post(
            "/api/v1/chat-followup",
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
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_redis_get:
        mock_redis_get.return_value = None
        resp = client.post(
            "/api/v1/chat-followup", json={"snapshot_key": "", "user_question": "What is GDP?"}
        )
        assert resp.status_code == 400
        assert "error" in resp.json()

@pytest.mark.asyncio
def test_chat_followup_missing_user_question():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = "snapshot text"
        resp = client.post(
            "/api/v1/chat-followup", json={"snapshot_key": "abc123", "user_question": ""}
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert "user_question" in resp.json()["error"] or "Missing" in resp.json()["error"]

@pytest.mark.asyncio
def test_chat_followup_redis_error():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Redis is down!")
        resp = client.post(
            "/api/v1/chat-followup", json={"snapshot_key": "abc123", "user_question": "GDP?"}
        )
        assert resp.status_code == 500
        assert "error" in resp.json()
        assert "Redis" in resp.json()["error"] or "Failed" in resp.json()["error"]

# Fix test_chat_followup_chat_history: provide valid fields, mock Redis and LLM
@pytest.mark.asyncio
def test_chat_followup_chat_history():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_get, \
         patch("app.routes.redis_client.exists", new_callable=AsyncMock) as mock_exists, \
         patch("app.routes.redis_client.set", new_callable=AsyncMock) as mock_set, \
         patch("app.routes.call_llm", new_callable=AsyncMock) as mock_call_llm:
        # First two calls to get() return previous chat turns, then None
        prev_turns = [json.dumps({"question": "Q1", "answer": "A1"}), json.dumps({"question": "Q2", "answer": "A2"}), "summary", None]
        def get_side_effect(key):
            if key.endswith(":0"):
                return prev_turns[0]
            if key.endswith(":1"):
                return prev_turns[1]
            if key.startswith("snapshot:"):
                return prev_turns[2]
            return prev_turns[3]
        mock_get.side_effect = get_side_effect
        mock_exists.side_effect = [True, True, False]
        mock_call_llm.return_value = "A3"
        resp = client.post(
            "/api/v1/chat-followup",
            json={"snapshot_key": "abc123", "user_question": "Q3", "prev_chat_key": "chat:abc123:1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "A3"
        assert data["turn_index"] == 2
        mock_set.assert_called()

# Mock admin credentials (should match a user in DashboardUsers for real test)
ADMIN_USER = "admin"
ADMIN_PASS = "adminpass"

# Test public endpoint: sensitive fields should be redacted
def test_public_transactions_redacted():
    resp = client.get("/api/v1/transactions/public")
    assert resp.status_code == 200
    data = resp.json()
    for customer in data["customers"]:
        assert "email" not in customer
        assert "phone" not in customer
        assert "address" not in customer
        assert "privileged_notes" not in customer
    for txn in data["transactions"]:
        assert "privileged_notes" not in txn

# Test admin endpoint: all fields present (mocking Supabase auth)
def test_admin_transactions_full(monkeypatch):
    # Patch supabase and dashboard user check to always succeed
    import hashlib
    admin_hash = hashlib.sha256(ADMIN_PASS.encode()).hexdigest()
    class DummyClient:
        def table(self, name, *args, **kwargs):
            class DummyTable:
                def select(self, *a, **k):
                    return self
                def eq(self, *a, **k):
                    return self
                def execute(self):
                    if name == "DashboardUsers":
                        return type("Resp", (), {"data": [{"username": ADMIN_USER, "password_hash": admin_hash}]})()
                    elif name == "Customers_test":
                        # Return customers with all sensitive fields
                        return type("Resp", (), {"data": [
                            {"customer_id": 1, "first_name": "John", "last_name": "Doe", "email": "john@example.com", "phone": "1234567890", "address": "123 Main St", "privileged_notes": "VIP"}
                        ]})()
                    elif name == "Transactions":
                        # Return transactions with privileged_notes
                        return type("Resp", (), {"data": [
                            {"transaction_id": 1, "customer_id": 1, "store_id": 1, "amount": 100, "timestamp": "2024-01-01T00:00:00Z", "privileged_notes": "Sensitive info"}
                        ]})()
                    else:
                        return type("Resp", (), {"data": []})()
            return DummyTable()
    monkeypatch.setattr("app.routes.create_client", lambda *a, **k: DummyClient())
    # Patch the password hash check to match using a proper mock object
    class DummyHash:
        def __init__(self, *args, **kwargs):
            pass
        def update(self, *args, **kwargs):
            pass
        def hexdigest(self):
            return admin_hash
    monkeypatch.setattr("app.routes.hashlib.sha256", lambda *a, **k: DummyHash())
    resp = client.get("/api/v1/transactions/admin", auth=(ADMIN_USER, ADMIN_PASS))
    assert resp.status_code == 200
    data = resp.json()
    found_sensitive = False
    for customer in data["customers"]:
        if all(k in customer for k in ("email", "phone", "address", "privileged_notes")):
            found_sensitive = True
    for txn in data["transactions"]:
        if "privileged_notes" in txn:
            found_sensitive = True
    assert found_sensitive, "Sensitive fields should be present for admin"
