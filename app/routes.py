"""
API routes for Economic Development Snapshot Generator
"""

import hashlib
import logging
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import (APIRouter, Body, Depends, FastAPI, HTTPException,
                     Request, Form)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from supabase import Client, create_client

from app.utils import (fetch_world_bank_data, generate_snapshot_with_llm,
                       validate_country_code, validate_indicator_code)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

security = HTTPBasic()


# Pydantic models for request/response
class SnapshotRequest(BaseModel):
    country_code: str = "USA"  # United States is valid for NY.GDP.MKTP.CD
    indicator_codes: List[str] = ["NY.GDP.MKTP.CD"]
    year: Optional[int] = 2021
    llm_provider: str = "openai"  # "openai" or "lm_studio"


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
            {"code": "CAN", "name": "Canada"},
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
                "indicator_count": len(request.indicator_codes),
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


@router.get("/data/{country_code}")
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


@router.get("/health")
async def api_health_check():
    """
    Health check for the API
    """
    return {"status": "healthy", "api": "economic-development-snapshot-generator"}


# --- Data Quality Agent Endpoint ---
@router.post("/data-quality/scan")
async def data_quality_scan(request: Request, action: str = Body("report_only")):
    """
    Step 1: Data Quality Agent for Supabase Tables
    Accepts 'action' parameter: 'report_only' or 'report_and_fix'.
    If 'report_and_fix', attempts to fix detected issues.
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
    import datetime

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
    import json

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
@router.get("/data-quality/dashboard")
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


def register_routes(app: FastAPI, templates: Jinja2Templates):
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/login", response_class=HTMLResponse)
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

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/transactions/entry")):
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            return HTMLResponse("<h2>Supabase URL or service_role key not set in environment variables.</h2>", status_code=500)
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
                return RedirectResponse(f"/login?error=Invalid+username+or+password.&next={next}", status_code=303)
        except Exception as e:
            return RedirectResponse(f"/login?error=Auth+error:+{str(e)}&next={next}", status_code=303)
        # Set session
        request.session["username"] = username
        return RedirectResponse(next, status_code=303)

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    @app.get("/transactions/entry", response_class=HTMLResponse)
    async def transaction_entry_form(request: Request):
        username = request.session.get("username")
        if not username:
            return RedirectResponse("/login?next=/transactions/entry", status_code=303)
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            return HTMLResponse("<h2>Supabase URL or service_role key not set in environment variables.</h2>", status_code=500)
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        try:
            customers_resp = supabase.table("Customers_test").select("customer_id, first_name, last_name").execute()
            stores_resp = supabase.table("Stores").select("store_id, name").execute()
            customers = customers_resp.data if hasattr(customers_resp, 'data') else customers_resp
            stores = stores_resp.data if hasattr(stores_resp, 'data') else stores_resp
        except Exception as e:
            return HTMLResponse(f"<h2>Error fetching customers or stores: {str(e)}</h2>", status_code=500)
        result = request.query_params.get("result")
        # Pre-fill fields if present
        customer_id = request.query_params.get('customer_id', '')
        store_id = request.query_params.get('store_id', '')
        amount = request.query_params.get('amount', '')
        timestamp = request.query_params.get('timestamp', '')
        show_duplicate_options = request.query_params.get('show_duplicate_options')
        # Build dropdowns
        customer_options = "<option value=''>Select a customer</option>" + "".join([
            f"<option value='{c['customer_id']}'{' selected' if str(customer_id)==str(c['customer_id']) else ''}>{c['first_name']} {c['last_name']}</option>" for c in customers
        ])
        store_options = "<option value=''>Select a store</option>" + "".join([
            f"<option value='{s['store_id']}'{' selected' if str(store_id)==str(s['store_id']) else ''}>{s['name']}</option>" for s in stores
        ])
        # Top right button
        if username:
            top_right = f"<span>Logged in as {username}</span> <a href='/logout'><button type='button'>Logout</button></a>"
        else:
            top_right = "<a href='/login'><button type='button'>Service Role Login</button></a>"
        # Duplicate radio buttons
        duplicate_html = ""
        if show_duplicate_options:
            duplicate_html = f"""
            <div class='alert error' style='margin-bottom: 1rem;'>
                {result or ''}
            </div>
            <div style='margin-bottom: 1rem;'>
                <label><input type='radio' name='duplicate_action' value='block' required> Block Duplicate</label>
                <label><input type='radio' name='duplicate_action' value='allow' required> Allow Duplicate</label>
            </div>
            """
        # Main form
        html = f"""
        <!DOCTYPE html>
        <html lang='en'>
        <head>
            <meta charset='UTF-8'>
            <title>New Transaction Entry</title>
            <link rel='stylesheet' href='/static/styles.css'>
            <style>.top-right{{position:absolute;top:1rem;right:1rem;}}</style>
        </head>
        <body>
            <div class='top-right'>{top_right}</div>
            <h1>Enter a New Transaction</h1>
            <form action='/transactions/new' method='post'>
                <label for='customer_id'>Customer:</label>
                <select id='customer_id' name='customer_id' required>{customer_options}</select>
                <label for='store_id'>Store:</label>
                <select id='store_id' name='store_id' required>{store_options}</select>
                <label for='amount'>Amount (USD):</label>
                <input type='number' id='amount' name='amount' min='0.01' step='0.01' required value='{amount}'>
                <label for='timestamp'>Timestamp:</label>
                <input type='datetime-local' id='timestamp' name='timestamp' required value='{timestamp}'>
                {duplicate_html}
                <button type='submit'>Submit Transaction</button>
            </form>
            {f"<div id='result'>{result}</div>" if result and not show_duplicate_options else ''}
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    @app.post("/transactions/new")
    async def add_transaction(request: Request):
        """
        Allows a user to add a new transaction to the Transactions table.
        Accepts both JSON and form submissions.
        Deduplicates on customer_id, store_id, amount, timestamp before insert.
        """
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            return JSONResponse({
                "status": "error",
                "message": "Supabase URL or service_role key not set in environment variables."
            }, status_code=500)
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
                return JSONResponse({"status": "error", "message": f"Invalid input: {str(e)}"}, status_code=400)

        if not customer_id or not store_id or amount is None or not timestamp:
            result_msg = "Missing required fields."
            if is_form:
                url = request.url_for("transaction_entry_form") + f"?result={result_msg}"
                return RedirectResponse(url, status_code=303)
            return JSONResponse({"status": "error", "message": result_msg}, status_code=400)
        try:
            amount = float(amount)
        except Exception:
            result_msg = "Amount must be a number."
            if is_form:
                url = request.url_for("transaction_entry_form") + f"?result={result_msg}"
                return RedirectResponse(url, status_code=303)
            return JSONResponse({"status": "error", "message": result_msg}, status_code=400)
        if amount <= 0:
            result_msg = "Amount must be greater than $0.00 USD."
            if is_form:
                url = request.url_for("transaction_entry_form") + f"?result={result_msg}"
                return RedirectResponse(url, status_code=303)
            return JSONResponse({"status": "error", "message": result_msg}, status_code=400)

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
        duplicates = duplicate_query.data if hasattr(duplicate_query, 'data') else duplicate_query
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
                show_duplicate_options="1"
            )
            return RedirectResponse(str(url), status_code=303)
        elif duplicates and action == "block":
            result_msg = "Duplicate transaction blocked. No new record inserted."
            url = request.url_for("transaction_entry_form").include_query_params(result=result_msg)
            return RedirectResponse(str(url), status_code=303)
        elif duplicates and action == "prompt":
            # Show details of duplicates in plain text
            details = "; ".join([
                f"ID: {d['transaction_id']}, Customer: {d['customer_id']}, Store: {d['store_id']}, Amount: {d['amount']}, Timestamp: {d['timestamp']}"
                for d in duplicates
            ])
            result_msg = f"Duplicate(s) found: {details}"
            url = request.url_for("transaction_entry_form").include_query_params(result=result_msg)
            return RedirectResponse(str(url), status_code=303)
        # If action == "allow" or no duplicates, proceed with insert

        try:
            resp = supabase.table("Transactions").insert({
                "customer_id": customer_id,
                "store_id": store_id,
                "amount": amount,
                "timestamp": timestamp
            }).execute()
            if hasattr(resp, 'data') and resp.data:
                result_msg = "Transaction added successfully!"
                url = request.url_for("transaction_entry_form").include_query_params(result=result_msg)
                return RedirectResponse(str(url), status_code=303)
            else:
                result_msg = "Failed to add transaction."
                url = request.url_for("transaction_entry_form").include_query_params(result=result_msg)
                return RedirectResponse(str(url), status_code=303)
        except Exception as e:
            result_msg = f"Error: {str(e)}"
            url = request.url_for("transaction_entry_form").include_query_params(result=result_msg)
            return RedirectResponse(str(url), status_code=303)
