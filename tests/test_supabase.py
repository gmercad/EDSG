import os
import pytest
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables from .env if present
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")


@pytest.fixture(scope="module")
def supabase():
    """Fixture to provide a Supabase client using the service_role key."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@pytest.mark.parametrize("table_name", ["Customers_test", "Stores", "Transactions"])
def test_table(table_name, supabase):
    """Test access to main Supabase tables."""
    try:
        response = supabase.table(table_name).select("*").limit(1).execute()
        assert response.data is not None
    except Exception as e:
        pytest.fail(f"Error accessing {table_name}: {e}")
