# app/meta_collector.py

import requests
from sqlalchemy.orm import Session
from .models import MetaInsight

# Fetch Page/Instagram insights using a stored token
def fetch_page_insights(page_id: str, access_token: str, db: Session):
    """
    Pulls Facebook Page and Instagram metrics and saves to database
    """
    metrics = "page_impressions,page_engaged_users"
    url = f"https://graph.facebook.com/v19.0/{page_id}/insights"

    response = requests.get(url, params={"access_token": access_token, "metric": metrics})
    data = response.json()

    # Save data to database
    if "data" in data:
        for metric in data["data"]:
            insight = MetaInsight(
                page_id=page_id,
                metric_name=metric["name"],
                values=metric["values"]
            )
            db.add(insight)
        db.commit()