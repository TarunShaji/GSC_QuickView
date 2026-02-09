"""
FastAPI wrapper for GSC Quick View pipeline.

This is a minimal HTTP interface that exposes the existing pipeline
via authentication and execution endpoints.

Endpoints:
  - GET  /health        → Health check
  - GET  /auth/status   → Check GSC authentication status
  - POST /auth/login    → Trigger Google OAuth (opens browser)
  - POST /pipeline/run  → Execute the full pipeline (blocking)

Usage:
    uvicorn api:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Import pipeline + GSC client
from main import run_pipeline
from gsc_client import GSCClient


# Initialize FastAPI app
app = FastAPI(
    title="GSC Quick View API",
    description="HTTP wrapper for Google Search Console analytics pipeline",
    version="1.0.0"
)


# -------------------------
# Health
# -------------------------

@app.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "ok"}


# -------------------------
# Authentication
# -------------------------

@app.get("/auth/status")
def auth_status():
    """
    Check whether backend is authenticated with Google Search Console.
    """
    client = GSCClient()
    return {
        "authenticated": client.is_authenticated()
    }


@app.post("/auth/login")
def auth_login():
    """
    Trigger Google OAuth flow.

    This will:
    - Open a browser
    - Ask the user to log in and grant permissions
    - Store token.json on the backend
    """
    client = GSCClient()
    client.authenticate()  # Opens browser
    return {"status": "authenticated"}


# -------------------------
# Pipeline
# -------------------------

@app.post("/pipeline/run")
def run_pipeline_endpoint():
    """
    Execute the full GSC analytics pipeline.

    Requirements:
    - Backend must already be authenticated
    """
    client = GSCClient()

    if not client.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Google Search Console. Run /auth/login first."
        )

    # Run the pipeline synchronously (blocking)
    run_pipeline()

    return {"status": "completed"}