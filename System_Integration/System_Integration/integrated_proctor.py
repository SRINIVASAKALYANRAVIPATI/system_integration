import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import base64
import os
from ultralytics import YOLO
from queue import Queue
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import Counter

# ---------------- CONFIG ----------------
SMOOTHING = 0.5          # Ultra-responsive eye tracking
EYE_DEADZONE = 1.0       # Tightened deadzone
EYE_THRESHOLD = 2.5      # Aggressive gaze detection

MAX_FACE_VIOLATIONS = 10
MAX_EYE_VIOLATIONS = 15

FACE_COOLDOWN = 15.0
EYE_COOLDOWN = 15.0
MULTI_PERSON_COOLDOWN = 20.0
GLOBAL_ALERT_COOLDOWN = 15.0         
CONTINUOUS_VIOLATION_THRESHOLD = 3.5  # Faster response (3.5s)
MULTI_PERSON_THRESHOLD = 3.0         

# Auto-detect Absolute Paths
THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))

# YOLO Config (Maximum Performance)
YOLO_MODEL_PATH = os.path.join(THIS_FILE_DIR, "yolov8n.pt")
TARGET_CLASSES = [0, 65, 67] # 0:Person, 65:Remote, 67:Phone
YOLO_CONFIDENCE = 0.03       # Absolute floor for detection
YOLO_SKIP_FRAMES = 1         # Process EVERY frame

# Mediapipe Tasks Config
MODEL_PATH = os.path.join(THIS_FILE_DIR, "face_landmarker.task")

# Indices
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]
NOSE_TIP = 1

class AlertManager:
    def __init__(self, backend_url=None):
        self.backend_url = backend_url
        self.alert_queue = Queue()
        self.worker_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.worker_thread.start()

    def send_alert(self, violation_type, frame, data=None):
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        alert_payload = {
            "type": violation_type,
            "timestamp": time.time(),
            "data": data or {},
            "image": img_base64[:50] + "..."
        }
        self.alert_queue.put(alert_payload)

    def _process_alerts(self):
        while True:
            alert = self.alert_queue.get()
            print(f"[ALERT] {alert['type']} at {time.ctime(alert['timestamp'])}")
            self.alert_queue.task_done()

