# 🤖 LEO — AI-Powered Elderly Care Assistant

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-7.x-47A248?style=for-the-badge&logo=mongodb&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Real--time-FF6F00?style=for-the-badge&logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Final Year Project — BS(Hons) Computer Science**
**GC University Lahore | 2024–2025**

*An intelligent home assistant system designed to ensure the safety, health, and independence of elderly individuals through AI-powered monitoring, real-time fall detection, and smart health management.*

</div>

---

## 📌 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
- [How It Works](#-how-it-works)
- [Team](#-team)

---

## 🧠 Overview

LEO is a full-stack AI home assistant for elderly care, combining computer vision, natural language AI, and real-time health monitoring into a unified system. It is designed for deployment in a home environment where an elderly person lives — optionally alone — and a caregiver or family member needs remote visibility and emergency alerting.

The system runs across three interfaces simultaneously:
- A **Flutter mobile/web app** for caregivers and family
- A **CustomTkinter desktop GUI** (`leo_app.py`) for local on-premise control
- A **Flask web dashboard** for live monitoring

All interfaces connect to a shared **FastAPI + MongoDB backend** with JWT-authenticated role-based access control.

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     LEO SYSTEM                          │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐  ┌─────────────┐  │
│  │ Flutter App  │   │  Desktop GUI │  │  Dashboard  │  │
│  │ (Mobile/Web) │   │  leo_app.py  │  │  Flask :5000│  │
│  └──────┬───────┘   └──────┬───────┘  └──────┬──────┘  │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                            │
│              ┌─────────────▼──────────────┐             │
│              │   FastAPI Backend :8000     │             │
│              │   (JWT Auth, REST API)      │             │
│              └─────────────┬──────────────┘             │
│                            │                            │
│         ┌──────────────────┼──────────────────┐         │
│         │                  │                  │         │
│  ┌──────▼──────┐  ┌────────▼───────┐  ┌──────▼──────┐  │
│  │  MongoDB    │  │  YOLO Fall     │  │  Kokoro TTS │  │
│  │  7 Collections│  │  Detection    │  │  Audio      │  │
│  └─────────────┘  └────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 🚨 Real-Time Fall Detection
- Dual YOLO model pipeline (fall detection + posture classification)
- Weighted multi-signal scoring algorithm
- Optical flow analysis for motion context
- Safe-zone detection for bed/sofa (prevents false positives)
- Automatic emergency alerts on confirmed fall events

### 💊 Health & Medication Management
- Medication schedules with reminder system
- Health vitals tracking (heart rate, blood pressure, etc.)
- Historical health data visualization
- Doctor/caregiver notification pipeline

### 🤖 AI Chat Assistant
- Integrated conversational AI for elderly user interaction
- Voice output via Kokoro ONNX text-to-speech
- Natural language health queries and reminders

### 📱 Flutter Mobile App
- 12 screens including live YOLO video feed
- Emergency alert management
- Real-time status via nested StreamBuilder architecture
- Platform-conditional imports (Android/iOS/Web)

### 🔐 Secure Backend
- JWT authentication with role-based access control
- 7 MongoDB collections (users, medications, health_records, alerts, devices, caregivers, logs)
- RESTful API with full CRUD operations
- Uvicorn ASGI server with hot reload

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI, Uvicorn, Python 3.10+ |
| Database | MongoDB 7.x, PyMongo |
| Authentication | JWT (python-jose), bcrypt |
| Mobile/Web Frontend | Flutter 3.x, Dart |
| Desktop GUI | CustomTkinter |
| Web Dashboard | Flask |
| Computer Vision | YOLOv8, OpenCV, Optical Flow |
| Text-to-Speech | Kokoro ONNX |
| System Launcher | Python subprocess orchestration |

---

## 📁 Project Structure

```
LEO/
├── start_leo.py                    # One-click system launcher
├── stop_leo.bat                    # Graceful shutdown script
│
├── FYP_Backend/                    # Core backend
│   ├── main.py                     # FastAPI app & all routes
│   ├── leo_app.py                  # CustomTkinter desktop GUI
│   ├── dashboard.py                # Flask live dashboard
│   ├── final_monitering_brain.py   # YOLO fall detection engine
│   ├── audio.py                    # TTS with Kokoro ONNX
│   ├── models/                     # YOLO model weights (.pt files)
│   └── requirements.txt            # Python dependencies
│
└── FYP_Frontent/                   # Flutter mobile/web app
    ├── lib/
    │   ├── main.dart
    │   ├── screens/                # 12 app screens
    │   ├── services/               # API service layer
    │   └── widgets/                # Reusable UI components
    ├── pubspec.yaml
    └── ...
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.10+
- Flutter 3.x SDK
- MongoDB 7.x (running locally or Atlas URI)
- CUDA-capable GPU recommended (for real-time YOLO inference)

### 1. Clone the repository

```bash
git clone https://github.com/MuhammadHunzlaKhalid/LEO.git
cd LEO
```

### 2. Backend Setup

```bash
cd FYP_Backend
pip install -r requirements.txt
```

Create a `.env` file in `FYP_Backend/`:

```env
MONGO_URI=mongodb://localhost:27017
DB_NAME=leo_db
JWT_SECRET=your_secret_key_here
JWT_ALGORITHM=HS256
```

### 3. Flutter Setup

```bash
cd FYP_Frontent
flutter pub get
```

Update the API base URL in `lib/services/api_service.dart`:
```dart
const String baseUrl = 'http://127.0.0.1:8000';
```

### 4. Launch the System

```bash
# From root LEO directory
python start_leo.py
```

This will automatically start:
1. MongoDB (background)
2. FastAPI Backend (new terminal window, port 8000)
3. Flask Dashboard (background, port 5000)
4. LEO Desktop App (GUI window)
5. Flutter Web App (Chrome, ~30s)

### 5. Manual Start (individual services)

```bash
# Backend only
cd FYP_Backend
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Flutter only
cd FYP_Frontent
flutter run -d chrome

# Desktop GUI only
cd FYP_Backend
python leo_app.py
```

---

## 🔍 How It Works

### Fall Detection Pipeline (`final_monitering_brain.py`)

```
Camera Feed
    │
    ▼
YOLO Fall Model ──→ Fall Score (weighted)
    │
    ▼
YOLO Posture Model ──→ Posture Classification
    │                   (standing/sitting/lying)
    ▼
Optical Flow ──→ Motion Score
    │
    ▼
Multi-Signal Weighted Scoring Algorithm
    │
    ├── Score < Threshold → Normal (continue)
    │
    └── Score ≥ Threshold → FALL DETECTED
                │
                ├── Safe Zone Check (bed/sofa)
                │   └── Yes → Suppress alert (safe lying)
                │
                └── No Safe Zone → EMERGENCY ALERT
                        │
                        ├── TTS Audio Warning
                        ├── MongoDB Alert Record
                        └── Flutter Push Notification
```

### API Endpoints (FastAPI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | JWT login |
| POST | `/auth/register` | User registration |
| GET | `/health/records` | Get health records |
| POST | `/medications/add` | Add medication |
| GET | `/alerts/active` | Get active alerts |
| POST | `/alerts/resolve` | Resolve alert |
| GET | `/monitoring/status` | Live monitoring status |
| WS | `/monitoring/stream` | WebSocket live feed |

---

## 👨‍💻 Team

| Name | Role |
|------|------|
| **Muhammad Hunzla Khalid** | Backend, Computer Vision, Desktop GUI, System Integration |
| **Ayesha Abaidullah** | Flutter Frontend, UI/UX |
| **Shaiq Bhatti** | Research, Documentation, Testing |

**Supervisor:** Dr. Zia Ul Rehman
**Institution:** GC University Lahore
**Degree:** BS(Hons) Computer Science
**Year:** 2024–2025

---

## 📄 License

This project is developed as an academic Final Year Project at GC University Lahore.
MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
<i>Built with ❤️ for elderly care — because every life deserves dignity and safety.</i>
</div>
