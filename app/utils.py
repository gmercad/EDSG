"""
Utility functions for Economic Development Snapshot Generator
"""

import asyncio
import aiohttp
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import re
import sys
print("Python executable:", sys.executable)

# LLM imports
from langchain_openai import OpenAI, ChatOpenAI
from app.config import settings

# Validate config at import time
try:
    settings.validate()
except Exception as e:
    import logging
    logging.error(f"LLM configuration error: {e}")
    raise

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# World Bank API configuration
WORLD_BANK_BASE_URL = "https://api.worldbank.org/v2"
WORLD_BANK_FORMAT = "json"

# LLM configuration
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")

async def fetch_world_bank_data(
    country_code: str,
    indicator_codes: List[str],
    year: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch economic data from World Bank API with a timeout
    """
    try:
        timeout = aiohttp.ClientTimeout(total=15)  # 15-second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Build the URL for the World Bank API
            indicators_str = ";".join(indicator_codes)
            url = f"{WORLD_BANK_BASE_URL}/country/{country_code}/indicator/{indicators_str}"
            params = {
                "format": WORLD_BANK_FORMAT,
                "per_page": 1000
            }
            if year:
                params["date"] = str(year)
            else:
                current_year = datetime.now().year
                params["date"] = f"{current_year-5}:{current_year}"
            logger.info(f"Fetching data from World Bank API: {url}")
            try:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"World Bank API error: {response.status}")
                        return None
                    data = await response.json()
                    if not data or len(data) < 2:
                        logger.warning("No data returned from World Bank API")
                        return None
                    processed_data = process_world_bank_data(data, country_code, indicator_codes)
                    return processed_data
            except asyncio.TimeoutError:
                logger.error("World Bank API request timed out")
                return None
    except Exception as e:
        logger.error(f"Error fetching World Bank data: {e}")
        return None

def process_world_bank_data(
    raw_data: List,
    country_code: str,
    indicator_codes: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Process raw World Bank API response into structured format
    """
    if not raw_data or len(raw_data) < 2:
        return None
    try:
        # Extract metadata and data
        metadata = raw_data[0] if raw_data else {}
        data_points = raw_data[1] if len(raw_data) > 1 else []
        
        # Get country name from metadata
        country_name = "Unknown"
        if metadata.get("country"):
            country_name = metadata["country"][0].get("value", "Unknown")
        
        # Process indicators
        indicators = {}
        for data_point in data_points:
            indicator_code = data_point.get("indicator", {}).get("id")
            if indicator_code in indicator_codes:
                if indicator_code not in indicators:
                    indicators[indicator_code] = {
                        "code": indicator_code,
                        "name": data_point.get("indicator", {}).get("value", ""),
                        "values": []
                    }
                
                indicators[indicator_code]["values"].append({
                    "year": data_point.get("date"),
                    "value": data_point.get("value"),
                    "unit": data_point.get("unit", ""),
                    "obs_status": data_point.get("obs_status", "")
                })
        
        # Convert to list format for response
        indicators_list = list(indicators.values())
        
        return {
            "country_code": country_code,
            "country_name": country_name,
            "indicators": indicators_list,
            "generated_at": datetime.now().isoformat(),
            "total_indicators": len(indicators_list),
            "data_points": len(data_points)
        }
        
    except Exception as e:
        logger.error(f"Error processing World Bank data: {e}")
        return None

async def generate_snapshot_with_llm(
    country_code: str,
    data: Dict[str, Any],
    llm_provider: str = "openai"
) -> str:
    """
    Generate economic development snapshot using LLM
    Returns (text, payload_dict)
    """
    try:
        # Prepare the data for LLM
        country_name = data.get("country_name", country_code)
        indicators = data.get("indicators", [])
        
        # Create a structured prompt
        prompt = create_snapshot_prompt(country_name, indicators)
        
        if llm_provider == "openai":
            return await generate_with_openai(prompt)
        elif llm_provider == "lm_studio":
            return await generate_with_lm_studio(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            
    except Exception as e:
        logger.error(f"Error generating snapshot with LLM: {e}")
        return f"Error generating snapshot: {str(e)}", None

def create_snapshot_prompt(country_name: str, indicators: List[Dict[str, Any]]) -> str:
    """
    Create a structured prompt for the LLM
    """
    prompt = f"""You are an economic analyst. Generate a comprehensive economic development snapshot for {country_name} based on the following data.

Please provide:
1. A brief overview of the country's economic situation
2. Analysis of key economic indicators
3. Trends and patterns in the data
4. Potential implications for economic development
5. A summary conclusion

Economic Data for {country_name}:
"""
    
    for indicator in indicators:
        prompt += f"\n{indicator['name']} ({indicator['code']}):\n"
        for value in indicator['values']:
            if value['value'] is not None:
                prompt += f"  {value['year']}: {value['value']} {value['unit']}\n"
    
    prompt += "\nPlease provide a professional, data-driven analysis in 3-4 paragraphs."
    
    return prompt

LLM_TIMEOUT = 300  # 5 minutes

async def generate_with_openai(prompt: str):
    """
    Generate text using OpenAI API via langchain_openai.OpenAI with a longer timeout.
    Returns (text, payload_dict)
    """
    try:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")
        llm = OpenAI(openai_api_key=settings.OPENAI_API_KEY, model="gpt-3.5-turbo", temperature=0.7, max_tokens=1000)
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            try:
                result = await asyncio.wait_for(loop.run_in_executor(pool, llm.invoke, prompt), timeout=LLM_TIMEOUT)
                # Try to get the raw payload if available
                payload = getattr(llm, 'last_response', None)
                if payload is None:
                    # Try to parse result as JSON if possible
                    try:
                        payload = json.loads(result)
                    except Exception:
                        payload = {"result": result}
                return result, payload
            except asyncio.TimeoutError:
                logger.error("OpenAI API call timed out")
                return "Error: LLM call timed out after 5 minutes.", None
    except Exception as e:
        logger.error(f"Error with OpenAI API: {e}")
        return f"Error generating snapshot: {str(e)}", None

async def generate_with_lm_studio(prompt: str):
    print("DEBUG: generate_with_lm_studio called")
    """
    Generate text using LM Studio (Mistral-7B-Instruct-v0.1) via langchain_openai.ChatOpenAI with a longer timeout.
    Returns (text, payload_dict)
    """
    try:
        logger.debug(f"LM Studio URL: {settings.LM_STUDIO_URL}")
        logger.debug(f"LM Studio model: {settings.LM_STUDIO_MODEL}")
        logger.debug(f"Prompt being sent to LM Studio: {prompt}")
        llm = ChatOpenAI(
            openai_api_key="not-needed",
            base_url=settings.LM_STUDIO_URL,  # Should be http://localhost:1234/v1
            model=settings.LM_STUDIO_MODEL,
            temperature=0.7,
            max_tokens=1000
        )
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            try:
                logger.debug("Invoking LM Studio LLM via ChatOpenAI...")
                result = await asyncio.wait_for(loop.run_in_executor(pool, llm.invoke, prompt), timeout=LLM_TIMEOUT)
                logger.debug(f"LM Studio LLM result: {result}")
                payload = getattr(llm, 'last_response', None)
                if payload is None:
                    try:
                        payload = json.loads(result)
                    except Exception:
                        payload = {"result": result}
                return result, payload
            except asyncio.TimeoutError as te:
                logger.error("LM Studio LLM call timed out")
                return f"Error: LLM call timed out after 5 minutes.", None
            except Exception as e:
                logger.error(f"LM Studio LLM call failed: {e}")
                return f"Error: LLM call failed: {str(e)}", None
    except Exception as e:
        logger.error(f"Error with LM Studio: {e}")
        return f"Error generating snapshot: {str(e)}", None

def validate_country_code(country_code: str) -> bool:
    """
    Validate country code format
    """
    if not country_code or not isinstance(country_code, str):
        return False
    
    # World Bank uses 3-letter ISO country codes
    if len(country_code) != 3:
        return False
    
    # Check if it's all uppercase letters
    if not country_code.isalpha() or not country_code.isupper():
        return False
    
    return True

def validate_indicator_code(indicator_code: str) -> bool:
    """
    Validate World Bank indicator code format
    """
    if not indicator_code or not isinstance(indicator_code, str):
        return False
    
    # World Bank indicator codes typically follow pattern like NY.GDP.MKTP.CD
    if "." not in indicator_code:
        return False
    
    # Check if it contains only letters, numbers, and dots
    if not all(c.isalnum() or c == "." for c in indicator_code):
        return False
    
    return True

async def test_world_bank_connection() -> bool:
    """
    Test connection to World Bank API
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{WORLD_BANK_BASE_URL}/country/USA/indicator/NY.GDP.MKTP.CD"
            params = {"format": WORLD_BANK_FORMAT, "per_page": 1}
            
            async with session.get(url, params=params) as response:
                return response.status == 200
                
    except Exception as e:
        logger.error(f"Error testing World Bank connection: {e}")
        return False

async def test_llm_connection(llm_provider: str = "openai") -> bool:
    """
    Test connection to LLM provider
    """
    try:
        test_prompt = "Generate a one-sentence economic analysis."
        
        if llm_provider == "openai":
            await generate_with_openai(test_prompt)
        elif llm_provider == "lm_studio":
            await generate_with_lm_studio(test_prompt)
        else:
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error testing LLM connection: {e}")
        return False 

def resolve_env_vars(value):
    if isinstance(value, str):
        # Replace ${VAR} with the value from the environment
        return re.sub(r"\$\{(\w+)\}", lambda m: os.getenv(m.group(1), ""), value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(v) for v in value]
    else:
        return value 

# Simple test for LLM config and runtime errors
def test_llm_config():
    try:
        settings.validate()
        print("LLM config validated successfully.")
    except Exception as e:
        print(f"LLM config error: {e}") 