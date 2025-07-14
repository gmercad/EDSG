"""
Economic Development Snapshot Generator
Main FastAPI application entry point
"""

import sys

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

print("Python executable:", sys.executable)
# Load environment variables
load_dotenv()

#import os
#print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
#print("SUPABASE_SERVICE_ROLE_KEY:", os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

# Create FastAPI app instance
app = FastAPI(
    title="Economic Development Snapshot Generator",
    description="API for generating economic development snapshots using World Bank data and LLMs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add SessionMiddleware for signed cookies
app.add_middleware(SessionMiddleware, secret_key="super-secret-session-key-change-this")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Import routes
from app.routes import register_routes
from app.routes import router as api_router
from app.utils import fetch_country_code_mapping


@app.on_event("startup")
async def startup_event():
    await fetch_country_code_mapping()


# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Register dashboard.html route at root
register_routes(app, templates)

# Remove or comment out the old root endpoint to avoid conflict
# @app.get("/")
# async def root():
#     """Root endpoint with basic project information"""
#     return {
#         "message": "Economic Development Snapshot Generator API",
#         "version": "1.0.0",
#         "docs": "/docs",
#         "status": "running"
#     }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "economic-development-snapshot-generator"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
