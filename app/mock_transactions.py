import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) must be set in your environment or .env file."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# Fetch all customer_ids
def fetch_ids(table, id_col):
    response = supabase.table(table).select(id_col).execute()
    if response.data:
        return [row[id_col] for row in response.data]
    else:
        raise Exception(f"No data found in {table} or column {id_col} not found.")


def random_date(start, end):
    """Return a random datetime between start and end."""
    return start + timedelta(
        seconds=random.randint(0, int((end - start).total_seconds()))
    )


def main():
    # Adjust these column names if needed
    customer_id_col = "customer_id"
    store_id_col = "store_id"

    print("Fetching customer and store IDs...")
    customer_ids = fetch_ids("Customers_test", customer_id_col)
    store_ids = fetch_ids("Stores", store_id_col)
    print(f"Found {len(customer_ids)} customers and {len(store_ids)} stores.")

    # Assign each customer a home store
    home_store = {cid: random.choice(store_ids) for cid in customer_ids}

    # Generate 100 transactions
    now = datetime.utcnow()
    two_years_ago = now - timedelta(days=2 * 365)
    transactions = []
    for _ in range(100):
        cid = random.choice(customer_ids)
        # 95% use home store, 5% use random other store
        if random.random() < 0.95 or len(store_ids) == 1:
            sid = home_store[cid]
        else:
            sid = random.choice([s for s in store_ids if s != home_store[cid]])
        amount = round(random.uniform(5, 500), 2)
        ts = random_date(two_years_ago, now).isoformat()
        transactions.append(
            {"customer_id": cid, "store_id": sid, "amount": amount, "timestamp": ts}
        )

    print(f"Inserting {len(transactions)} transactions...")
    # Insert in batches of 50 to avoid payload limits
    for i in range(0, len(transactions), 50):
        batch = transactions[i : i + 50]
        resp = supabase.table("Transactions").insert(batch).execute()
        print(
            f"Inserted batch {i//50+1}: {resp.data if hasattr(resp, 'data') else resp}"
        )

    print("Done.")


if __name__ == "__main__":
    main()
