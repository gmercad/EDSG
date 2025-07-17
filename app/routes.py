"""
API routes for Economic Development Snapshot Generator
"""

import datetime
import hashlib
import json
import logging
import os
import secrets
import uuid
from typing import Any, Dict, List, Optional

# Redis async client
import redis.asyncio as aioredis
from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import Client, create_client
import traceback
from app.utils import (call_llm, fetch_world_bank_data,
                      generate_snapshot_with_llm, validate_country_code,
                      validate_indicator_code)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_router = APIRouter()
page_router = APIRouter()

security = HTTPBasic()


# Pydantic models for request/response
class SnapshotRequest(BaseModel):
    """
    Request model for generating an economic development snapshot.

    Attributes:
        country_code (str): Country code (e.g., 'USA').
        indicator_codes (List[str]): List of World Bank indicator codes.
        year (Optional[int]): Year for the snapshot (optional).
        llm_provider (str): LLM provider to use (default: 'lm_studio').
    """
    country_code: str = "USA"  # United States is valid for NY.GDP.MKTP.CD
    indicator_codes: List[str] = ["NY.GDP.MKTP.CD"]
    year: Optional[int] = 2021
    llm_provider: str = "lm_studio"  # Default to LM Studio


class SnapshotResponse(BaseModel):
    country_code: str
    country_name: str
    indicators: List[Dict[str, Any]]
    snapshot_text: str
    generated_at: str
    metadata: Dict[str, Any]
    llm_payload: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(i) for i in obj]
    elif hasattr(obj, "content"):
        return obj.content
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


@api_router.get("/countries", response_model=List[Dict[str, str]])
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
            {"code": "CAN", "name": "Canada"},
        ]
        return countries
    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch countries")


@api_router.get("/indicators", response_model=List[Dict[str, str]])
async def get_available_indicators():
    """
    Get list of available economic indicators.

    Returns:
        List[Dict[str, str]]: List of indicator code/name pairs.
    """
    try:
        # Sample economic indicators from World Bank
        indicators = [
            {"code": "NY.GDP.MKTP.CD", "name": "GDP (current US$)"},
            {"code": "NY.GDP.MKTP.KD.ZG", "name": "GDP growth (annual %)"},
            {"code": "NY.GDP.PCAP.CD", "name": "GDP per capita (current US$)"},
            {"code": "FP.CPI.TOTL.ZG", "name": "Inflation, consumer prices (annual %)"},
            {
                "code": "SL.UEM.TOTL.ZS",
                "name": "Unemployment, total (% of total labor force)",
            },
            {
                "code": "NE.EXP.GNFS.ZS",
                "name": "Exports of goods and services (% of GDP)",
            },
            {
                "code": "NE.IMP.GNFS.ZS",
                "name": "Imports of goods and services (% of GDP)",
            },
            {
                "code": "GC.DOD.TOTL.GD.ZS",
                "name": "Central government debt, total (% of GDP)",
            },
            {
                "code": "SE.ADT.LITR.ZS",
                "name": "Literacy rate, adult total (% of people ages 15 and above)",
            },
            {
                "code": "SH.DYN.MORT",
                "name": "Under-5 mortality rate, per 1,000 live births",
            },
        ]
        return indicators
    except Exception as e:
        logger.error(f"Error fetching indicators: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch indicators")


