# 🚀 AI Interview Proctoring & Evaluation System

### **Database Integration Layer**
[cite_start]This repository features a robust **Python-based database integration** for an automated interview proctoring system. [cite_start]It bridges the gap between raw **PostgreSQL** data and application logic, specifically designed to monitor candidate behavior and evaluate interview performance using AI.

---

## 🛠️ Tech Stack
* **Language:** Python 3.x
* [cite_start]**ORM:** SQLAlchemy (Object Relational Mapper) 
* [cite_start]**Database:** PostgreSQL 
* [cite_start]**Drivers:** Psycopg2-binary 

---

## 📊 Database Schema
The project maps the following entities as defined in the PostgreSQL structure:

| Table | Purpose |
| :--- | :--- |
| **`users`** | [cite_start]Manages candidate profiles and authentication data. |
| **`interview_sessions`** | [cite_start]Central hub tracking status, timing, and cumulative risk scores. |
| **`object_detection_events`** | [cite_start]Logs AI-detected items (e.g., cell phones) with confidence levels. |
| **`face_pose_events`** | [cite_start]Tracks suspicious physical behavior and severity levels. |
| **`audio_transcripts`** | [cite_start]Stores text content and timestamps for candidate responses. |
| **`answer_evaluations`** | [cite_start]Links answers to AI-generated relevance scores and feedback. |



