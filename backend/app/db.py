import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Get Database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for Heroku/Railway using "postgres://" instead of "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- THE FIX IS HERE ---
# pool_pre_ping=True: Checks if connection is alive before using it (Fixes SSL EOF error)
# pool_recycle=1800: Recycles connections every 30 mins to prevent stale timeouts
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
