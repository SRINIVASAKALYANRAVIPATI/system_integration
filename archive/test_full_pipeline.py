"""
=============================================================
AI Interview System - Full Pipeline Test
=============================================================
Modules tested:
  1. Database Connection & Mock Data Seeding
  2. Object Detection (YOLO v8)
  3. Face/Pose Tracking (OpenCV + MediaPipe)
  4. GPT/LLM Answer Evaluation (Mock or Live)
  5. Speech Transcript Storage
  6. Risk Score Aggregation
  7. End-to-End Session Flow (Start -> Q1 -> Q2 -> Q3 -> End)
=============================================================
"""

import os
import sys
import time
import traceback
from datetime import datetime

# ── Path Setup ────────────────────────────────────────────────────────────────
BASE = r"C:\Users\OM SRIKAR\Downloads\INTEGRATION"
PATHS = [
    BASE,
    os.path.join(BASE, "System_Integration", "System_Integration"),
    os.path.join(BASE, "Database-Integration-For-AI-Interview-System-main (2)",
                 "Database-Integration-For-AI-Interview-System-main"),
    os.path.join(BASE, "intern1", "intern", "gpt-llm-module"),
]
for p in PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── ASCII-Safe Terminal Helpers ──────────────────────────────────────────────
SEP  = "=" * 65
LINE = "-" * 65

def banner(title):
    print("\n" + SEP)
    print("  " + title)
    print(SEP)

def section(title):
    print("\n" + LINE)
    print("  >> " + title)
    print(LINE)

def ok(msg):   print("  [OK]   " + str(msg))
def warn(msg): print("  [WARN] " + str(msg))
def err(msg):  print("  [ERR]  " + str(msg))
def info(msg): print("  [->]   " + str(msg))

# ──────────────────────────────────────────────────────────────────────────────
# MODULE 1 — DATABASE
# ──────────────────────────────────────────────────────────────────────────────
banner("MODULE 1 -- DATABASE CONNECTION & MOCK DATA")

db_ok = False
db = None
test_user = None
mock_session = None
SessionLocal = User = InterviewSession = AnswerEvaluation = None
AudioTranscript = FacePoseEvent = ObjectDetectionEvent = None

