
import cv2
import os
import mediapipe as mp
import time

from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

def test_mediapipe():
    print("Initializing MediaPipe Task API...")
    MODEL_PATH = os.path.join("System_Integration", "System_Integration", "face_landmarker.task")
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
        num_faces=1
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)
    
    print("Opening Camera...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return False
    
    print("Camera opened. Capturing 5 frames...")
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            print(f"Error reading frame {i}")
            break
        
        # Process frame
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        detection_result = landmarker.detect(mp_image)
        
        if detection_result.face_landmarks:
            print(f"Frame {i}: Face landmarks detected!")
        else:
            print(f"Frame {i}: Face not detected.")
        
        time.sleep(0.5)

    cap.release()
    print("Test complete.")
    return True

if __name__ == "__main__":
    test_mediapipe()
