
import subprocess
import time
import os
import sys
import signal

# --- CONFIG ---
BASE_DIR = os.getcwd()
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend-UI-Ai-and-Interview-assessment--master", "frontend-UI-Ai-and-Interview-assessment--master")
BACKEND_DIR = os.path.join(BASE_DIR, "Integration_Final")
AUTH_SERVER_DIR = os.path.join(FRONTEND_DIR, "server")

def start_process(cmd, cwd, name):
    print(f"[*] Starting {name}...")
    return subprocess.Popen(cmd, cwd=cwd, shell=True)

def run_full_stack():
    # 1. Start FastAPI Orchestrator (Backend AI)
    # We must set PYTHONPATH for FastAPI
    env = os.environ.copy()
    python_path = [
        BASE_DIR,
        os.path.join(BASE_DIR, "System_Integration"),
        os.path.join(BASE_DIR, "System_Integration", "System_Integration"),
        os.path.join(BASE_DIR, "Database-Integration-For-AI-Interview-System-main (2)", "Database-Integration-For-AI-Interview-System-main"),
        os.path.join(BASE_DIR, "intern1", "intern", "gpt-llm-module"),
        os.path.join(BASE_DIR, "TTS"),   # Whisper STT module
    ]
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    env["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY_HERE"
    env["USE_MOCK_MODE"] = "false"

    # Kill existing node processes
    subprocess.run("taskkill /F /IM node.exe /T", shell=True,
                   stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    # Fast port-free using netstat (avoids long PowerShell hang)
    def free_port(port):
        try:
            result = subprocess.run(
                f"netstat -ano | findstr :{port}",
                shell=True, capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    pid = parts[-1]
                    subprocess.run(f"taskkill /F /PID {pid}",
                                   shell=True, stderr=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL)
        except Exception:
            pass  # Port already free or timeout — safe to ignore

    free_port(8000)
    free_port(5000)
    time.sleep(1)

    processes = []
    
    def log_watcher(proc, prefix):
        for line in iter(proc.stdout.readline, b''):
            try:
                print(f"{prefix} {line.decode('utf-8', errors='replace').strip()}")
            except Exception:
                pass

    import threading

    # A. FastAPI — use list args + shell=False to handle spaces in Python path
    print("[*] Starting AI Backend on :8000...")
    fastapi_args = [
        sys.executable, "-m", "uvicorn",
        "orchestrator:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info"
    ]
    p_api = subprocess.Popen(
        fastapi_args,
        cwd=BACKEND_DIR,
        env=env,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    threading.Thread(target=log_watcher, args=(p_api, "[API]"), daemon=True).start()
    processes.append(p_api)
    
    # B. Auth Server (Node Express)
    print("[*] Starting Auth Server on :5000...")
    p_auth = subprocess.Popen("node index.js", cwd=AUTH_SERVER_DIR, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=log_watcher, args=(p_auth, "[AUTH]"), daemon=True).start()
    processes.append(p_auth)
    
    # C. Frontend (Vite)
    print("[*] Starting Frontend on :5173...")
    # Disable Vite's screen clear so it doesn't wipe our API/AUTH logs
    p_vite = subprocess.Popen("npm run dev -- --clearScreen false", cwd=FRONTEND_DIR, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=log_watcher, args=(p_vite, "[UI]"), daemon=True).start()
    processes.append(p_vite)

    print("\n" + "="*50)
    print("AI INTERVIEW ASSESSMENT SYSTEM IS STARTING")
    print("="*50)
    print("- Frontend (UI): http://localhost:5173")
    print("- AI Backend:    http://localhost:8000")
    print("- Auth Server:   http://localhost:5000")
    print("="*50)

    try:
        dead = set()
        while True:
            time.sleep(2)
            for i, p in enumerate(processes):
                if i in dead:
                    continue
                if p.poll() is not None:
                    names = ["API", "AUTH", "UI"]
                    print(f"\n[!] {names[i]} service stopped (exit code: {p.returncode}). Check [{names[i]}] logs above.")
                    dead.add(i)
                    if names[i] == "UI":
                        return  # Frontend stopping is fatal
    except KeyboardInterrupt:
        print("\nShutting down services...")
        for p in processes:
            subprocess.run(f"taskkill /F /PID {p.pid} /T", shell=True, stderr=subprocess.DEVNULL)
        print("Done.")

if __name__ == "__main__":
    run_full_stack()