try:
    from database_integration import (
        SessionLocal, engine, Base,
        User, InterviewSession, AnswerEvaluation,
        AudioTranscript, FacePoseEvent, ObjectDetectionEvent
    )
    Base.metadata.create_all(bind=engine)
    ok("SQLAlchemy engine connected. All tables verified/created.")

    db = SessionLocal()

    # Seed mock user
    test_user = db.query(User).filter(User.email == "testcandidate@ai.com").first()
    if not test_user:
        import bcrypt
        pw = bcrypt.hashpw(b"test1234", bcrypt.gensalt()).decode()
        test_user = User(
            username="test_candidate",
            email="testcandidate@ai.com",
            password_hash=pw,
            full_name="Test Candidate"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        ok("Mock user CREATED -> ID: {} | Email: testcandidate@ai.com | Pass: test1234".format(test_user.id))
    else:
        ok("Mock user already exists -> ID: {}".format(test_user.id))

    # Create a fresh IN_PROGRESS session
    mock_session = InterviewSession(user_id=test_user.id, status="IN_PROGRESS")
    db.add(mock_session)
    db.commit()
    db.refresh(mock_session)
    ok("Mock interview session created -> Session ID: {}".format(mock_session.id))
    info("Session started at: {}".format(mock_session.start_time))
    db_ok = True

except Exception as e:
    err("Database failed: {}".format(e))
    warn("Running in MOCK (no-DB) mode. Values will be logged but NOT persisted.")
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────────────────────
# MODULE 2 — YOLO OBJECT DETECTION
# ──────────────────────────────────────────────────────────────────────────────
banner("MODULE 2 -- YOLO v8 OBJECT DETECTION")

yolo_ok = False
person_count_yolo = 0
phone_detected_yolo = False

try:
    from ultralytics import YOLO
    import numpy as np
    import cv2

    yolo_path = os.path.join(BASE, "yolov8n.pt")
    model = YOLO(yolo_path)
    ok("YOLO model loaded from: {}".format(yolo_path))

    # Synthetic blank frame (640x480 black = empty room)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = model(test_frame, imgsz=640, conf=0.2, classes=[0, 67], verbose=False)

    for r in results:
        for box in r.boxes:
            cls  = int(box.cls[0])
            conf = float(box.conf[0])
            if cls == 0:
                person_count_yolo += 1
                info("Person detected -- conf: {:.2f}".format(conf))
            elif cls == 67:
                phone_detected_yolo = True
                warn("!!! Phone detected -- conf: {:.2f}".format(conf))

    ok("YOLO inference done -> Persons: {} | Phone: {}".format(person_count_yolo, phone_detected_yolo))
    yolo_ok = True

    if db_ok and phone_detected_yolo:
        ev = ObjectDetectionEvent(
            session_id=mock_session.id,
            object_detected="PHONE_DETECTED",
            confidence_score=0.85
        )
        db.add(ev)
        db.commit()
        ok("Phone-detection event saved to DB.")

except Exception as e:
    err("YOLO module failed: {}".format(e))
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────────────────────
# MODULE 3 — OPENCV / MEDIAPIPE PROCTORING
# ──────────────────────────────────────────────────────────────────────────────
banner("MODULE 3 -- OPENCV FACE & POSE TRACKING (MediaPipe)")

opencv_ok = False
proctor = None

try:
    import cv2
    import numpy as np
    ok("OpenCV version: {}".format(cv2.__version__))

    import integrated_proctor as ip
    ip.YOLO_MODEL_PATH = os.path.join(BASE, "System_Integration", "System_Integration", "yolov8n.pt")
    ip.MODEL_PATH      = os.path.join(BASE, "System_Integration", "System_Integration", "face_landmarker.task")

    proctor = ip.ProctorSystem()
    ok("ProctorSystem (MediaPipe + YOLO) initialised.")

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    proctor.process_frame(blank)

    info("Face violations : {}".format(proctor.face_violations))
    info("Eye violations  : {}".format(proctor.eye_violations))
    info("Session risk    : {:.3f}".format(proctor.session_risk_score))
    info("Phone detected  : {}".format(proctor.phone_detected))
    ok("Frame proctoring pipeline executed successfully.")
    opencv_ok = True

    if db_ok and proctor.face_violations > 0:
        fe = FacePoseEvent(
            session_id=mock_session.id,
            event_type="NO_FACE_DETECTED",
            duration_ms=500,
            severity_score=1
        )
        db.add(fe)
        db.commit()
        ok("Face-pose event written to DB.")

except Exception as e:
    err("OpenCV/ProctorSystem failed: {}".format(e))
    warn("Check that face_landmarker.task exists in System_Integration/System_Integration/")
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────────────────────
# MODULE 4 — GPT / LLM ANSWER EVALUATION
# ──────────────────────────────────────────────────────────────────────────────
banner("MODULE 4 -- GPT / LLM ANSWER EVALUATION")

# Mock interview questions (3-question set)
QUESTIONS = [
    {
        "id": "q1",
        "text": "What is the difference between a list and a tuple in Python?",
        "keywords": ["mutable", "immutable", "list", "tuple", "performance"],
        "type": "technical"
    },
    {
        "id": "q2",
        "text": "Explain the concept of Object-Oriented Programming.",
        "keywords": ["class", "object", "inheritance", "encapsulation", "polymorphism"],
        "type": "technical"
    },
    {
        "id": "q3",
        "text": "Describe a time you resolved a conflict within your team.",
        "keywords": ["communication", "conflict", "resolution", "team", "collaboration"],
        "type": "behavioral"
    }
]

# These simulate what Whisper would transcribe from the candidate's microphone
MOCK_SPEECH_ANSWERS = [
    "A list is mutable, meaning you can change its elements after creation. "
    "A tuple is immutable, so once created it can't be changed. "
    "Tuples are generally faster and use less memory.",

    "Object-Oriented Programming is a paradigm based on the concept of objects. "
    "It involves classes, inheritance where child classes inherit from parent classes, "
    "encapsulation to hide internal state, and polymorphism to allow different types to be used interchangeably.",

    "In my last project, two team members disagreed on the architecture approach. "
    "I facilitated a meeting where each person explained their reasoning. "
    "We evaluated both options against requirements and made a collaborative decision. "
    "The conflict was resolved through open communication and mutual respect."
]

llm_ok = False
evaluations = []

try:
    from app.services.llm_evaluator import LLMEvaluator
    from app.schemas import EvaluationInput, ExperienceLevel, QuestionType
    from app.config import USE_MOCK_MODE, OPENAI_API_KEY

    evaluator = LLMEvaluator()
    ok("LLMEvaluator module loaded.")

    if not OPENAI_API_KEY or USE_MOCK_MODE:
        warn("No OPENAI_API_KEY -> running MOCK evaluation (scores are simulated, not real GPT).")
    else:
        ok("OpenAI API key detected -> using live GPT-4o-mini.")

    qtype_map = {
        "technical":  QuestionType.TECHNICAL,
        "behavioral": QuestionType.BEHAVIORAL
    }

    for i, (q, answer) in enumerate(zip(QUESTIONS, MOCK_SPEECH_ANSWERS)):

        section("Q{}: {}".format(i + 1, q["text"]))

        # Simulate Whisper speech-to-text output
        print()
        print("  [WHISPER TRANSCRIPT]")
        print("  \"{}\"".format(answer))

        eval_input = EvaluationInput(
            question=q["text"],
            candidate_answer=answer,
            expected_keywords=q["keywords"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            question_type=qtype_map.get(q["type"], QuestionType.TECHNICAL),
            interview_id=str(mock_session.id) if db_ok else "mock_{}".format(i)
        )

        result = evaluator.evaluate_answer(eval_input)
        evaluations.append(result)

        print()
        print("  [GPT EVALUATION RESULT]")
        print("  +--------------------------------------------------")
        print("  | Score         : {:.1f} / 10".format(result.scores.final_score))
        print("  | Technical     : {:.1f}".format(result.scores.technical_accuracy))
        print("  | Clarity       : {:.1f}".format(result.scores.concept_clarity))
        print("  | Keywords      : {:.1f}".format(result.scores.keyword_coverage))
        print("  | Communication : {:.1f}".format(result.scores.communication))
        print("  | Anti-cheat    : AI-Gen={} | CopyPaste={}".format(
            result.anti_cheat.is_ai_generated, result.anti_cheat.is_copy_paste))
        feedback_preview = result.feedback[:140].replace("\n", " ")
        print("  | Feedback      : {}...".format(feedback_preview))
        print("  +--------------------------------------------------")

        # Persist to database
        if db_ok:
            transcript = AudioTranscript(
                session_id=mock_session.id,
                start_timestamp=datetime.now(),
                end_timestamp=datetime.now(),
                text_content=answer,
                is_multiple_speakers=False
            )
            db.add(transcript)

            eval_record = AnswerEvaluation(
                session_id=mock_session.id,
                question_id=q["id"],
                candidate_answer=answer,
                ai_relevance_score=result.scores.final_score,
                ai_feedback=result.feedback
            )
            db.add(eval_record)
            db.commit()
            ok("Q{} evaluation + transcript saved to DB.".format(i + 1))

        time.sleep(0.3)

    llm_ok = True

except Exception as e:
    err("LLM module failed: {}".format(e))
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────────────────────
# MODULE 5 — RISK AGGREGATION & SESSION CLOSE
# ──────────────────────────────────────────────────────────────────────────────
banner("MODULE 5 -- RISK SCORE AGGREGATION & SESSION CLOSE")

risk_ok = False
try:
    if evaluations:
        avg_score = sum(e.scores.final_score for e in evaluations) / len(evaluations)
        cheating_flags = sum(
            1 for e in evaluations
            if e.anti_cheat.is_copy_paste or e.anti_cheat.is_ai_generated
        )
    else:
        avg_score = 5.0
        cheating_flags = 0

    proctor_risk = float(proctor.session_risk_score) if opencv_ok and proctor else 0.0

    # Risk formula: LLM quality accounts for 40%, visual proctoring for 60%
    combined_risk = round((1.0 - (avg_score / 10.0)) * 0.4 + proctor_risk * 0.6, 3)
    risk_label = "LOW" if combined_risk < 0.3 else "MEDIUM" if combined_risk < 0.6 else "HIGH"

    print()
    print("  +-------------- FINAL SESSION REPORT ---------------+")
    print("  | Session ID          : {}".format(mock_session.id if db_ok else "MOCK"))
    print("  | Candidate           : {}".format(test_user.full_name if db_ok else "Test Candidate"))
    print("  | Questions answered  : {}/{}".format(len(evaluations), len(QUESTIONS)))
    print("  | Average LLM Score   : {:.2f} / 10".format(avg_score))
    print("  | Anti-cheat flags    : {}".format(cheating_flags))
    print("  | YOLO Persons        : {}".format(person_count_yolo))
    print("  | Visual Proctor Risk : {:.3f}".format(proctor_risk))
    print("  +----------------------------------------------------+")
    print("  | COMBINED RISK SCORE : {:.3f}".format(combined_risk))
    print("  | INTEGRITY VERDICT   : {} RISK".format(risk_label))
    print("  +----------------------------------------------------+")

    if db_ok:
        mock_session.end_time = datetime.now()
        mock_session.status = "COMPLETED"
        mock_session.total_risk_score = combined_risk
        db.commit()
        ok("Session {} marked COMPLETED in database.".format(mock_session.id))
        ok("Risk score {:.3f} persisted.".format(combined_risk))

    risk_ok = True

except Exception as e:
    err("Risk aggregation failed: {}".format(e))
    traceback.print_exc()

# ──────────────────────────────────────────────────────────────────────────────
# FINAL HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────
banner("PIPELINE HEALTH CHECK SUMMARY")

checks = [
    ("1. Database (PostgreSQL)",    db_ok),
    ("2. YOLO Object Detection",   yolo_ok),
    ("3. OpenCV / MediaPipe",      opencv_ok),
    ("4. GPT / LLM Evaluation",    llm_ok),
    ("5. Risk Aggregation",        risk_ok),
]

all_pass = True
for name, status in checks:
    tag = "[PASS]" if status else "[FAIL]"
    print("  {}  {}".format(tag, name))
    if not status:
        all_pass = False

print()
if all_pass:
    print("  >>> ALL MODULES OPERATIONAL - System ready for live interviews!")
else:
    print("  [!] Some modules need attention. Fix the [FAIL] items above.")

print()
print("  NOTE: These diagnostic print statements can be removed before production.")
print()

if db_ok and db:
    db.close()
