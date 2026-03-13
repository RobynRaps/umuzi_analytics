# app/worker.py

import os
from celery import Celery
from sqlalchemy.orm import Session
from .db import SessionLocal
from .meta_collector import fetch_page_insights

celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://queue:6379/0")
)

@celery_app.task
def fetch_meta_data_task(page_id: str, access_token: str):
    db: Session = SessionLocal()
    try:
        fetch_page_insights(page_id, access_token, db)
    finally:
        db.close()