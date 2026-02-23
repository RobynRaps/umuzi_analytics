from sqlalchemy import JSON, Column, Float, Integer, String, Text

from .db import Base

# create data models for meta, linkedin and google' apis


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)

    # The Input Data
    original_text_snippet = Column(Text)

    # The Analysis Results
    sentiment_score = Column(Float)
    topic_keywords = Column(Text)  # <--- THIS WAS MISSING
    sentiment_time_series = Column(JSON)  # <--- ENSURE THIS IS HERE TOO

    # The Decision
    action_plan = Column(JSON)

    # Meta
    status = Column(String, default="PENDING")
