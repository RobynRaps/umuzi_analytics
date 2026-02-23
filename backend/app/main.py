import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # <--- NEW IMPORT
from sqlalchemy.orm import Session

# Imports from your app structure
from .db import Base, SessionLocal, engine
from .models import AnalysisResult

# Create DB Tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Starting Umuzi Analytics Engine")

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (Safe for this stage of dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis Connection
celery_app = Celery(
    "worker", broker=os.getenv("CELERY_BROKER_URL", "redis://queue:6379/0")
)


# --- REQUEST MODELS (THE FIX) ---
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


@app.get("/")
def health_check():
    return {"status": "Research System Online", "version": "1.0.0"}


@app.post("/analyze")
def submit_transcript(request: TranscriptRequest):
    """
    Endpoint 1: Submit a job.
    Accepts text in the JSON Body (allows large files).
    """
    # Push to Celery Queue
    task = celery_app.send_task("app.worker.analyze_task", args=[request.text])
    return {"job_id": task.id, "status": "Queued", "filename": request.filename}


@app.get("/results/{job_id}")
def get_analysis_results(job_id: str, db: Session = Depends(get_db)):
    """
    Endpoint 2: Poll for results.
    """
    # 1. Check Database first
    record = db.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()

    if record:
        return record

    # 2. Check Celery State
    task_result = AsyncResult(job_id, app=celery_app)

    if task_result.state == "PENDING":
        return {"status": "PENDING", "message": "Job is waiting in queue..."}
    elif task_result.state == "STARTED":
        return {"status": "PROCESSING", "message": "NLP Engine is analyzing..."}
    elif task_result.state == "FAILURE":
        return {"status": "FAILED", "error": str(task_result.result)}

    return {"status": "UNKNOWN", "message": "Job ID not found."}


@app.get("/history")
def get_job_history(limit: int = 10, db: Session = Depends(get_db)):
    """
    Returns the latest jobs saved in the database.
    """
    jobs = (
        db.query(AnalysisResult).order_by(AnalysisResult.id.desc()).limit(limit).all()
    )
    return jobs


@app.get("/action-plans")
def get_all_action_plans(db: Session = Depends(get_db)):
    """
    Returns specific audit data: Job ID, Sentiment, and Action Plan.
    """
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
