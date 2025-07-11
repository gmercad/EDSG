
# Project Requirements Document
**Project Name**: Economic Development Snapshot Generator
**Team**: Luis Frias & Greg Mercado
**Primary Language**: Python
**IDE**: Cursor
**LLMs**: OpenAI API + LM Studio (Mistral-7B-Instruct-v0.1)
**Data Source**: World Bank Open Data API
**Frameworks & Libraries**: FastAPI, Pandas, Langchain
**Database & Auth**: Supabase (with Row-Level Security)
**Workflow Orchestration**: MCP (Multi-Agent Control Plane)

## Folder Structure
```
economic_development_snapshot_generator/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── routes.py            # API route definitions
│   ├── utils.py             # Utility functions (data fetching, validation, etc.)
│   ├── templates/
│   │   └── dashboard.html   # Optional HTML template for snapshot display
│   └── static/              # Static assets (if needed)
├── tests/                   # Unit and integration tests
├── requirements.txt         # Python dependencies
└── README.md                # Project overview and setup instructions
```

## Task Breakdown for Agentic Coding

Each task is designed to be modular, testable, and independently verifiable before proceeding to the next.

### Phase 1: Project Setup
1. **Initialize project structure**
2. **Create requirements.txt**

### Phase 2: Core Application Logic
3. **Implement FastAPI app entry point (`main.py`)**
4. **Define API routes (`routes.py`)**
5. **Implement utility functions (`utils.py`)**

### Phase 3: LLM Integration
6. **Integrate Langchain with OpenAI and LM Studio**
7. **Implement snapshot generation logic**

### Phase 4: Validation & Testing
8. **Implement validation logic**
9. **Write unit tests (`tests/`)**
10. **Run linting and formatting**

### Phase 5: Supabase Integration
11. **Design Supabase schema**
12. **Connect FastAPI to Supabase**

### Phase 6: Final Testing & Review
13. **End-to-end test of full workflow**
14. **Document everything**

## README Instructions for Setup and Usage

### Environment Setup
1. Clone the repository `git clone <repo_url>`
2. Navigate to the project directory
3. Create a virtual environment: `python -m venv env`
4. Activate the virtual environment: `source env/bin/activate` (Linux/Mac) or `env\Scriptsctivate` (Windows)
5. Install dependencies: `pip install -r requirements.txt`

### Running the Application
1. Start the FastAPI server: `uvicorn app.main:app --reload`
2. Access the API via `http://127.0.0.1:8000/`

### Running Tests
1. Run tests with `pytest` from the project root directory

### Configuration
1. Set up environment variables if needed (e.g., API keys, Supabase credentials)

**Note**: Make sure you have set up the database and LLM credentials as per instructions in the project documentation.

---
