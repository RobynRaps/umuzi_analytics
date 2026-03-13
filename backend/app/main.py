import os
import requests
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Imports from your app structure
from .db import Base, SessionLocal, engine
from .models import AnalysisResult, MetaInsight

# Create DB Tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Starting Umuzi Analytics Engine")

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Redis / Celery Configuration ---
celery_app = Celery(
    "worker", broker=os.getenv("CELERY_BROKER_URL", "redis://queue:6379/0")
)

# --- REQUEST MODELS ---
class TranscriptRequest(BaseModel):
    text: str
    filename: str = "unknown_file"


# Dependency to get DB Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Health Check
# -------------------------
@app.get("/")
def health_check():
    return {"status": "Research System Online", "version": "1.0.0"}


# -------------------------
# NLP Analysis Endpoints
# -------------------------
@app.post("/analyze")
def submit_transcript(request: TranscriptRequest):

    task = celery_app.send_task("app.worker.analyze_task", args=[request.text])

    return {
        "job_id": task.id,
        "status": "Queued",
        "filename": request.filename
    }


@app.get("/results/{job_id}")
def get_analysis_results(job_id: str, db: Session = Depends(get_db)):

    record = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()

    if record:
        return record

    task_result = AsyncResult(job_id, app=celery_app)

    if task_result.state == "PENDING":
        return {"status": "PENDING"}

    elif task_result.state == "STARTED":
        return {"status": "PROCESSING"}

    elif task_result.state == "FAILURE":
        return {"status": "FAILED", "error": str(task_result.result)}

    return {"status": "UNKNOWN"}


@app.get("/history")
def get_job_history(limit: int = 10, db: Session = Depends(get_db)):

    jobs = (
        db.query(AnalysisResult)
        .order_by(AnalysisResult.id.desc())
        .limit(limit)
        .all()
    )

    return jobs


@app.get("/action-plans")
def get_all_action_plans(db: Session = Depends(get_db)):

    results = (
        db.query(
            AnalysisResult.job_id,
            AnalysisResult.sentiment_score,
            AnalysisResult.action_plan,
        )
        .order_by(AnalysisResult.id.desc())
        .all()
    )

    return [
        {
            "job_id": row.job_id,
            "sentiment_score": row.sentiment_score,
            "action_plan": row.action_plan,
        }
        for row in results
    ]


# -------------------------
# Meta OAuth Configuration
# -------------------------

APP_ID = os.getenv("META_APP_ID")
APP_SECRET = os.getenv("META_APP_SECRET")
REDIRECT_URI = os.getenv("META_REDIRECT_URI")

ACCESS_TOKEN = None


# -------------------------
# Step 1: Login with Facebook
# -------------------------
@app.get("/meta/login")
def meta_login():

    if not APP_ID:
        raise HTTPException(status_code=500, detail="META_APP_ID not set")

    oauth_url = (
        f"https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope=public_profile&"
        f"response_type=code"
    )

    return {
        "login_url": oauth_url
    }

# -------------------------
# Step 2: OAuth Callback
# -------------------------
@app.get("/oauth/callback")
def oauth_callback(code: str = Query(...)):

    global ACCESS_TOKEN

    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"

    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "client_secret": APP_SECRET,
        "code": code
    }

    r = requests.get(token_url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get token")

    ACCESS_TOKEN = r.json()["access_token"]

    return {"message": "Meta login successful"}


# -------------------------
# Step 3: Get Facebook Pages
# -------------------------
@app.get("/meta/pages")
def get_pages():

    if not ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Login first")

    url = "https://graph.facebook.com/v19.0/me/accounts"

    r = requests.get(
        url,
        params={"access_token": ACCESS_TOKEN}
    )

    return r.json()


# -------------------------
# Step 4: Get Page Insights
# -------------------------
@app.get("/meta/page-insights/{page_id}")
def get_page_insights(page_id: str):

    if not ACCESS_TOKEN:
        raise HTTPException(status_code=400, detail="Login first")

    url = f"https://graph.facebook.com/v19.0/{page_id}/insights"

    params = {
        "metric": "page_impressions,page_engaged_users,page_fans",
        "access_token": ACCESS_TOKEN
    }

    r = requests.get(url, params=params)

    return r.json()