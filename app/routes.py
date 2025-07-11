"""
API routes for Economic Development Snapshot Generator
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app.utils import (
    fetch_world_bank_data,
    generate_snapshot_with_llm,
    validate_country_code,
    validate_indicator_code
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for request/response
class SnapshotRequest(BaseModel):
    country_code: str
    indicator_codes: List[str]
    year: Optional[int] = None
    llm_provider: Optional[str] = "openai"  # "openai" or "lm_studio"
    
class SnapshotResponse(BaseModel):
    country_code: str
    country_name: str
    indicators: List[Dict[str, Any]]
    snapshot_text: str
    generated_at: str
    metadata: Dict[str, Any]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

@router.get("/countries", response_model=List[Dict[str, str]])
async def get_available_countries():
    """
    Get list of available countries with their codes and names
    """
    try:
        # This would typically fetch from a cached list or database
        # For now, returning a sample list
        countries = [
            {"code": "USA", "name": "United States"},
            {"code": "CHN", "name": "China"},
            {"code": "DEU", "name": "Germany"},
            {"code": "JPN", "name": "Japan"},
            {"code": "GBR", "name": "United Kingdom"},
            {"code": "IND", "name": "India"},
            {"code": "BRA", "name": "Brazil"},
            {"code": "FRA", "name": "France"},
            {"code": "ITA", "name": "Italy"},
            {"code": "CAN", "name": "Canada"}
        ]
        return countries
    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch countries")

@router.get("/indicators", response_model=List[Dict[str, str]])
async def get_available_indicators():
    """
    Get list of available economic indicators
    """
    try:
        # Sample economic indicators from World Bank
        indicators = [
            {"code": "NY.GDP.MKTP.CD", "name": "GDP (current US$)"},
            {"code": "NY.GDP.MKTP.KD.ZG", "name": "GDP growth (annual %)"},
            {"code": "NY.GDP.PCAP.CD", "name": "GDP per capita (current US$)"},
            {"code": "FP.CPI.TOTL.ZG", "name": "Inflation, consumer prices (annual %)"},
            {"code": "SL.UEM.TOTL.ZS", "name": "Unemployment, total (% of total labor force)"},
            {"code": "NE.EXP.GNFS.ZS", "name": "Exports of goods and services (% of GDP)"},
            {"code": "NE.IMP.GNFS.ZS", "name": "Imports of goods and services (% of GDP)"},
            {"code": "GC.DOD.TOTL.GD.ZS", "name": "Central government debt, total (% of GDP)"},
            {"code": "SE.ADT.LITR.ZS", "name": "Literacy rate, adult total (% of people ages 15 and above)"},
            {"code": "SH.DYN.MORT", "name": "Under-5 mortality rate, per 1,000 live births"}
        ]
        return indicators
    except Exception as e:
        logger.error(f"Error fetching indicators: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch indicators")

@router.post("/generate-snapshot", response_model=SnapshotResponse)
async def generate_snapshot(request: SnapshotRequest):
    """
    Generate an economic development snapshot for a country
    """
    try:
        # Validate inputs
        if not validate_country_code(request.country_code):
            raise HTTPException(status_code=400, detail="Invalid country code")
        
        for indicator in request.indicator_codes:
            if not validate_indicator_code(indicator):
                raise HTTPException(status_code=400, detail=f"Invalid indicator code: {indicator}")
        
        # Fetch World Bank data
        logger.info(f"Fetching data for country: {request.country_code}")
        world_bank_data = await fetch_world_bank_data(
            country_code=request.country_code,
            indicator_codes=request.indicator_codes,
            year=request.year
        )
        
        if not world_bank_data:
            raise HTTPException(status_code=404, detail="No data found for the specified parameters")
        
        # Generate snapshot with LLM
        logger.info("Generating snapshot with LLM")
        snapshot_text = await generate_snapshot_with_llm(
            country_code=request.country_code,
            data=world_bank_data,
            llm_provider=request.llm_provider
        )
        
        # Prepare response
        response = SnapshotResponse(
            country_code=request.country_code,
            country_name=world_bank_data.get("country_name", "Unknown"),
            indicators=world_bank_data.get("indicators", []),
            snapshot_text=snapshot_text,
            generated_at=world_bank_data.get("generated_at", ""),
            metadata={
                "llm_provider": request.llm_provider,
                "year": request.year,
                "indicator_count": len(request.indicator_codes)
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating snapshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate snapshot")

@router.get("/data/{country_code}")
async def get_country_data(
    country_code: str,
    indicators: str = Query(..., description="Comma-separated list of indicator codes"),
    year: Optional[int] = Query(None, description="Specific year (optional)")
):
    """
    Get raw World Bank data for a country and indicators
    """
    try:
        if not validate_country_code(country_code):
            raise HTTPException(status_code=400, detail="Invalid country code")
        
        indicator_list = [ind.strip() for ind in indicators.split(",")]
        for indicator in indicator_list:
            if not validate_indicator_code(indicator):
                raise HTTPException(status_code=400, detail=f"Invalid indicator code: {indicator}")
        
        data = await fetch_world_bank_data(
            country_code=country_code,
            indicator_codes=indicator_list,
            year=year
        )
        
        if not data:
            raise HTTPException(status_code=404, detail="No data found")
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching country data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch country data")

@router.get("/health")
async def api_health_check():
    """
    Health check for the API
    """
    return {"status": "healthy", "api": "economic-development-snapshot-generator"} 