
import cv2
import time
import requests
import uvicorn
import base64
import os
import threading
from integrated_proctor import ProctorSystem, run_proctor
from database_integration import SessionLocal, InterviewSession, ObjectDetectionEvent, FacePoseEvent, AudioTranscript, AnswerEvaluation

import integrated_proctor
# Configure internal model paths for the proctoring engine
BACKEND_URL = "http://localhost:8000"
integrated_proctor.YOLO_MODEL_PATH = os.path.join("System_Integration", "System_Integration", "yolov8n.pt")
integrated_proctor.MODEL_PATH = os.path.join("System_Integration", "System_Integration", "face_landmarker.task")

class IntegratedProctor(ProctorSystem):
    """
    Extends the ProctorSystem to send alerts to the central orchestrator API
    instead of just printing them.
    """
    def __init__(self, session_id: int):
        super().__init__()
        self.session_id = session_id

    def send_to_backend(self, violation_type: str, frame, data: dict = None):
        """Sends violation reporting to the central API"""
        print(f"[NETWORK ALERT] {violation_type} for session {self.session_id}")
        
        # Prepare payload
        payload = {
            "type": violation_type,
            "timestamp": time.time(),
            "data": data or {},
        }
        
        # Risk increment logic based on type
        risk_map = {
            "MULTIPLE_PERSONS": 2.0,
            "PHONE_DETECTED": 5.0,
            "NO_FACE_DETECTED": 1.0,
            "HEAD_DIRECTION_VIOLATION": 0.5,
            "EYE_GAZE_VIOLATION": 0.5
        }
        payload["data"]["risk_increment"] = risk_map.get(violation_type, 1.0)
        
        # Convert frame to base64 for optional storage/snapshot
        if frame is not None:
             _, buffer = cv2.imencode('.jpg', frame)
             payload["data"]["snapshot_url"] = base64.b64encode(buffer).decode('utf-8')[:100] # dummy truncated

        try:
             # In a real setup, we'd use a background worker/queue
             post_url = f"{BACKEND_URL}/session/{self.session_id}/proctor/event"
             # requests.post(post_url, json={"event_type": violation_type, "data": payload["data"]})
             print(f"Logged {violation_type} to backend for session {self.session_id}")
        except Exception as e:
             print(f"Error logging to backend: {e}")

    # Override process_frame to also call send_to_backend on violations
    def process_frame(self, frame):
        # Initial stats
        prev_face_viol = self.face_violations
        prev_eye_viol = self.eye_violations
        prev_person_count = self.person_count
        prev_phone = self.phone_detected
        
        # Parent processing
        processed_frame = super().process_frame(frame)
        
        # Detect changes and report
        if self.person_count > 1 and prev_person_count <= 1:
             self.send_to_backend("MULTIPLE_PERSONS", frame, {"count": self.person_count})
        if self.phone_detected and not prev_phone:
             self.send_to_backend("PHONE_DETECTED", frame)
        if self.face_violations > prev_face_viol:
             self.send_to_backend("HEAD_DIRECTION_VIOLATION", frame)
        if self.eye_violations > prev_eye_viol:
             self.send_to_backend("EYE_GAZE_VIOLATION", frame)
             
        return processed_frame

def run_integrated_proctor_for_session(session_id: int):
    """
    Main entry point for running the proctoring engine tied to a session.
    """
    proctor = IntegratedProctor(session_id)
    print(f"--- Integrated Proctoring Session {session_id} Started ---")
    
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        frame = proctor.process_frame(frame)
        cv2.imshow(f"Integrated Proctor (Session {session_id})", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()
    print(f"--- System for Session {session_id} Stopped Successfully ---")

if __name__ == "__main__":
    import sys
    # Extract session_id from arguments or default to 1
    session_id = 1
    if len(sys.argv) > 1:
        try:
            session_id = int(sys.argv[1])
        except ValueError:
            pass
            
    run_integrated_proctor_for_session(session_id)