@api_router.post("/generate-snapshot", response_model=SnapshotResponse)
async def generate_snapshot(request: SnapshotRequest):
    """
    Generate an economic development snapshot for a country using World Bank data and an LLM.

    Args:
        request (SnapshotRequest): Request body with country, indicators, year, and LLM provider.

    Returns:
        SnapshotResponse: Snapshot and metadata, or error JSONResponse.
    """
    try:
        # Validate inputs
        if not validate_country_code(request.country_code):
            raise HTTPException(status_code=400, detail="Invalid country code")
        for indicator in request.indicator_codes:
            if not validate_indicator_code(indicator):
                raise HTTPException(
                    status_code=400, detail=f"Invalid indicator code: {indicator}"
                )
        # Fetch World Bank data
        logger.info(f"Fetching data for country: {request.country_code}")
        world_bank_data = await fetch_world_bank_data(
            country_code=request.country_code,
            indicator_codes=request.indicator_codes,
            year=request.year,
        )
        if not world_bank_data:
            raise HTTPException(
                status_code=404, detail="No data found for the specified parameters"
            )
        # Generate snapshot with LLM
        logger.info("Generating snapshot with LLM")
        snapshot_text, llm_payload = await generate_snapshot_with_llm(
            country_code=request.country_code,
            data=world_bank_data,
            llm_provider=request.llm_provider,
        )
        # Ensure snapshot_text is a string (extract 'content' if needed)
        if not isinstance(snapshot_text, str):
            if hasattr(snapshot_text, "content"):
                snapshot_text = snapshot_text.content
            elif isinstance(snapshot_text, dict) and "content" in snapshot_text:
                snapshot_text = snapshot_text["content"]
        # If it's already a string, leave as is
        # Ensure llm_payload is JSON serializable (recursively)
        llm_payload = make_json_safe(llm_payload)
        # If the LLM returned an error string, return a 502 error
        if isinstance(snapshot_text, str) and snapshot_text.lower().startswith("error"):
            logger.error(f"LLM error: {snapshot_text}")
            return JSONResponse(
                status_code=502, content={"error": "LLM Error", "detail": snapshot_text}
            )
        # After generating snapshot_text and llm_payload:
        snapshot_key = str(uuid.uuid4())
        try:
            await redis_client.set(f"snapshot:{snapshot_key}", snapshot_text, ex=3600)  # 1 hour expiry
        except Exception as e:
            logger.error(f"Redis error: {e}")
            return JSONResponse(status_code=500, content={"error": "Failed to store snapshot in Redis", "detail": str(e)})
        # Add snapshot_key to response
        response = SnapshotResponse(
            country_code=request.country_code,
            country_name=world_bank_data.get("country_name", "Unknown"),
            indicators=world_bank_data.get("indicators", []),
            snapshot_text=snapshot_text,
            generated_at=world_bank_data.get("generated_at", ""),
            metadata={
                "llm_provider": request.llm_provider,
                "year": request.year,
                "indicator_count": len(request.indicator_codes),
                "snapshot_key": snapshot_key,
            },
            llm_payload=llm_payload,
        )
        return response
    except HTTPException as he:
        logger.error(f"HTTPException: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Error generating snapshot: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "detail": str(e)},
        )


