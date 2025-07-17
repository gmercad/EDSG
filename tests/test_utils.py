"""
Unit tests for utility functions
"""

from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

from app.utils import (call_llm, create_snapshot_prompt,
                       process_world_bank_data, validate_country_code,
                       validate_indicator_code)


class TestValidationFunctions:
    """Test validation functions"""

    def test_validate_country_code_valid(self):
        """Test valid country codes"""
        valid_codes = ["USA", "CHN", "DEU", "JPN", "GBR"]
        for code in valid_codes:
            assert validate_country_code(code)

    def test_validate_country_code_invalid(self):
        """Test invalid country codes"""
        invalid_codes = ["", "US", "us", "USA1", "123", None]
        for code in invalid_codes:
            assert not validate_country_code(code)

    def test_validate_indicator_code_valid(self):
        """Test valid indicator codes"""
        valid_codes = [
            "NY.GDP.MKTP.CD",
            "NY.GDP.MKTP.KD.ZG",
            "FP.CPI.TOTL.ZG",
            "SL.UEM.TOTL.ZS",
        ]
        for code in valid_codes:
            assert validate_indicator_code(code)

    def test_validate_indicator_code_invalid(self):
        """Test invalid indicator codes"""
        invalid_codes = ["", "GDP", "NY-GDP-MKTP-CD", "NY.GDP.MKTP.CD!", None]
        for code in invalid_codes:
            assert not validate_indicator_code(code)


class TestDataProcessing:
    """Test data processing functions"""

    def test_process_world_bank_data_valid(self):
        """Test processing valid World Bank data"""
        raw_data = [
            {"country": [{"value": "United States"}], "total": 1},
            [
                {
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                    "country": {"id": "USA", "value": "United States"},
                    "countryiso3code": "USA",
                    "date": "2022",
                    "value": 25462700000000,
                    "unit": "",
                    "obs_status": "",
                    "decimal": 0,
                }
            ],
        ]

        result = process_world_bank_data(raw_data, "USA", ["NY.GDP.MKTP.CD"])

        assert result is not None
        assert result["country_code"] == "USA"
        assert result["country_name"] == "United States"
        assert len(result["indicators"]) == 1
        assert result["indicators"][0]["code"] == "NY.GDP.MKTP.CD"
        assert result["indicators"][0]["name"] == "GDP (current US$)"
        assert len(result["indicators"][0]["values"]) == 1
        assert result["indicators"][0]["values"][0]["year"] == "2022"
        assert result["indicators"][0]["values"][0]["value"] == 25462700000000

    def test_process_world_bank_data_empty(self):
        """Test processing empty World Bank data"""
        raw_data = []
        result = process_world_bank_data(raw_data, "USA", ["NY.GDP.MKTP.CD"])
        assert result is None

    def test_process_world_bank_data_invalid_structure(self):
        """Test processing invalid World Bank data structure"""
        raw_data = [{"invalid": "structure"}]
        result = process_world_bank_data(raw_data, "USA", ["NY.GDP.MKTP.CD"])
        assert result is None


class TestPromptGeneration:
    """Test prompt generation functions"""

    def test_create_snapshot_prompt(self):
        """Test creating snapshot prompt"""
        country_name = "United States"
        indicators = [
            {
                "name": "GDP (current US$)",
                "code": "NY.GDP.MKTP.CD",
                "values": [
                    {"year": "2022", "value": 25462700000000, "unit": ""},
                    {"year": "2021", "value": 23315080556000, "unit": ""},
                ],
            }
        ]

        prompt = create_snapshot_prompt(country_name, indicators)

        assert "United States" in prompt
        assert "GDP (current US$)" in prompt
        assert "NY.GDP.MKTP.CD" in prompt
        assert "2022" in prompt
        assert "2021" in prompt
        assert "economic analyst" in prompt.lower()
        assert "economic development" in prompt.lower()


