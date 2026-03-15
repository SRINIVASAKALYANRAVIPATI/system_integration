from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging
import os
import base64
import cv2
import numpy as np
import time
from datetime import datetime
from typing import Dict, Any

# ─────────────────────────────────────────────
# Logging — must be first
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IntegratedSystem")

# ─────────────────────────────────────────────
# Module Imports
# ─────────────────────────────────────────────
try:
    from integrated_proctor import ProctorSystem
    from database_integration import (
        SessionLocal, InterviewSession,
        ObjectDetectionEvent, FacePoseEvent,
        AudioTranscript, AnswerEvaluation
    )
    from app.services.llm_evaluator import LLMEvaluator
    from app.schemas import EvaluationInput, ExperienceLevel, QuestionType
    logger.info("Core modules imported successfully.")
except ImportError as e:
    logger.error(f"Core import failed: {e}")

# Import Whisper STT from TTS folder
try:
    from live_stt_faster_whisper import FastSpeechToText
    logger.info("Whisper STT module imported successfully.")
    _whisper_available = True
except ImportError as e:
    logger.warning(f"Whisper STT not available: {e}")
    _whisper_available = False

# ─────────────────────────────────────────────
# Absolute Model Paths
# ─────────────────────────────────────────────
_THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR      = os.path.dirname(_THIS_DIR)
_SYS_INT       = os.path.join(_BASE_DIR, "System_Integration", "System_Integration")
YOLO_MODEL_ABS = os.path.join(_SYS_INT, "yolov8n.pt")
FACE_MODEL_ABS = os.path.join(_SYS_INT, "face_landmarker.task")

logger.info(f"YOLO model path : {YOLO_MODEL_ABS}  [exists={os.path.exists(YOLO_MODEL_ABS)}]")
logger.info(f"Face model path : {FACE_MODEL_ABS}  [exists={os.path.exists(FACE_MODEL_ABS)}]")

# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────
app = FastAPI(title="Integrated AI Interview System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Global Services
# ─────────────────────────────────────────────
evaluator = LLMEvaluator()

# Per-session risk accumulator
_session_risk: Dict[int, dict] = {}

# ─────────────────────────────────────────────
# DB Dependency
# ─────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "AI Interview Assessment System Orchestrator is running",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.post("/session/start")
async def start_session(user_id: int, db: Session = Depends(get_db)):
    """Starts a new interview session and records it in the database."""
    print("\n" + "="*60)
    print(f"[SESSION START] User ID: {user_id}  |  Time: {datetime.now().strftime('%H:%M:%S')}")

    try:
        new_session = InterviewSession(user_id=user_id, status="IN_PROGRESS")
        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        _session_risk[new_session.id] = {
            "risk": 0.0,
            "face_viols": 0,
            "eye_viols": 0,
            "phone_detections": 0,
            "frame_count": 0,
        }

        print(f"[DB] Session {new_session.id} created and saved.")
        print("="*60)
        return {"session_id": new_session.id, "status": "started"}

    except Exception as e:
        logger.error(f"Session start DB error: {e}")
        raise HTTPException(status_code=500, detail=f"Could not create session: {e}")

@app.websocket("/ws/proctor/{session_id}")
async def proctor_websocket(websocket: WebSocket, session_id: int):
    """WebSocket — receives camera frames, runs YOLO + MediaPipe, updates risk score live."""
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    session_proctor = None
    try:
        import integrated_proctor as _ip
        _ip.YOLO_MODEL_PATH = YOLO_MODEL_ABS
        _ip.MODEL_PATH      = FACE_MODEL_ABS
        session_proctor = ProctorSystem()
        print(f"\n[PROCTOR] Session {session_id} — AI monitoring active")
    except Exception as e:
        logger.error(f"ProctorSystem init failed: {e}")

    frame_count = 0
    DB_FLUSH_EVERY = 30
    if session_id not in _session_risk:
        _session_risk[session_id] = {"risk": 0.0, "face_viols": 0, "eye_viols": 0, "frame_count": 0}

    db = SessionLocal()
    try:
        while True:
            data = await websocket.receive_text()
            if not data: continue
            if data.startswith("data:image"): data = data.split(",")[1]
            img_bytes = base64.b64decode(data)
            nparr     = np.frombuffer(img_bytes, np.uint8)
            frame     = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if session_proctor is not None and frame is not None:
                session_proctor.process_frame(frame)
                risk_score  = float(session_proctor.session_risk_score)
                face_viols  = int(session_proctor.face_violations)
                eye_viols   = int(session_proctor.eye_violations)
                phone_flag  = bool(session_proctor.verified_phone_detected)
                p_count     = int(session_proctor.verified_person_count)
            else:
                risk_score, face_viols, eye_viols, phone_flag, p_count = 0.0, 0, 0, False, 1

            acc = _session_risk[session_id]
            prev_face = acc.get("face_viols", 0)
            prev_eye  = acc.get("eye_viols", 0)
            acc["risk"]        = risk_score
            acc["face_viols"]  = face_viols
            acc["eye_viols"]   = eye_viols
            acc["person_count"] = p_count
            acc["frame_count"] = frame_count

            # DB Logs (Gaze/Face)
            if face_viols > prev_face:
                try:
                    db.add(FacePoseEvent(session_id=session_id, event_type="NO_FACE_DETECTED", duration_ms=2000, severity_score=2))
                    db.commit()
                    print(f"[DB] Face violation saved for session {session_id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Error (Face): {e}")

            if eye_viols > prev_eye:
                try:
                    db.add(FacePoseEvent(session_id=session_id, event_type="EYE_GAZE_VIOLATION", duration_ms=2000, severity_score=1))
                    db.commit()
                    print(f"[DB] Gaze violation saved for session {session_id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Error (Gaze): {e}")

            now_ts = time.time()
            if phone_flag and (now_ts - acc.get("last_phone_log", 0) > 5): # 5s internal cooldown for DB
                acc["last_phone_log"] = now_ts
                try:
                    db.add(ObjectDetectionEvent(session_id=session_id, object_detected="PHONE_DETECTED", confidence_score=0.85))
                    db.commit()
                    print(f"!!! [DB] Phone detection saved for session {session_id} !!!")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Error (Phone): {e}")

            if p_count > 1 and (now_ts - acc.get("last_person_log", 0) > 5):
                acc["last_person_log"] = now_ts
                try:
                    db.add(ObjectDetectionEvent(session_id=session_id, object_detected="MULTIPLE_PERSONS", confidence_score=0.90))
                    db.commit()
                    print(f"[DB] Multiple Persons detection saved for session {session_id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Error (Person): {e}")

            frame_count += 1
            if frame_count % DB_FLUSH_EVERY == 0:
                s_row = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
                if s_row:
                    s_row.total_risk_score = risk_score
                    db.commit()

            await websocket.send_json({
                "risk_score": risk_score,
                "violations": {"face": face_viols, "eye": eye_viols},
                "phone_detected": phone_flag,
                "multiple_persons": p_count > 1,
                "person_count": p_count,
                "status": "active"
            })
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Proctoring loop error: {e}")
    finally:
        db.close()

@app.post("/session/{session_id}/proctor/event")
async def log_proctor_event(
    session_id: int,
    event_type: str,
    data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Logs proctoring violations/events from the frontend (e.g. Tab Switch)."""
    try:
        if event_type in ["TAB_SWITCH", "WINDOW_BLUR"]:
            event = FacePoseEvent(
                session_id=session_id,
                event_type=event_type,
                duration_ms=data.get("duration_ms", 0),
                severity_score=data.get("severity", 2)
            )
            db.add(event)
        
        # Increment risk score in DB
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            increment = float(data.get("risk_increment", 0.1))
            session.total_risk_score = float(session.total_risk_score or 0) + increment
            db.commit()
            print(f"[DB] Frontend event '{event_type}' logged | Risk +{increment}")
            
    except Exception as e:
        logger.error(f"Manual event log failed: {e}")

    return {"status": "event_logged"}

@app.post("/session/{session_id}/evaluate")
async def evaluate_answer(
    session_id: int, question_id: str, question_text: str, answer_text: str,
    exp_level: str = "intermediate", db: Session = Depends(get_db)
):
    try:
        # AGGREGATION LOGIC: If incoming answer is short, pull everything from AudioTranscript table
        final_answer = answer_text
        if len(answer_text.split()) < 5:
            all_stt = db.query(AudioTranscript).filter(AudioTranscript.session_id == session_id).order_by(AudioTranscript.start_timestamp.asc()).all()
            if all_stt:
                aggregated = " ".join([t.text_content for t in all_stt])
                if len(aggregated.split()) > len(answer_text.split()):
                    final_answer = aggregated
                    logger.info(f"[EVAL] Using aggregated transcript ({len(all_stt)} blocks) for Session {session_id}")

        eval_input = EvaluationInput(
            question=question_text, candidate_answer=final_answer, expected_keywords=[],
            experience_level=ExperienceLevel(exp_level.lower()), question_type=QuestionType.TECHNICAL,
            interview_id=str(session_id)
        )
        evaluation = evaluator.evaluate_answer(eval_input)

        # Save eval to DB
        db_eval = AnswerEvaluation(
            session_id=session_id, question_id=question_id, candidate_answer=final_answer,
            ai_relevance_score=evaluation.scores.final_score,
            ai_feedback=f"{evaluation.feedback} | Score: {evaluation.scores.final_score:.1f}"
        )
        db.add(db_eval)
        db.commit()

        return {"score": evaluation.scores.final_score, "feedback": evaluation.feedback, "anti_cheat": evaluation.anti_cheat.dict()}
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/stt/{session_id}")
async def stt_websocket(websocket: WebSocket, session_id: int):
    await websocket.accept()
    logger.info(f"[STT WS] Connected for session {session_id}")
    db = SessionLocal()

    if not hasattr(stt_websocket, "_wmodel") and _whisper_available:
        from faster_whisper import WhisperModel
        try:
            stt_websocket._wmodel = WhisperModel("small", device="cpu", compute_type="int8")
        except Exception as mle:
            logger.error(f"STT Model Load Error: {mle}")

    try:
        while True:
            # Receive message (could be binary audio or JSON text)
            try:
                message = await websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    logger.info(f"[STT WS] Client disconnected for session {session_id}")
                    break

                transcript_text = ""
                
                if "bytes" in message:
                    # Whisper Binary Path
                    audio_bytes = message["bytes"]
                    if not audio_bytes or len(audio_bytes) < 100: continue
                    chunk_start = datetime.now()
                    
                    if _whisper_available and hasattr(stt_websocket, "_wmodel"):
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                            tmp.write(audio_bytes)
                            tmp_path = tmp.name
                        segments, _ = stt_websocket._wmodel.transcribe(tmp_path, beam_size=1)
                        transcript_text = " ".join(s.text.strip() for s in segments).strip()
                        os.remove(tmp_path)
                    
                    if transcript_text:
                        await websocket.send_json({"transcript": transcript_text, "session_id": session_id})

                elif "text" in message:
                    # Chrome Native Text Path
                    import json
                    json_data = json.loads(message["text"])
                    transcript_text = json_data.get("text", "").strip()
                
                # ── SAVE TO DB ──
                if transcript_text:
                    current_p_count = _session_risk.get(session_id, {}).get("person_count", 1)
                    is_multi = (current_p_count > 1)
                    
                    try:
                        db.add(AudioTranscript(
                            session_id=session_id, 
                            start_timestamp=datetime.now(), 
                            end_timestamp=datetime.now(),
                            text_content=transcript_text, 
                            is_multiple_speakers=is_multi
                        ))
                        db.commit()
                        print(f"[DB] CAPTION SAVED: {transcript_text[:40]}... (Multi: {is_multi})")
                    except Exception as db_err:
                        logger.error(f"DB Save Error: {db_err}")
                        db.rollback()

            except Exception as e:
                logger.error(f"[STT] Inner loop error: {e}")
                break # Exit loop on unexpected errors to prevent crash loops

    except WebSocketDisconnect:
        logger.info(f"[STT WS] Disconnected for session {session_id}")
    finally:
        db.close()

@app.post("/session/{session_id}/end")
async def end_session(session_id: int, status: str = "COMPLETED", db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    
    final_risk = float(_session_risk.get(session_id, {}).get("risk", session.total_risk_score or 0.0))
    session.end_time = datetime.now()
    session.status = status # Use provided status from frontend
    session.total_risk_score = final_risk
    
    db.commit()
    _session_risk.pop(session_id, None)
    return {"status": status, "session_id": session_id, "final_risk_score": final_risk}

@app.get("/session/{session_id}/report")
async def get_session_report(session_id: int, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    evals = db.query(AnswerEvaluation).filter(AnswerEvaluation.session_id == session_id).all()
    transcripts = db.query(AudioTranscript).filter(AudioTranscript.session_id == session_id).all()
    pose_events = db.query(FacePoseEvent).filter(FacePoseEvent.session_id == session_id).all()
    obj_events = db.query(ObjectDetectionEvent).filter(ObjectDetectionEvent.session_id == session_id).all()

    return {
        "session": {
            "id": session.id, "user_id": session.user_id, "final_risk_score": float(session.total_risk_score or 0),
            "status": session.status,
            "integrity_summary": {
                "face_violations": len(pose_events), "object_detections": len(obj_events),
                "phone_detected": any(o.object_detected == "PHONE_DETECTED" for o in obj_events),
                "multiple_persons": any(o.object_detected == "MULTIPLE_PERSONS" for o in obj_events)
            }
        },
        "evaluations": [{"question_id": e.question_id, "answer": e.candidate_answer, "score": float(e.ai_relevance_score or 0)} for e in evals],
        "transcripts": [{"text": t.text_content, "time": str(t.start_timestamp)} for t in transcripts],
        "violations": {"face_pose": [p.event_type for p in pose_events], "objects": [o.object_detected for o in obj_events]}
    }

if __name__ == "__main__":
    from database_integration import engine, Base
    Base.metadata.create_all(bind=engine)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