@api_router.get("/data/{country_code}")
async def get_country_data(
    country_code: str = Request,
    indicators: str = Request,
    year: Optional[int] = Request,
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
                raise HTTPException(
                    status_code=400, detail=f"Invalid indicator code: {indicator}"
                )

        # Fetch each indicator separately and merge results
        merged_data = []
        for indicator in indicator_list:
            data = await fetch_world_bank_data(
                country_code=country_code, indicator_codes=[indicator], year=year
            )
            if data and data.get("indicators"):
                merged_data.extend(data["indicators"])

        if not merged_data:
            raise HTTPException(status_code=404, detail="No data found")

        return {"country_code": country_code, "indicators": merged_data, "year": year}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching country data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch country data")


@api_router.get("/health")
async def api_health_check():
    """
    Health check for the API
    """
    return {"status": "healthy", "api": "economic-development-snapshot-generator"}


# --- Data Quality Agent Endpoint ---
@api_router.post("/data-quality/scan")
async def data_quality_scan(request: Request, action: str = Body("report_only")):
    """
    Data Quality Agent for Supabase Tables.

    Args:
        request (Request): FastAPI request object.
        action (str): 'report_only' or 'report_and_fix'.

    Returns:
        JSONResponse: Data quality findings, anomalies, and fix actions.
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(
            {
                "status": "error",
                "message": "Supabase URL or service_role key not set in environment variables.",
            },
            status_code=500,
        )
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    findings = []
    anomalies = []
    fix_actions = []

    # Step 2: Fetch schemas and data for Customers_test, Stores, Transactions
    table_names = ["Customers_test", "Stores", "Transactions"]
    table_data = {}
    for table in table_names:
        try:
            resp = supabase.table(table).select("*").execute()
            table_data[table] = resp.data if hasattr(resp, "data") else resp
        except Exception as e:
            anomalies.append({"table": table, "error": str(e)})
            table_data[table] = []

    customers = table_data.get("Customers_test", [])
    stores = table_data.get("Stores", [])
    transactions = table_data.get("Transactions", [])

    # Step 4: Core Checks
    # --- Customers_test ---
    if customers:
        # Null checks
        null_name = [c["id"] for c in customers if not c.get("name")]
        null_email = [c["id"] for c in customers if not c.get("email")]
        null_store = [c["id"] for c in customers if not c.get("store_id")]
        if null_name:
            anomalies.append(
                {"table": "Customers_test", "column": "name", "null_ids": null_name}
            )
        if null_email:
            anomalies.append(
                {"table": "Customers_test", "column": "email", "null_ids": null_email}
            )
        if null_store:
            anomalies.append(
                {
                    "table": "Customers_test",
                    "column": "store_id",
                    "null_ids": null_store,
                }
            )
        # Duplicate email check
        emails = [c["email"] for c in customers if c.get("email")]
        duplicate_emails = set([e for e in emails if emails.count(e) > 1])
        if duplicate_emails:
            anomalies.append(
                {
                    "table": "Customers_test",
                    "column": "email",
                    "duplicates": list(duplicate_emails),
                }
            )
        findings.append({"table": "Customers_test", "count": len(customers)})
    else:
        findings.append(
            {"table": "Customers_test", "count": 0, "note": "No data found or error."}
        )

    # --- Stores ---
    if stores:
        null_name = [s["id"] for s in stores if not s.get("name")]
        null_location = [s["id"] for s in stores if not s.get("location")]
        if null_name:
            anomalies.append(
                {"table": "Stores", "column": "name", "null_ids": null_name}
            )
        if null_location:
            anomalies.append(
                {"table": "Stores", "column": "location", "null_ids": null_location}
            )
        findings.append({"table": "Stores", "count": len(stores)})
    else:
        findings.append(
            {"table": "Stores", "count": 0, "note": "No data found or error."}
        )

    # --- Transactions ---
    if transactions:
        null_customer = [t["id"] for t in transactions if not t.get("customer_id")]
        null_store = [t["id"] for t in transactions if not t.get("store_id")]
        null_amount = [t["id"] for t in transactions if t.get("amount") is None]
        null_timestamp = [t["id"] for t in transactions if not t.get("timestamp")]
        if null_customer:
            anomalies.append(
                {
                    "table": "Transactions",
                    "column": "customer_id",
                    "null_ids": null_customer,
                }
            )
        if null_store:
            anomalies.append(
                {"table": "Transactions", "column": "store_id", "null_ids": null_store}
            )
        if null_amount:
            anomalies.append(
                {"table": "Transactions", "column": "amount", "null_ids": null_amount}
            )
        if null_timestamp:
            anomalies.append(
                {
                    "table": "Transactions",
                    "column": "timestamp",
                    "null_ids": null_timestamp,
                }
            )
        # Value range check for amount
        invalid_amounts = [
            t["id"]
            for t in transactions
            if t.get("amount") is not None and t.get("amount") <= 0
        ]
        if invalid_amounts:
            anomalies.append(
                {
                    "table": "Transactions",
                    "column": "amount",
                    "invalid_ids": invalid_amounts,
                    "rule": "> $0.00 USD",
                }
            )
        findings.append({"table": "Transactions", "count": len(transactions)})
    else:
        findings.append(
            {"table": "Transactions", "count": 0, "note": "No data found or error."}
        )

    # Referential integrity checks
    # --- Customers_test.store_id should exist in Stores.id ---
    store_ids = set(s["id"] for s in stores if s.get("id"))
    invalid_customer_stores = [
        c["id"]
        for c in customers
        if c.get("store_id") and c["store_id"] not in store_ids
    ]
    if invalid_customer_stores:
        anomalies.append(
            {
                "table": "Customers_test",
                "column": "store_id",
                "invalid_store_ids": invalid_customer_stores,
                "rule": "store_id must exist in Stores.id",
            }
        )

    # --- Transactions.customer_id should exist in Customers_test.id ---
    customer_ids = set(c["id"] for c in customers if c.get("id"))
    invalid_transaction_customers = [
        t["id"]
        for t in transactions
        if t.get("customer_id") and t["customer_id"] not in customer_ids
    ]
    if invalid_transaction_customers:
        anomalies.append(
            {
                "table": "Transactions",
                "column": "customer_id",
                "invalid_customer_ids": invalid_transaction_customers,
                "rule": "customer_id must exist in Customers_test.id",
            }
        )

    # --- Transactions.store_id should exist in Stores.id ---
    invalid_transaction_stores = [
        t["id"]
        for t in transactions
        if t.get("store_id") and t["store_id"] not in store_ids
    ]
    if invalid_transaction_stores:
        anomalies.append(
            {
                "table": "Transactions",
                "column": "store_id",
                "invalid_store_ids": invalid_transaction_stores,
                "rule": "store_id must exist in Stores.id",
            }
        )

    # Min/max summaries for numeric/date columns
    def get_min_max(values):
        if not values:
            return None, None
        return min(values), max(values)

    # Transactions.amount min/max
    amounts = [t["amount"] for t in transactions if t.get("amount") is not None]
    min_amount, max_amount = get_min_max(amounts)
    findings.append(
        {"table": "Transactions", "amount_min": min_amount, "amount_max": max_amount}
    )

    # Transactions.timestamp min/max
    timestamps = []
    for t in transactions:
        ts = t.get("timestamp")
        if ts:
            try:
                # Try to parse as ISO format
                timestamps.append(datetime.datetime.fromisoformat(ts))
            except Exception:
                pass
    if timestamps:
        min_ts, max_ts = get_min_max(timestamps)
        findings.append(
            {
                "table": "Transactions",
                "timestamp_min": str(min_ts),
                "timestamp_max": str(max_ts),
            }
        )

    # --- Fix logic if requested ---
    if action == "report_and_fix":
        # 1. Remove duplicate emails in Customers_test (keep first occurrence)
        emails_seen = set()
        duplicate_customer_ids = []
        for c in customers:
            email = c.get("email")
            if email:
                if email in emails_seen:
                    duplicate_customer_ids.append(c["id"])
                else:
                    emails_seen.add(email)
        if duplicate_customer_ids:
            try:
                supabase.table("Customers_test").delete().in_(
                    "id", duplicate_customer_ids
                ).execute()
                fix_actions.append(
                    {
                        "action": "remove_duplicate_customers",
                        "ids": duplicate_customer_ids,
                    }
                )
            except Exception as e:
                anomalies.append(
                    {"fix_error": f"Failed to remove duplicate customers: {str(e)}"}
                )

        # 2. Remove transactions with invalid customer_id or store_id
        valid_customer_ids = set(
            c["id"]
            for c in customers
            if c.get("id") and c.get("email") not in duplicate_customer_ids
        )
        valid_store_ids = set(s["id"] for s in stores if s.get("id"))
        invalid_transaction_ids = [
            t["id"]
            for t in transactions
            if (
                t.get("customer_id") not in valid_customer_ids
                or t.get("store_id") not in valid_store_ids
            )
        ]
        if invalid_transaction_ids:
            try:
                supabase.table("Transactions").delete().in_(
                    "id", invalid_transaction_ids
                ).execute()
                fix_actions.append(
                    {
                        "action": "remove_invalid_transactions",
                        "ids": invalid_transaction_ids,
                    }
                )
            except Exception as e:
                anomalies.append(
                    {"fix_error": f"Failed to remove invalid transactions: {str(e)}"}
                )

        # 3. Remove transactions with amount <= 0
        invalid_amount_ids = [
            t["id"]
            for t in transactions
            if t.get("amount") is not None and t.get("amount") <= 0
        ]
        if invalid_amount_ids:
            try:
                supabase.table("Transactions").delete().in_(
                    "id", invalid_amount_ids
                ).execute()
                fix_actions.append(
                    {
                        "action": "remove_invalid_amount_transactions",
                        "ids": invalid_amount_ids,
                    }
                )
            except Exception as e:
                anomalies.append(
                    {
                        "fix_error": f"Failed to remove transactions with invalid amount: {str(e)}"
                    }
                )

    # After findings/anomalies/user_prompt are prepared:
    # Log findings/anomalies to DataQualityLogs table in Supabase
    try:
        supabase.table("DataQualityLogs").insert(
            {
                "findings": json.dumps(findings),
                "anomalies": json.dumps(anomalies),
                "user_prompt": json.dumps(
                    {
                        "prompt": "Data quality scan complete. Would you like to (1) report only, or (2) report & fix issues?",
                        "options": ["report_only", "report_and_fix"],
                        "last_action": action,
                        "fix_actions": fix_actions,
                    }
                ),
            }
        ).execute()
    except Exception as e:
        anomalies.append({"logging_error": str(e)})

    user_prompt = {
        "prompt": "Data quality scan complete. Would you like to (1) report only, or (2) report & fix issues?",
        "options": ["report_only", "report_and_fix"],
        "last_action": action,
        "fix_actions": fix_actions,
    }

    return JSONResponse(
        {
            "status": "success",
            "findings": findings,
            "anomalies": anomalies,
            "fix_actions": fix_actions,
            "note": "Data quality checks complete. Further dashboard integration and fixing logic to follow.",
            "user_prompt": user_prompt,
        }
    )


# --- Data Quality Dashboard Endpoint (service_role only) ---
@api_router.get("/data-quality/dashboard")
async def data_quality_dashboard(
    request: Request, credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Returns the latest data quality findings and anomalies.
    Only accessible by users with valid username/password (checked against Supabase DashboardUsers table).
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(
            {
                "status": "error",
                "message": "Supabase URL or service_role key not set in environment variables.",
            },
            status_code=500,
        )
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Check credentials against DashboardUsers table
    username = credentials.username
    password = credentials.password
    # Hash the password for comparison (SHA256)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        resp = (
            supabase.table("DashboardUsers")
            .select("username, password_hash")
            .eq("username", username)
            .execute()
        )
        users = resp.data if hasattr(resp, "data") else resp
        if not users or not secrets.compare_digest(
            users[0]["password_hash"], password_hash
        ):
            return JSONResponse(
                {"status": "error", "message": "Invalid username or password."},
                status_code=401,
            )
    except Exception as e:
        return JSONResponse(
            {
                "status": "error",
                "message": f"Auth error: {str(e)}. Please ensure the DashboardUsers table exists with columns: username (text, PK), password_hash (text).",
            },
            status_code=500,
        )

    # Fetch the latest data quality logs from the DataQualityLogs table
    try:
        resp = (
            supabase.table("DataQualityLogs")
            .select("*")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        logs = resp.data if hasattr(resp, "data") else resp
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Failed to fetch logs: {str(e)}"},
            status_code=500,
        )

    return JSONResponse({"status": "success", "logs": logs})


@api_router.post("/chat-followup")
async def chat_followup(snapshot_key: str = Body(...), user_question: str = Body(...), prev_chat_key: str = Body(None)):
    """
    Handle follow-up chat questions about a generated snapshot.

    Args:
        snapshot_key (str): Redis key for the snapshot.
        user_question (str): User's follow-up question.
        prev_chat_key (str, optional): Previous chat key for context.

    Returns:
        dict: Answer, chat_key, and turn_index, or error JSONResponse.
    """
    logger = logging.getLogger(__name__)
    try:
        snapshot_text = await redis_client.get(f"snapshot:{snapshot_key}")
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return JSONResponse({"error": "Failed to retrieve snapshot from Redis", "detail": str(e)}, status_code=500)
    snapshot_hash = (
        hashlib.sha256(snapshot_text.encode()).hexdigest() if snapshot_text else None
    )
    logger.info(
        f"/chat-followup request: question='{user_question}', snapshot_hash={snapshot_hash}"
    )
    if not snapshot_text or not user_question:
        logger.warning("Missing snapshot_text or user_question.")
        return JSONResponse(
            {"error": "Missing snapshot_text or user_question."}, status_code=400
        )
    # Compose context: if prev_chat_key is provided, fetch previous chat turns
    chat_context = []
    if prev_chat_key:
        # Fetch all previous chat turns for this snapshot
        idx = 0
        while True:
            chat_turn = await redis_client.get(f"chat:{snapshot_key}:{idx}")
            if not chat_turn:
                break
            chat_context.append(json.loads(chat_turn))
            idx += 1
    # Compose prompt with snapshot and chat history
    prompt = (
        "You are a data assistant. The user has just received the following economic development snapshot:\n\n"
        f"{snapshot_text}\n\n"
        "When the user asks a follow-up question, answer using the information in the snapshot above as your primary source. "
        "If the answer is not directly available, use your general knowledge, but always prioritize the snapshot data.\n\n"
    )
    if chat_context:
        for turn in chat_context:
            prompt += f"Previous Q: {turn['question']}\nA: {turn['answer']}\n"
    # Guardrails filter temporarily disabled for debugging
    # flagged, category = await filter_with_guardrails(prompt)
    # if flagged:
    #     logger.warning(
    #         f"Prompt flagged by guardrails: category={category}, question='{user_question}', snapshot_hash={snapshot_hash}"
    #     )
    #     return JSONResponse(
    #         {
    #             "error": f"Your request was flagged for {category} and cannot be processed."
    #         },
    #         status_code=400,
    #     )
    try:
        answer = await call_llm(prompt, user_question)
        # Guardrails filter on LLM response temporarily disabled
        # flagged_resp, category_resp = await filter_with_guardrails(answer)
        # if flagged_resp:
        #     logger.warning(
        #         f"LLM response flagged by guardrails: category={category_resp}, question='{user_question}', snapshot_hash={snapshot_hash}"
        #     )
        #     return JSONResponse(
        #         {
        #             "error": f"The response was flagged for {category_resp} and cannot be shown."
        #         },
        #         status_code=400,
        #     )
        if isinstance(answer, str) and answer.lower().startswith("error"):
            logger.error(f"LLM error: {answer}")
            return JSONResponse({"error": answer}, status_code=502)
        # Save this chat turn in Redis
        # Find the next available index
        idx = 0
        while True:
            exists = await redis_client.exists(f"chat:{snapshot_key}:{idx}")
            if not exists:
                break
            idx += 1
        chat_turn = {"question": user_question, "answer": answer}
        await redis_client.set(f"chat:{snapshot_key}:{idx}", json.dumps(chat_turn), ex=3600)
        chat_key = f"chat:{snapshot_key}:{idx}"
        return {"answer": answer, "chat_key": chat_key, "turn_index": idx}
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return JSONResponse(
            {"error": f"Internal server error: {str(e)}"}, status_code=500
        )


# --- PAGE ROUTES (HTML) ---
@page_router.get("/dashboard", response_class=HTMLResponse)
async def home(request: Request):
    return Jinja2Templates(directory="app/templates").TemplateResponse(
        "dashboard.html", {"request": request}
    )

@page_router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    error = request.query_params.get("error")
    next_url = request.query_params.get("next", "/transactions/entry")
    html = f"""
    <!DOCTYPE html>
    <html lang='en'>
    <head>
        <meta charset='UTF-8'>
        <title>Service Role Login</title>
        <link rel='stylesheet' href='/static/styles.css'>
        <style>.login-container{{max-width:400px;margin:4rem auto;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.06);padding:2rem;}}.login-container h2{{text-align:center;color:#1a73e8;}}</style>
    </head>
    <body>
        <div class='login-container'>
            <h2>Service Role Login</h2>
            {f"<div class='alert error'>{error}</div>" if error else ''}
            <form method='post' action='/login'>
                <input type='hidden' name='next' value='{next_url}'>
                <label for='username'>Username:</label>
                <input type='text' id='username' name='username' required autofocus>
                <label for='password'>Password:</label>
                <input type='password' id='password' name='password' required>
                <button type='submit'>Login</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@page_router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/transactions/entry"),
):
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return HTMLResponse(
            "<h2>Supabase URL or service_role key not set in environment variables.</h2>",
            status_code=500,
        )
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    import hashlib

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        resp = (
            supabase.table("DashboardUsers")
            .select("username, password_hash")
            .eq("username", username)
            .execute()
        )
        users = resp.data if hasattr(resp, "data") else resp
        if not users or users[0]["password_hash"] != password_hash:
            return RedirectResponse(
                f"/login?error=Invalid+username+or+password.&next={next}",
                status_code=303,
            )
    except Exception as e:
        return RedirectResponse(
            f"/login?error=Auth+error:+{str(e)}&next={next}", status_code=303
        )
    # Set session
    request.session["username"] = username
    return RedirectResponse(next, status_code=303)

@page_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@page_router.get("/transactions/entry", response_class=HTMLResponse)
async def transaction_entry_form(request: Request):
    username = request.session.get("username")
    if not username:
        return RedirectResponse("/login?next=/transactions/entry", status_code=303)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return HTMLResponse(
            "<h2>Supabase URL or service_role key not set in environment variables.</h2>",
            status_code=500,
        )
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    try:
        customers_resp = (
            supabase.table("Customers_test")
            .select("customer_id, first_name, last_name")
            .execute()
        )
        stores_resp = supabase.table("Stores").select("store_id, name").execute()
        customers = (
            customers_resp.data
            if hasattr(customers_resp, "data")
            else customers_resp
        )
        stores = stores_resp.data if hasattr(stores_resp, "data") else stores_resp
    except Exception as e:
        return HTMLResponse(
            f"<h2>Error fetching customers or stores: {str(e)}</h2>",
            status_code=500,
        )
    result = request.query_params.get("result")
    # Pre-fill fields if present
    customer_id = request.query_params.get("customer_id", "")
    store_id = request.query_params.get("store_id", "")
    amount = request.query_params.get("amount", "")
    timestamp = request.query_params.get("timestamp", "")
    show_duplicate_options = request.query_params.get("show_duplicate_options")
    context = {
        "request": request,
        "customers": customers,
        "stores": stores,
        "result": result,
        "customer_id": customer_id,
        "store_id": store_id,
        "amount": amount,
        "timestamp": timestamp,
        "show_duplicate_options": show_duplicate_options,
        "username": username,
    }
    return Jinja2Templates(directory="app/templates").TemplateResponse(
        "transaction_entry.html", context
    )

@page_router.post("/transactions/new")
async def add_transaction(request: Request):
    """
    Allows a user to add a new transaction to the Transactions table.
    Accepts both JSON and form submissions.
    Deduplicates on customer_id, store_id, amount, timestamp before insert.
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return JSONResponse(
            {
                "status": "error",
                "message": "Supabase URL or service_role key not set in environment variables.",
            },
            status_code=500,
        )
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    form = await request.form()
    if form:
        customer_id = form.get("customer_id")
        store_id = form.get("store_id")
        amount = form.get("amount")
        timestamp = form.get("timestamp")
        is_form = True
        action = form.get("duplicate_action")
    else:
        try:
            data = await request.json()
            customer_id = data.get("customer_id")
            store_id = data.get("store_id")
            amount = data.get("amount")
            timestamp = data.get("timestamp")
            is_form = False
            action = data.get("duplicate_action")
        except Exception as e:
            return JSONResponse(
                {"status": "error", "message": f"Invalid input: {str(e)}"},
                status_code=400,
            )

    if not customer_id or not store_id or amount is None or not timestamp:
        result_msg = "Missing required fields."
        if is_form:
            url = (
                request.url_for("transaction_entry_form") + f"?result={result_msg}"
            )
            return RedirectResponse(url, status_code=303)
        return JSONResponse(
            {"status": "error", "message": result_msg}, status_code=400
        )
    try:
        amount = float(amount)
    except Exception:
        result_msg = "Amount must be a number."
        if is_form:
            url = (
                request.url_for("transaction_entry_form") + f"?result={result_msg}"
            )
            return RedirectResponse(url, status_code=303)
        return JSONResponse(
            {"status": "error", "message": result_msg}, status_code=400
        )
    if amount <= 0:
        result_msg = "Amount must be greater than $0.00 USD."
        if is_form:
            url = (
                request.url_for("transaction_entry_form") + f"?result={result_msg}"
            )
            return RedirectResponse(url, status_code=303)
        return JSONResponse(
            {"status": "error", "message": result_msg}, status_code=400
        )

    # --- Deduplication logic ---
    duplicate_query = (
        supabase.table("Transactions")
        .select("transaction_id, customer_id, store_id, amount, timestamp")
        .eq("customer_id", customer_id)
        .eq("store_id", store_id)
        .eq("amount", amount)
        .eq("timestamp", timestamp)
        .execute()
    )
    duplicates = (
        duplicate_query.data
        if hasattr(duplicate_query, "data")
        else duplicate_query
    )
    if duplicates and not action:
        # Redirect back to form with message, pre-filled fields, and show radio buttons
        result_msg = (
            "Duplicate transaction detected! "
            "A transaction with the same customer, store, amount, and timestamp already exists. "
            "Please select how to proceed below."
        )
        # Pass all form fields and a flag to show radio buttons
        url = request.url_for("transaction_entry_form").include_query_params(
            result=result_msg,
            customer_id=customer_id,
            store_id=store_id,
            amount=amount,
            timestamp=timestamp,
            show_duplicate_options="1",
        )
        return RedirectResponse(str(url), status_code=303)
    elif duplicates and action == "block":
        result_msg = "Duplicate transaction blocked. No new record inserted."
        url = request.url_for("transaction_entry_form").include_query_params(
            result=result_msg
        )
        return RedirectResponse(str(url), status_code=303)
    elif duplicates and action == "prompt":
        # Show details of duplicates in plain text
        details = "; ".join(
            [
                f"ID: {d['transaction_id']}, Customer: {d['customer_id']}, Store: {d['store_id']}, Amount: {d['amount']}, Timestamp: {d['timestamp']}"
                for d in duplicates
            ]
        )
        result_msg = f"Duplicate(s) found: {details}"
        url = request.url_for("transaction_entry_form").include_query_params(
            result=result_msg
        )
        return RedirectResponse(str(url), status_code=303)
    # If action == "allow" or no duplicates, proceed with insert

    try:
        resp = (
            supabase.table("Transactions")
            .insert(
                {
                    "customer_id": customer_id,
                    "store_id": store_id,
                    "amount": amount,
                    "timestamp": timestamp,
                }
            )
            .execute()
        )
        if hasattr(resp, "data") and resp.data:
            result_msg = "Transaction added successfully!"
            url = request.url_for("transaction_entry_form").include_query_params(
                result=result_msg
            )
            return RedirectResponse(str(url), status_code=303)
        else:
            result_msg = "Failed to add transaction."
            url = request.url_for("transaction_entry_form").include_query_params(
                result=result_msg
            )
            return RedirectResponse(str(url), status_code=303)
    except Exception as e:
        result_msg = f"Error: {str(e)}"
        url = request.url_for("transaction_entry_form").include_query_params(
            result=result_msg
        )
        return RedirectResponse(str(url), status_code=303)

# Public endpoint: redacted data
@api_router.get("/transactions/public")
async def get_public_transactions():
    """
    Get public (redacted) transaction data from Supabase.

    Returns:
        dict: Customers and transactions data.
    """
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase URL or service_role key not set.")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    try:
        customers_resp = supabase.table("Customers_test").select("customer_id, first_name, last_name, created_at").execute()
        transactions_resp = supabase.table("Transactions").select("transaction_id, customer_id, store_id, amount, timestamp, description").execute()
        customers = getattr(customers_resp, "data", None)
        if customers is None or not isinstance(customers, list):
            customers = []
        transactions = getattr(transactions_resp, "data", None)
        if transactions is None or not isinstance(transactions, list):
            transactions = []
        return {"customers": customers, "transactions": transactions}
    except Exception as e:
        logger.error(f"Error fetching public transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch public transactions")

# Admin endpoint: full data, requires dashboard login
@api_router.get("/transactions/admin")
async def get_admin_transactions(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Get full transaction data for admin users (requires authentication).

    Args:
        credentials (HTTPBasicCredentials): Username and password for admin access.

    Returns:
        dict: Customers and transactions data.
    """
    username = credentials.username
    password = credentials.password
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase URL or service_role key not set.")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    try:
        resp = (
            supabase.table("DashboardUsers")
            .select("username, password_hash")
            .eq("username", username)
            .execute()
        )
        users = getattr(resp, "data", None)
        if not users or users[0]["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    except Exception as e:
        print("Exception in /api/v1/transactions/admin:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")
    # Return full data from Supabase
    try:
        customers_resp = supabase.table("Customers_test").select("*").execute()
        transactions_resp = supabase.table("Transactions").select("*").execute()
        customers = getattr(customers_resp, "data", None)
        if customers is None or not isinstance(customers, list):
            customers = []
        transactions = getattr(transactions_resp, "data", None)
        if transactions is None or not isinstance(transactions, list):
            transactions = []
        return {"customers": customers, "transactions": transactions}
    except Exception as e:
        logger.error(f"Error fetching admin transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch admin transactions")

@api_router.get("/transactions/recent")
async def get_recent_transactions():
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase URL or service_role key not set.")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    try:
        transactions_resp = supabase.table("Transactions") \
            .select("transaction_id, customer_id, store_id, amount, timestamp, description") \
            .order("timestamp", desc=True) \
            .limit(20) \
            .execute()
        transactions = transactions_resp.data if hasattr(transactions_resp, "data") else transactions_resp
        return {"transactions": transactions}
    except Exception as e:
        logger.error(f"Error fetching recent public transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent public transactions")

@api_router.get("/transactions/recent/admin")
async def get_recent_transactions_admin(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="Supabase URL or service_role key not set.")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    try:
        resp = (
            supabase.table("DashboardUsers")
            .select("username, password_hash")
            .eq("username", username)
            .execute()
        )
        users = resp.data if hasattr(resp, "data") else resp
        if not users or users[0]["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    except Exception as e:
        print("Exception in /transactions/recent/admin:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Auth error: {str(e)}")
    try:
        transactions_resp = supabase.table("Transactions") \
            .select("*") \
            .order("timestamp", desc=True) \
            .limit(20) \
            .execute()
        transactions = transactions_resp.data if hasattr(transactions_resp, "data") else transactions_resp
        return {"transactions": transactions}
    except Exception as e:
        logger.error(f"Error fetching recent admin transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent admin transactions")

@page_router.get("/transactions", response_class=HTMLResponse)
async def transactions_page(request: Request):
    return Jinja2Templates(directory="app/templates").TemplateResponse(
        "transactions.html", {"request": request, "username": request.session.get("username")}
    )

@page_router.get("/transactions/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: str = ""):
    return Jinja2Templates(directory="app/templates").TemplateResponse(
        "admin_login.html", {"request": request, "error": error}
    )

@page_router.post("/transactions/admin-login", response_class=HTMLResponse)
async def admin_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return HTMLResponse("<h2>Supabase URL or service_role key not set in environment variables.</h2>", status_code=500)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    users = supabase.table("DashboardUsers").select("username, password_hash").eq("username", username).execute().data
    if not users or users[0]["password_hash"] != password_hash:
        return Jinja2Templates(directory="app/templates").TemplateResponse(
            "admin_login.html", {"request": request, "error": "Invalid username or password."}
        )
    request.session["username"] = username
    return RedirectResponse("/transactions/admin", status_code=303)

@page_router.get("/transactions/admin", response_class=HTMLResponse)
async def admin_transactions_page(request: Request):
    username = request.session.get("username")
    if not username:
        return RedirectResponse("/transactions/admin-login", status_code=303)
    return Jinja2Templates(directory="app/templates").TemplateResponse(
        "admin_transactions.html", {"request": request, "username": username}
    )

@page_router.get("/transactions/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/transactions", status_code=303)

@page_router.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/dashboard")

__all__ = ["api_router", "page_router"]