class ProctorSystem:
    def __init__(self):
        self.model = YOLO(YOLO_MODEL_PATH)
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.alert_manager = AlertManager()
        
        # Core State
        self.face_violations = 0
        self.eye_violations = 0
        self.session_risk_score = 0
        self.last_face_time = 0
        self.last_eye_time = 0
        self.prev_left_iris = None
        self.prev_right_iris = None
        self.prev_face_dir = "Face: CENTER"
        self.prev_eye_dir = "Eyes: CENTER"
        self.person_count = 0
        self.verified_person_count = 1
        self.phone_detected = False
        self.verified_phone_detected = False
        self.frame_count = 0
        
        # Professional Persistence Timers
        self.face_gone_start = None
        self.face_turn_start = None
        self.eye_gaze_start = None
        self.multi_person_start = None
        self.phone_start_time = None
        
        self.last_global_alert_time = 0
        self.last_phone_alert_time = 0
        self.last_person_alert_time = 0
        
        # YOLO Boxes for Debug
        self.yolo_boxes = []

    def get_head_direction(self, landmarks, frame_shape):
        h, w = frame_shape[:2]
        nose = landmarks[NOSE_TIP]
        left_face = landmarks[234]
        right_face = landmarks[454]
        offset = (nose.x - (left_face.x + right_face.x) / 2) * w
        if offset > w * 0.04: return "Face: RIGHT"
        elif offset < -w * 0.04: return "Face: LEFT"
        nose_y = nose.y * h
        center_y = (landmarks[152].y + landmarks[10].y) * h / 2
        v_offset = nose_y - center_y
        if v_offset > h * 0.03: return "Face: DOWN"
        elif v_offset < -h * 0.03: return "Face: UP"
        return "Face: CENTER"

    def get_eye_direction(self, iris_center, eye_points):
        eye_center = np.mean(eye_points, axis=0)
        dx, dy = iris_center - eye_center
        if abs(dx) < EYE_DEADZONE and abs(dy) < EYE_DEADZONE: return "Eyes: CENTER"
        if abs(dx) > abs(dy):
            if dx > EYE_THRESHOLD: return "Eyes: RIGHT"
            elif dx < -EYE_THRESHOLD: return "Eyes: LEFT"
        else:
            if dy > EYE_THRESHOLD: return "Eyes: DOWN"
            elif dy < -EYE_THRESHOLD: return "Eyes: UP"
        return "Eyes: CENTER"

    def process_frame(self, frame):
        self.frame_count += 1
        h, w = frame.shape[:2]
        now = time.time()

        # 1. YOLO DETECTION (Every Frame Scanning)
        yolo_results = self.model(frame, imgsz=640, conf=0.03, device='cpu', classes=TARGET_CLASSES, verbose=False)
        raw_person_count = 0
        raw_phone_detected = False
        self.yolo_boxes = []
        
        for r in yolo_results:
            for box in r.boxes:
                coords = box.xyxy[0].tolist() 
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                label = self.model.names[cls]
                
                # VERBOSE DEBUG: Print detection candidates to terminal
                if conf > 0.05:
                    print(f"[YOLO DEBUG] Frame {self.frame_count}: Found {label} ({conf:.2f})", flush=True)

                if cls == 0 and conf > 0.35:
                    raw_person_count += 1
                    self.yolo_boxes.append({'coords': coords, 'label': f"Person {raw_person_count}", 'color': (0, 255, 0)})
                elif (cls == 67 or cls == 65) and conf > 0.05: # Phone or Remote
                    raw_phone_detected = True
                    self.yolo_boxes.append({'coords': coords, 'label': f"PHONE!! ({conf:.2f})", 'color': (0, 0, 255)})

        # Person Count Logic
        self.person_count = raw_person_count
        if self.person_count > 1:
            if self.multi_person_start is None: self.multi_person_start = now
            elif (now - self.multi_person_start) > MULTI_PERSON_THRESHOLD:
                self.verified_person_count = self.person_count
                if now - self.last_person_alert_time > 10.0:
                    self.alert_manager.send_alert("MULTIPLE_PERSONS", frame, {"count": self.person_count})
                    self.session_risk_score += 2
                    self.last_person_alert_time = now
                    self.multi_person_start = None 
        else:
            self.multi_person_start = None
            self.verified_person_count = max(1, self.person_count)

        # Phone Verification (INSTANT)
        if raw_phone_detected:
            if not self.verified_phone_detected:
                print(f"!!! [AI CRITICAL] PHONE VERIFIED: {time.ctime(now)} !!!", flush=True)
            self.verified_phone_detected = True
            
            if now - self.last_phone_alert_time > 10.0:
                self.alert_manager.send_alert("PHONE_DETECTED", frame)
                self.session_risk_score += 5
                self.last_phone_alert_time = now
        else:
            if self.verified_phone_detected:
                print(f"--- [AI] Phone cleared at {time.ctime(now)} ---", flush=True)
            self.verified_phone_detected = False

        # 2. FACE LANDMARK DETECTION
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        detection_result = self.landmarker.detect(mp_image)

        current_face_dir = "Face: CENTER"
        current_eye_dir = "Eyes: CENTER"

        if not detection_result.face_landmarks:
            if self.face_gone_start is None: self.face_gone_start = now
            elif (now - self.face_gone_start) > CONTINUOUS_VIOLATION_THRESHOLD:
                if now - self.last_global_alert_time > GLOBAL_ALERT_COOLDOWN:
                    self.face_violations += 1; self.last_face_time = now
                    self.last_global_alert_time = now
                    self.alert_manager.send_alert("NO_FACE_DETECTED", frame)
                    self.face_gone_start = None
            self.face_turn_start = self.eye_gaze_start = None
        else:
            self.face_gone_start = None
            face_landmarks = detection_result.face_landmarks[0]
            def pts(idxs): return np.array([[int(face_landmarks[i].x * w), int(face_landmarks[i].y * h)] for i in idxs])
            landmarks_px = {"l_eye": pts(LEFT_EYE), "r_eye": pts(RIGHT_EYE), "l_iris": pts(LEFT_IRIS), "r_iris": pts(RIGHT_IRIS)}
            
            current_face_dir = self.get_head_direction(face_landmarks, frame.shape)
            raw_left = np.mean(landmarks_px["l_iris"], axis=0)
            raw_right = np.mean(landmarks_px["r_iris"], axis=0)

            if self.prev_left_iris is None: self.prev_left_iris, self.prev_right_iris = raw_left, raw_right
            left_iris = SMOOTHING * self.prev_left_iris + (1 - SMOOTHING) * raw_left
            right_iris = SMOOTHING * self.prev_right_iris + (1 - SMOOTHING) * raw_right
            self.prev_left_iris, self.prev_right_iris = left_iris, right_iris

            l_dir = self.get_eye_direction(left_iris, landmarks_px["l_eye"])
            r_dir = self.get_eye_direction(right_iris, landmarks_px["r_eye"])
            
            if l_dir != "Eyes: CENTER": current_eye_dir = l_dir
            elif r_dir != "Eyes: CENTER": current_eye_dir = r_dir
            else: current_eye_dir = "Eyes: CENTER"

            # Head Violation
            if current_face_dir != "Face: CENTER":
                if self.face_turn_start is None: self.face_turn_start = now
                elif (now - self.face_turn_start) > CONTINUOUS_VIOLATION_THRESHOLD:
                    if now - self.last_global_alert_time > GLOBAL_ALERT_COOLDOWN:
                        self.face_violations += 1; self.last_face_time = now
                        self.last_global_alert_time = now
                        self.alert_manager.send_alert("HEAD_DIRECTION_VIOLATION", frame, {"dir": current_face_dir})
                        self.face_turn_start = None
            else: self.face_turn_start = None

            # Eye Violation
            if current_eye_dir != "Eyes: CENTER":
                if self.eye_gaze_start is None: self.eye_gaze_start = now
                elif (now - self.eye_gaze_start) > CONTINUOUS_VIOLATION_THRESHOLD:
                    if now - self.last_global_alert_time > GLOBAL_ALERT_COOLDOWN:
                        self.eye_violations += 1; self.last_eye_time = now
                        self.last_global_alert_time = now
                        self.alert_manager.send_alert("EYE_GAZE_VIOLATION", frame, {"dir": current_eye_dir})
                        self.eye_gaze_start = None
            else: self.eye_gaze_start = None

        # Draw YOLO Boxes
        for obj in self.yolo_boxes:
            x1, y1, x2, y2 = map(int, obj['coords'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), obj['color'], 2)
            cv2.putText(frame, obj['label'], (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, obj['color'], 2)

        return self.draw_hud(frame, current_face_dir, current_eye_dir)

    def draw_hud(self, frame, face_dir, eye_dir):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (320, 250), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
        now = time.time()
        max_out = max(
            (now - self.face_gone_start) if self.face_gone_start else 0,
            (now - self.face_turn_start) if self.face_turn_start else 0,
            (now - self.eye_gaze_start) if self.eye_gaze_start else 0
        )
        info = [
            (face_dir, (0, 255, 255)), (eye_dir, (0, 255, 0)),
            (f"Away Timer: {max_out:.1f}s", (0, 0, 255) if max_out > 2.0 else (255, 255, 255)),
            (f"Persons: {self.verified_person_count}", (255, 255, 255)),
            (f"Phone: {'YES' if self.verified_phone_detected else 'NO'}", (0, 0, 255) if self.verified_phone_detected else (0, 255, 0)),
            (f"Total Risk: {int(self.session_risk_score)}", (0, 165, 255)),
            (f"Violations (H/E): {self.face_violations}/{self.eye_violations}", (200, 200, 200))
        ]
        for i, (text, color) in enumerate(info):
            cv2.putText(frame, text, (10, 30 + i * 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return frame

def run_proctor():
    proctor = ProctorSystem()
    cap = cv2.VideoCapture(0)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        processed_frame = proctor.process_frame(frame)
        cv2.imshow("AI Proctoring System - Professional Mode", processed_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    run_proctor()
