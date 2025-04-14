# File: app/storage.py

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models import Assignment, PendingReview, SubmissionHistory
from app.supabase_client import supabase
import os

# ✅ Load DB URL from .env
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ Set up database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# ----------------------------
# ✅ ASSIGNMENTS
# ----------------------------

def save_assignment_data(data):
    session = SessionLocal()
    try:
        for item in data:
            existing = session.query(Assignment).filter_by(assignment_title=item["assignment_title"]).first()
            if existing:
                for key, value in item.items():
                    setattr(existing, key, value)
            else:
                new_assignment = Assignment(**item)
                session.add(new_assignment)
        session.commit()
    finally:
        session.close()


def load_assignment_data():
    session = SessionLocal()
    try:
        return {a.assignment_title: a.to_dict() for a in session.query(Assignment).all()}
    finally:
        session.close()


# ----------------------------
# ✅ PENDING REVIEWS
# ----------------------------

def store_pending_feedback(submission_id, data):
    session = SessionLocal()
    try:
        existing = session.query(PendingReview).filter_by(submission_id=submission_id).first()
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            session.add(PendingReview(**data))
        session.commit()
    finally:
        session.close()


def load_pending_feedback(submission_id):
    session = SessionLocal()
    try:
        pending = session.query(PendingReview).filter_by(submission_id=submission_id).first()
        return pending.to_dict() if pending else None
    finally:
        session.close()


def load_all_pending_feedback():
    session = SessionLocal()
    try:
        return [r.to_dict() for r in session.query(PendingReview).all()]
    finally:
        session.close()


# ----------------------------
# ✅ SUBMISSION HISTORY
# ----------------------------

def store_submission_history(data):
    session = SessionLocal()
    try:
        session.add(SubmissionHistory(**data))
        session.commit()
    finally:
        session.close()

def upload_to_supabase(file_path, filename, folder="rubrics"):
    try:
        with open(file_path, "rb") as f:
            data = f.read()

        filepath = f"{folder}/{filename}"
        supabase.storage.from_("rubrics").upload(filepath, data)
        supabase.storage.from_("rubrics").update(filepath, {"cacheControl": "3600", "upsert": True})

        public_url = supabase.storage.from_("rubrics").get_public_url(filepath)
        return public_url
    except Exception as e:
        print("❌ Supabase Upload Failed:", str(e))
        return None

