import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
PS_DATABASE_URL = os.getenv("PS_DB_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if not PS_DATABASE_URL:
    raise RuntimeError("PS_DB_URL is not set in the environment.")
ps_engine = create_engine(PS_DATABASE_URL)
SessionLocalPS = sessionmaker(autocommit=False, autoflush=False, bind=ps_engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_ps_db():
    db = SessionLocalPS()
    try:
        yield db
    finally:
        db.close()