@pytest.mark.asyncio
class TestAsyncFunctions:
    """Test async functions"""

    async def test_fetch_world_bank_data_mock(self):
        """Test fetching World Bank data (mock test)"""
        # This would require mocking the HTTP request
        # For now, just test that the function exists and is callable
        from app.utils import fetch_world_bank_data

        assert callable(fetch_world_bank_data)

    async def test_generate_snapshot_with_llm_mock(self):
        """Test generating snapshot with LLM (mock test)"""
        # This would require mocking the LLM calls
        # For now, just test that the function exists and is callable
        from app.utils import generate_snapshot_with_llm

        assert callable(generate_snapshot_with_llm)


def test_resolve_env_vars_replaces_placeholders(monkeypatch):
    from app.utils import resolve_env_vars

    # Set environment variables for test
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "test_token")
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "test_project")

    config = {
        "mcpServers": {
            "supabase": {
                "args": [
                    "--access-token",
                    "${SUPABASE_ACCESS_TOKEN}",
                    "--project-ref",
                    "${SUPABASE_PROJECT_REF}",
                ],
                "env": {"SUPABASE_ACCESS_TOKEN": "${SUPABASE_ACCESS_TOKEN}"},
            }
        }
    }

    resolved = resolve_env_vars(config)
    assert resolved["mcpServers"]["supabase"]["args"][1] == "test_token"
    assert resolved["mcpServers"]["supabase"]["args"][3] == "test_project"
    assert (
        resolved["mcpServers"]["supabase"]["env"]["SUPABASE_ACCESS_TOKEN"]
        == "test_token"
    )


@pytest.mark.asyncio
async def test_call_llm_success():
    mock_response = {"choices": [{"message": {"content": "This is a test answer."}}]}

    class MockResp:
        status_code = 200

        def json(self):
            return mock_response

        def raise_for_status(self):
            pass

    async def mock_post(*args, **kwargs):
        return MockResp()

    with patch("httpx.AsyncClient.post", new=mock_post):
        answer = await call_llm("prompt", "question")
        assert answer == "This is a test answer."


@pytest.mark.asyncio
async def test_call_llm_error():
    async def mock_post(*args, **kwargs):
        raise Exception("LLM error!")

    with patch("httpx.AsyncClient.post", new=mock_post):
        answer = await call_llm("prompt", "question")
        assert answer.startswith("Error communicating with LLM:")


def test_chat_followup_missing_snapshot_key():
    with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_redis_get:
        mock_redis_get.return_value = None
        response = client.post("/api/v1/chat-followup", json={"snapshot_key": "", "user_question": "What is the GDP?"})
        assert response.status_code == 400
        assert "error" in response.json()
        assert "snapshot_text" in response.json()["error"] or "Missing" in response.json()["error"]

def test_chat_followup_missing_user_question():
    from unittest.mock import patch, AsyncMock
    # Mock generate_snapshot_with_llm in app.routes to avoid real LLM call
    with patch("app.routes.generate_snapshot_with_llm", new_callable=AsyncMock) as mock_generate, \
         patch("app.routes.redis_client.set", new_callable=AsyncMock) as mock_redis_set:
        mock_generate.return_value = ("Snapshot text", {"llm_payload": {}})
        mock_redis_set.return_value = None  # Simulate successful set
        resp = client.post("/api/v1/generate-snapshot", json={"country_code": "USA", "indicator_codes": ["NY.GDP.MKTP.CD"]})
        assert resp.status_code == 200
        snapshot_key = resp.json()["metadata"]["snapshot_key"]
        # Now, call chat-followup with missing user_question
        with patch("app.routes.redis_client.get", new_callable=AsyncMock) as mock_redis_get:
            mock_redis_get.return_value = "Snapshot text"
            response = client.post("/api/v1/chat-followup", json={"snapshot_key": snapshot_key, "user_question": ""})
            assert response.status_code == 400
            assert "error" in response.json()
            assert "user_question" in response.json()["error"] or "Missing" in response.json()["error"]


if __name__ == "__main__":
    pytest.main([__file__])
