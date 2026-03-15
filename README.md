# AI Interview Assessment System 🚀

An end-to-end AI-powered interview and assessment platform designed to automate technical interviews while ensuring high integrity through real-time proctoring. The system features a modern web interface, an AI orchestrator for question evaluation and speech-to-text, and real-time video streaming analysis for anti-cheat monitoring.

## 🌟 Key Features

* **Real-time AI Proctoring**: Uses YOLOv8 and MediaPipe to detect multiple people, mobile phones, head direction violations, and eye gaze anomalies.
* **Live Speech-to-Text (STT)**: Transcribes the candidate's spoken answers in real-time using Whisper models.
* **Intelligent Evaluation**: Evaluates candidate answers against expectations using LLMs (OpenAI Integration) and assigns a score and constructive feedback.
* **Anti-Cheat Browser Tracking**: Detects tab switching, window blurring, and other suspicious browser activities.
* **Comprehensive Dashboard**: Displays the live video feed, real-time STT transcripts, current questions, and dynamic risk warnings to the candidate.
* **Secure Authentication**: JWT-based user authentication system with strict password policies.

---

## 🏗️ Architecture & Tech Stack

This project is a distributed system consisting of three main components:

### 1. Frontend (UI)
* **Framework**: React 18 with Vite
* **Styling**: Tailwind CSS & Lucide Icons
* **Features**: Live camera feed processing, WebSocket integrations for STT and Proctoring, Markdown rendering for AI feedback.
* **Location**: `/frontend-UI-Ai-and-Interview-assessment--master/`

### 2. Auth Server (Express Backend)
* **Framework**: Node.js & Express
* **Database**: PostgreSQL (pg library)
* **Security**: bcrypt.js for password hashing, JWT for session tokens.
* **Features**: User registration, login, profile retrieval, and strict password validation.
* **Location**: `/frontend-UI-Ai-and-Interview-assessment--master/server/`

### 3. AI Assessment Backend (Orchestrator)
* **Framework**: FastAPI (Python)
* **Database Mapping**: SQLAlchemy
* **AI Models**: YOLOv8 (Object Detection), MediaPipe (Face Landmarker), Faster-Whisper (STT), OpenAI GPT (Evaluation).
* **Location**: `/Integration_Final/orchestrator.py`

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed on your machine:
* **Node.js**: v18.0 or later
* **Python**: v3.10 or later
* **PostgreSQL**: v14.0 or later (Running locally on default port 5432)
* **Create a PostgreSQL Database**: Make sure you have a default DB running. The system will create its own database named `interview_db`.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd INTEGRATION_checkpoint
```

### 2. Database Initialization
Ensure your local PostgreSQL server is running.
The password for the system is configured as `postgres`. If yours is different, update `init_db.py`, `check_db.py`, and the `server/.env` file.

Run the DB initialization script to create the necessary database and tables:
```bash
python init_db.py
python check_db.py  # To verify the connection
```

### 3. Frontend Setup
Navigate to the frontend directory and install dependencies:
```bash
cd frontend-UI-Ai-and-Interview-assessment--master/frontend-UI-Ai-and-Interview-assessment--master
npm install
```

### 4. Auth Server Setup
Navigate to the Node Express server directory and install dependencies:
```bash
cd server
npm install
```
Configure your `.env` file in the `server` directory:
```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=interview_db
JWT_SECRET=ai_interview_super_secret_jwt_key_2024
PORT=5000
```

### 5. AI Python Backend Setup
Install the required python packages (a virtual environment is recommended):
```bash
pip install -r Database-Integration-For-AI-Interview-System-main (2)/Database-Integration-For-AI-Interview-System-main/requirements.txt
# Additional packages might be required based on orchestrator imports:
pip install fastapi uvicorn sqlalchemy psycopg2-binary opencv-python numpy faster-whisper
```
Make sure the YOLO model (`yolov8n.pt`) and Face Landmarker task (`face_landmarker.task`) are placed correctly in the `System_Integration\System_Integration` directory.

---

## 🚀 Running the Application

A convenience script is provided to spin up all three servers (Frontend, Auth API, and FastAPI Orchestrator) simultaneously.

From the root project directory, run:
```powershell
python run_full_stack.py
```

**What this script does:**
1. Kills any dangling Node/Python processes on the required ports (8000, 5000, 5173).
2. Starts the **AI Backend** on `http://localhost:8000`.
3. Starts the **Node Auth Server** on `http://localhost:5000`.
4. Starts the **React Frontend** on `http://localhost:5173`.
5. Pipes all logs to the terminal with clear `[API]`, `[AUTH]`, and `[UI]` prefixes.

Open your browser and navigate to `http://localhost:5173` to access the application.

---

## 🛡️ Security & Integrity Logic

### Password Policies
New users must register with a password that meets the following criteria:
* 8 to 12 characters long.
* At least one uppercase letter.
* At least one lowercase letter.
* At least one number.
* At least one special symbol.

### Proctoring Violations
The system will automatically log and act upon the following violations:
1. **Gaze/Face Violations**: Looking away from the screen or no face detected.
2. **Object Violations**: Detection of mobile phones or multiple people in the frame.
3. **Browser Violations**: Switching tabs or minimizing the browser window.

If a candidate reaches **3 violations**, the interview is immediately terminated by the system, and a final risk report is registered in the database.

---

## 🐞 Troubleshooting

* **WebSocket Disconnects**: If you see STT WebSocket errors, ensure your microphone permissions are granted in the browser.
* **Database Connection Failed**: Ensure the PostgreSQL service is running and the username/password in `DATABASE_URL` (in `database_integration.py` and `check_db.py`) match your local setup.
* **Port Conflicts**: If the servers fail to start, `run_full_stack.py` will attempt to kill processes on ports 5000, 8000, and 5173. You can also manually terminate them if they hang.

### Project Contributors

**AI/ML Team**
* **Task 1: YOLOv8** (Detect phone, extra person, and other objects)
  * Abdul
  * Sudarshana
  * Jeevan
* **Task 2: OpenCV** (Capture face movement and pose tracking)
  * Karlyn
  * Shreeya
  * Pearl
  * Rishikeshwar
* **Task 3: Speech-to-Text Translation** (Whisper module for real-time transcription)
  * Omsrikar
* **Task 4: GPT/LLM Integration** (Score interview answers)
  * Dhwanil
  * Jaineel

**Frontend Team**
* **Task 1: React/HTML/CSS & WebRTC** (Create assessment UI and enable mic/camera browser streaming)
  * Harsh
  * Rahul
  * Valarmathi

**Backend Team**
* **Task 1: FastAPI (Python)** (Handle AI pipeline and scoring system)
  * Omsrikar
  * Srinivasa Kalyan

**Database and Storage Team**
* **Task 1: PostgreSQL** (Store results and user data)
  * Kush Soni
  * Sarthaki
  * Chitranjan

**Deployment and Integration Team**
* **Task 1: Integration** (Integrate all modules together)
  * Satyam
  * Gowthamkumar
  * Saksham
  * Srinivasa Kalyan
* **Task 2: Deployment** (Deploy project using Docker and AWS)
  * Shaikh Mohammad Faizal
  * Kush Soni
