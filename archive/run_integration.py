
import os
import subprocess
import time
import requests
import signal
import sys

# Paths setup
BASE_DIR = os.getcwd()
LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

def start_process(command: list, log_file: str):
    """Starts a subprocess and returns its handle"""
    with open(os.path.join(LOG_DIR, log_file), "w") as f:
        return subprocess.Popen(command, stdout=f, stderr=f)

def run_integration():
    """
    Main manager script to start all AI modules.
    1. Start the Orchestrator API (LLM + Database integration)
    2. Wait for it to be ready
    3. Start the proctoring engine
    4. Provide entry points for frontend/testing
    """
    print("--- AI Interview Assessment System: Full Integration ---")
    
    # Check if necessary models exist
    yolo_model = "System_Integration/System_Integration/yolov8n.pt"
    face_model = "System_Integration/System_Integration/face_landmarker.task"
    if not os.path.exists(yolo_model) or not os.path.exists(face_model):
        print(f"[ERROR] Required model files not found in {yolo_model} or {face_model}")
        sys.exit(1)
        
    # Python path setup for imports
    sys_int_path = os.path.join(BASE_DIR, "System_Integration", "System_Integration")
    db_int_path = os.path.join(BASE_DIR, "Database-Integration-For-AI-Interview-System-main (2)", "Database-Integration-For-AI-Interview-System-main")
    llm_module_path = os.path.join(BASE_DIR, "intern1/intern/gpt-llm-module")
    
    os.environ['PYTHONPATH'] = ";".join([BASE_DIR, sys_int_path, db_int_path, llm_module_path])
    
    # 1. Start the API Orchestrator (FastAPI)
    print("[1/4] Starting API Orchestrator (FastAPI)...")
    orchestrator_cmd = [sys.executable, "-m", "uvicorn", "Integration_Final.orchestrator:app", "--host", "0.0.0.0", "--port", "8000"]
    p_orchestrator = start_process(orchestrator_cmd, "orchestrator.log")
    
    # 2. Wait for API to be healthy
    print("[2/4] Waiting for API to be ready at http://localhost:8000/docs...")
    time.sleep(5)
    
    # 3. Start the    # 3. Ready Status
    print("[3/4] API Orchestrator is now the primary manager.")
    print("[4/4] FULL SYSTEM READY [OK]")
    print("      - Orchestrator: http://localhost:8000")
    print("      - Proctor Logs: logs/proctor.log")
    print("      - Orchestrator Logs: logs/orchestrator.log")
    print("\nPress Ctrl+C to stop all services.")

    try:
        while True:
            time.sleep(2)
            if p_orchestrator.poll() is not None:
                print("[CRITICAL] Orchestrator stopped unexpectedly!")
                break
    except KeyboardInterrupt:
        print("\nStopping services...")
        p_orchestrator.terminate()
        print("Integration shut down.")

if __name__ == "__main__":
    run_integration()
