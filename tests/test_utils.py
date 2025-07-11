"""
Unit tests for utility functions
"""

import pytest
import asyncio
from app.utils import (
    validate_country_code,
    validate_indicator_code,
    process_world_bank_data,
    create_snapshot_prompt
)

class TestValidationFunctions:
    """Test validation functions"""
    
    def test_validate_country_code_valid(self):
        """Test valid country codes"""
        valid_codes = ["USA", "CHN", "DEU", "JPN", "GBR"]
        for code in valid_codes:
            assert validate_country_code(code) == True
    
    def test_validate_country_code_invalid(self):
        """Test invalid country codes"""
        invalid_codes = ["", "US", "us", "USA1", "123", None]
        for code in invalid_codes:
            assert validate_country_code(code) == False
    
    def test_validate_indicator_code_valid(self):
        """Test valid indicator codes"""
        valid_codes = [
            "NY.GDP.MKTP.CD",
            "NY.GDP.MKTP.KD.ZG",
            "FP.CPI.TOTL.ZG",
            "SL.UEM.TOTL.ZS"
        ]
        for code in valid_codes:
            assert validate_indicator_code(code) == True
    
    def test_validate_indicator_code_invalid(self):
        """Test invalid indicator codes"""
        invalid_codes = ["", "GDP", "NY-GDP-MKTP-CD", "NY.GDP.MKTP.CD!", None]
        for code in invalid_codes:
            assert validate_indicator_code(code) == False

class TestDataProcessing:
    """Test data processing functions"""
    
    def test_process_world_bank_data_valid(self):
        """Test processing valid World Bank data"""
        raw_data = [
            {
                "country": [{"value": "United States"}],
                "total": 1
            },
            [
                {
                    "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
                    "country": {"id": "USA", "value": "United States"},
                    "countryiso3code": "USA",
                    "date": "2022",
                    "value": 25462700000000,
                    "unit": "",
                    "obs_status": "",
                    "decimal": 0
                }
            ]
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
        assert result is not None
        assert result["country_name"] == "Unknown"

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
                    {"year": "2021", "value": 23315080556000, "unit": ""}
                ]
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

if __name__ == "__main__":
    pytest.main([__file__]) 