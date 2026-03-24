import cv2
import os
from ultralytics import YOLO

# Detect path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(THIS_DIR, "System_Integration", "System_Integration", "yolov8n.pt")

print(f"Loading YOLO model from: {MODEL_PATH}")
if not os.path.exists(MODEL_PATH):
    print("ERROR: Model not found!")
    exit(1)

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(0)

print("Starting Camera... Press 'q' to quit.")
while cap.isOpened():
    ret, frame = cap.read()
    if not ret: break
    
    # Run YOLO on CPU for stability + sensitive confidence for phones
    results = model(frame, imgsz=640, conf=0.15, device='cpu', classes=[0, 67], verbose=False)
    
    # Draw detections
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            label = "Phone" if cls == 67 else "Person"
            color = (0, 0, 255) if cls == 67 else (0, 255, 0)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imshow("Check YOLO (Phone/Person)", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")
