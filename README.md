# Economic Development Snapshot Generator

## Features
- Generate economic development snapshots using World Bank data and LLMs
- Data quality agent for Supabase tables (Customers_test, Stores, Transactions)
- Automated data quality checks: nulls, duplicates, referential integrity, value ranges
- "Report & Fix" logic to automatically clean data issues
- Transaction entry subpage (Jinja2, FastAPI)
- Dashboard for data quality logs (protected by username/password)
- Modular, testable codebase with robust error handling

## Setup

### 1. Clone the Repository
```sh
git clone <repo-url>
cd EDSG
```

### 2. Install Dependencies (with Poetry)
```sh
poetry install
```

### 3. Environment Variables
Create a `.env` file in the project root with:
```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
```

### 4. Supabase Table Setup
Create the following tables in your Supabase project:

#### Customers_test
- `id` (UUID or int, PK)
- `name` (string)
- `email` (string, unique)
- `store_id` (FK to Stores.id)

#### Stores
- `id` (UUID or int, PK)
- `name` (string)
- `location` (string)

#### Transactions
- `id` (UUID or int, PK)
- `customer_id` (FK to Customers_test.id)
- `store_id` (FK to Stores.id)
- `amount` (float, > 0, not null)
- `timestamp` (datetime, not null)

#### DataQualityLogs
```sql
create table if not exists "DataQualityLogs" (
    id uuid primary key default gen_random_uuid(),
    created_at timestamp with time zone default timezone('utc', now()),
    findings jsonb not null,
    anomalies jsonb not null,
    user_prompt jsonb
);
```

#### DashboardUsers
```sql
create table if not exists "DashboardUsers" (
    username text primary key,
    password_hash text not null
);
```
To add a user:
- Hash the password with SHA256 (see below)
- Insert username and hash into DashboardUsers

### 5. Hashing Passwords for DashboardUsers
```python
import hashlib
print(hashlib.sha256("yourpassword".encode()).hexdigest())
```

## Usage

### Run the App
```sh
poetry run uvicorn app.main:app --reload
```

### Data Quality Agent
- POST `/data-quality/scan` with `{ "action": "report_only" }` or `{ "action": "report_and_fix" }`
- Checks for nulls, duplicates, referential integrity, and value ranges
- If `report_and_fix`, will remove/fix issues and log actions

### Transaction Entry
- Go to `/transactions/entry` (link in dashboard sidebar)
- Enter a new transaction via the form (customer, store, amount, timestamp)

### Dashboard & Authentication
- Go to `/data-quality/dashboard`
- Authenticate with username/password (must exist in DashboardUsers table)
- View latest data quality logs and actions

## Testing & Linting

### Run Tests
```sh
poetry run pytest -v
```

### Linting
```sh
poetry run black --check .
poetry run flake8 --ignore=E501 .  # Ignores line too long
poetry run isort --check-only .
poetry run ruff check .
```

### Code Formatting & Docstrings
- All code is auto-formatted with Black and isort.
- Linting is enforced with flake8 (except line length) and ruff.
- Use Google-style or Sphinx-style docstrings for all public functions and classes.
- Keep imports at the top of each file (per PEP8).

### Error Handling
- All API endpoints and utility functions include robust error handling and logging.
- User-facing errors are returned as JSON with appropriate HTTP status codes.
- Backend logs provide detailed tracebacks for debugging.

### Dashboard & Snapshot UI
- The dashboard snapshot and chat UI now use JSON-based AJAX for all interactions.
- Snapshot generation and follow-up chat are fully asynchronous and stateful, with Redis for session/chat storage.

### FastAPI Deprecation Note
- You may see a warning about `@app.on_event("startup")` being deprecated. This does not affect functionality, but you can migrate to FastAPI's new lifespan event handlers in the future.

### Code Documentation
- All public functions and classes use Google-style docstrings for clarity and consistency.
- Inline comments are added to clarify non-obvious logic and important implementation details.
- Please follow these standards for any new code or contributions.

## Contributing
- Please open issues or pull requests for improvements or bugfixes.
- Follow PEP8 and use Poetry for dependency management.

## License
MIT License
