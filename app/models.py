# File: app/models.py

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, Text

Base = declarative_base()

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    assignment_title = Column(String, unique=True)
    rubric_file = Column(String)
    total_points = Column(Integer)
    instructor_approval = Column(Boolean)
    requires_persona = Column(Boolean)
    faith_integration = Column(Boolean)
    grading_difficulty = Column(String)
    student_level = Column(String)
    feedback_tone = Column(String)
    ai_notes = Column(Text)

    def to_dict(self):
        return {
            "assignment_title": self.assignment_title,
            "rubric_file": self.rubric_file,
            "total_points": self.total_points,
            "instructor_approval": self.instructor_approval,
            "requires_persona": self.requires_persona,
            "faith_integration": self.faith_integration,
            "grading_difficulty": self.grading_difficulty,
            "student_level": self.student_level,
            "feedback_tone": self.feedback_tone,
            "ai_notes": self.ai_notes
        }


class PendingReview(Base):
    __tablename__ = "pending_reviews"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(String, unique=True)
    student_id = Column(String)
    assignment_title = Column(String)
    timestamp = Column(String)
    score = Column(Integer)
    feedback = Column(Text)
    student_text = Column(Text)
    ai_check_result = Column(Text)
    notes = Column(Text)

    def to_dict(self):
        return {
            "submission_id": self.submission_id,
            "student_id": self.student_id,
            "assignment_title": self.assignment_title,
            "timestamp": self.timestamp,
            "score": self.score,
            "feedback": self.feedback,
            "student_text": self.student_text,
            "ai_check_result": self.ai_check_result,
            "notes": self.notes
        }


class SubmissionHistory(Base):
    __tablename__ = "submission_history"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(String, unique=True)
    student_id = Column(String)
    assignment_title = Column(String)
    timestamp = Column(String)
    score = Column(Integer)
    feedback = Column(Text)
    student_text = Column(Text)
    ai_check_result = Column(Text)
    notes = Column(Text)

    def to_dict(self):
        return {
            "submission_id": self.submission_id,
            "student_id": self.student_id,
            "assignment_title": self.assignment_title,
            "timestamp": self.timestamp,
            "score": self.score,
            "feedback": self.feedback,
            "student_text": self.student_text,
            "ai_check_result": self.ai_check_result,
            "notes": self.notes
        }
