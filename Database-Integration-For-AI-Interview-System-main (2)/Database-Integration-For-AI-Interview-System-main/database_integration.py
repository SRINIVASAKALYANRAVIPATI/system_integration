from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Numeric, Text, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Update these details with your actual PostgreSQL credentials
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/interview_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Mapped Tables from your SQL File ---

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time = Column(DateTime(timezone=True))
    total_risk_score = Column(Numeric(5, 2), default=0.00)
    status = Column(String, default='IN_PROGRESS')

class ObjectDetectionEvent(Base):
    __tablename__ = 'object_detection_events'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('interview_sessions.id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    object_detected = Column(String, nullable=False)
    confidence_score = Column(Numeric(5, 2), nullable=False)
    snapshot_url = Column(Text)

class FacePoseEvent(Base):
    __tablename__ = 'face_pose_events'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('interview_sessions.id'), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    event_type = Column(String, nullable=False)
    duration_ms = Column(Integer, default=0)
    severity_score = Column(Integer, default=1)

class AudioTranscript(Base):
    __tablename__ = 'audio_transcripts'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('interview_sessions.id'), nullable=False)
    start_timestamp = Column(DateTime(timezone=True))
    end_timestamp = Column(DateTime(timezone=True))
    text_content = Column(Text, nullable=False)
    is_multiple_speakers = Column(Boolean, default=False)

class AnswerEvaluation(Base):
    __tablename__ = 'answer_evaluations'
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('interview_sessions.id'), nullable=False)
    question_id = Column(String)
    candidate_answer = Column(Text)
    ai_relevance_score = Column(Numeric(5, 2))
    ai_feedback = Column(Text)

# Initialize and Create Tables
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Database Integrated: All tables from SQL file created successfully.")
