"""
LEO — AI Home Assistant for the Elderly
FastAPI Backend
FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman

Endpoints:
  POST /chat                    → Main conversation with LEO
  GET  /user/{name}/profile     → Fetch user profile
  PUT  /user/{name}/profile     → Update user profile
  GET  /user/{name}/logs        → Get today's activity logs
  GET  /user/{name}/memory      → Get recent conversation history
  DELETE /user/{name}/memory    → Clear conversation memory
  POST /user/{name}/medications → Add / update medication schedule
  GET  /medications/{name}/due  → Get medications due right now
  POST /emergency/alert         → Trigger emergency alert manually
  GET  /health                  → Health check
  
  ── Fall Detection (monitoring brain) ──
  POST /vision/analyze-frame    → Analyze base64 image frame for fall
  GET  /vision/status           → Current fall detection state
  POST /vision/zones            → Save safe zones (bed / sofa)
  GET  /vision/zones            → Get saved zones
"""

from __future__ import annotations

import os
import json
import time
import base64
import warnings
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch

warnings.filterwarnings("ignore")
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
ZONES_FILE = BASE_DIR / "safe_zones.json"

LEO_MODEL_PATH = Path("D:/Python/FYP/models/qwen")
FALL_MODEL_PATH = (
    "D:\\Python\\FYP\\Trained Datasets\\"
    "GPT_fyp_train_dataset_fall_v2.1\\runs_backup\\detect\\"
    "runs\\train\\fall_stage1\\weights\\best.pt"
)
POSTURE_MODEL_PATH = (
    "D:\\Python\\FYP\\Trained Datasets\\"
    "GPT_fyp_train_dataset_lying1_posture_v2.1\\runs_backup\\detect\\"
    "runs\\train\\siting_stage1\\weights\\best.pt"
)

# ── New FYP modules ───────────────────────────
import sys as _sys
_sys.path.insert(0, str(BASE_DIR))
from patient_storage import PatientDirs
from mongo_storage   import leo_db


# ═══════════════════════════════════════════════════════════════════
# IMPORT FYP MODULES
# ═══════════════════════════════════════════════════════════════════

try:
    from audio import (
        UserProfile, ConversationMemory, ActivityLogger,
        IntentMatcher, EmergencyHandler, MedicationHandler,
        EmotionHandler, ContactHandler, LeoBrain
    )
    LEO_BRAIN_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Could not import Leo modules: {e}")
    LEO_BRAIN_AVAILABLE = False

# YOLO fall detection (lazy-loaded to avoid startup crash if models missing)
fall_model    = None
posture_model = None
YOLO_AVAILABLE = False

try:
    from ultralytics import YOLO
    fall_model    = YOLO(FALL_MODEL_PATH).to("cuda" if torch.cuda.is_available() else "cpu")
    posture_model = YOLO(POSTURE_MODEL_PATH).to("cuda" if torch.cuda.is_available() else "cpu")
    YOLO_AVAILABLE = True
    print("[OK] YOLO fall/posture models loaded.")
except Exception as e:
    print(f"[WARNING] YOLO models not loaded: {e}")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL STATE  (singleton Leo brain + per-user instances)
# ═══════════════════════════════════════════════════════════════════
_brain: Optional["LeoBrain"] = None
_brain_lock = threading.Lock()

# Per-user component cache  {username → {profile, memory, logger, ...}}
_user_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()


def _get_brain() -> "LeoBrain":
    global _brain
    if _brain is None and LEO_BRAIN_AVAILABLE:
        with _brain_lock:
            if _brain is None:
                _brain = LeoBrain(LEO_MODEL_PATH)
    return _brain


def _get_user_components(username: str) -> dict:
    username = username.lower().strip()
    with _cache_lock:
        if username not in _user_cache:
            profile_obj = UserProfile(username) if LEO_BRAIN_AVAILABLE else None
            # Save to MongoDB on first load
            if profile_obj and leo_db.connected:
                leo_db.save_patient(profile_obj.data)
            _user_cache[username] = {
                "profile":   profile_obj,
                "memory":    ConversationMemory(username) if LEO_BRAIN_AVAILABLE else None,
                "logger":    ActivityLogger(username) if LEO_BRAIN_AVAILABLE else None,
                "matcher":   IntentMatcher() if LEO_BRAIN_AVAILABLE else None,
                "emergency": EmergencyHandler() if LEO_BRAIN_AVAILABLE else None,
                "meds":      MedicationHandler() if LEO_BRAIN_AVAILABLE else None,
                "emotion":   EmotionHandler() if LEO_BRAIN_AVAILABLE else None,
                "contact":   ContactHandler() if LEO_BRAIN_AVAILABLE else None,
            }
    return _user_cache[username]


# ═══════════════════════════════════════════════════════════════════
# PYDANTIC  SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    username: str = Field(..., example="ahmed")
    message: str  = Field(..., example="Hello Leo, how are you?")

class ChatResponse(BaseModel):
    username: str
    message: str
    reply: str
    intent: Optional[str] = None
    timestamp: str

class ProfileUpdate(BaseModel):
    personal:           Optional[dict] = None
    emergency_contacts: Optional[list] = None
    contacts:           Optional[list] = None
    medications:        Optional[list] = None
    routine:            Optional[dict] = None
    preferences:        Optional[dict] = None

class MedicationItem(BaseModel):
    medicine: str
    time: str          # "HH:MM"
    quantity_left: Optional[str] = None
    notes: Optional[str] = None

class EmergencyAlertRequest(BaseModel):
    username: str
    level: str = Field(..., example="critical")   # critical | fall | confusion
    message: Optional[str] = None

class FrameAnalysisRequest(BaseModel):
    frame_b64: str   # base64-encoded JPEG/PNG frame
    username: Optional[str] = "unknown"

class ZoneItem(BaseModel):
    type: str          # "bed" | "sofa"
    box: list[int]     # [x1, y1, x2, y2]

class ZonesPayload(BaseModel):
    zones: list[ZoneItem]

class FallStatusResponse(BaseModel):
    state: str
    fall_detected: bool
    on_safe_zone: bool
    posture: str
    confidence: float
    timestamp: str


# ═══════════════════════════════════════════════════════════════════
# FALL DETECTION STATE  (updated by /vision/analyze-frame)
# ═══════════════════════════════════════════════════════════════════
_fall_state = {
    "state":         "UNKNOWN",
    "fall_detected": False,
    "on_safe_zone":  False,
    "posture":       "unknown",
    "confidence":    0.0,
    "timestamp":     datetime.now().isoformat(),
}
_fall_lock = threading.Lock()

# Safe zones (loaded from disk on startup)
def _load_zones() -> list[dict]:
    if not ZONES_FILE.exists():
        return []
    try:
        with open(ZONES_FILE) as f:
            data = json.load(f)
        return [{"type": d["type"], "box": tuple(d["box"])} for d in data]
    except Exception:
        return []

def _save_zones(zones: list[dict]):
    data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
    with open(ZONES_FILE, "w") as f:
        json.dump(data, f, indent=2)

_safe_zones: list[dict] = _load_zones()


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════
def _point_in_zone(cx: float, cy: float, zones: list[dict]) -> Optional[dict]:
    for z in zones:
        x1, y1, x2, y2 = z["box"]
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return z
    return None

def _person_in_safe_zone(box, zones: list[dict]) -> bool:
    if box is None or not zones:
        return False
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return _point_in_zone(cx, cy, zones) is not None

def _get_aspect_ratio(box) -> float:
    x1, y1, x2, y2 = box
    return max(y2 - y1, 1) / max(x2 - x1, 1)

def _route_intent(text: str, components: dict, username: str) -> tuple[str, str]:
    """
    Mirror of Leo._route() but returns (intent_label, response_text).
    """
    matcher   = components["matcher"]
    profile   = components["profile"]
    memory    = components["memory"]
    emergency = components["emergency"]
    meds      = components["meds"]
    emotion_h = components["emotion"]
    contact_h = components["contact"]
    brain     = _get_brain()

    t = text.strip()

    if matcher.is_greeting(t):
        hour = datetime.now().hour
        g = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
        return "greeting", f"{g}, {profile.name}! How are you feeling today?"

    if matcher.is_memory_question(t):
        recent = memory.recent_user_messages(3)
        if not recent:
            return "memory", "We haven't talked much yet today. What's on your mind?"
        return "memory", "Earlier you mentioned: " + " ... ".join(recent)

    if "emergency contact" in t.lower() and any(w in t.lower() for w in ["show","list","who","what"]):
        return "contacts", contact_h.list_contacts(profile.emergency_contacts, emergency_only=True)

    emotion = matcher.detect_emotion(t)
    if emotion == "hopeless":
        resp = emergency.respond("critical", profile.name, profile.emergency_contacts)
        return "emergency_critical", resp
    if emotion:
        return f"emotion_{emotion}", emotion_h.respond(emotion, profile.name)

    level = matcher.detect_emergency_level(t)
    if level:
        resp = emergency.respond(level, profile.name, profile.emergency_contacts)
        return f"emergency_{level}", resp

    if matcher.is_medication(t):
        return "medication", meds.respond(t, profile.medications)

    if matcher.is_call_request(t):
        contact = contact_h.find(profile.all_contacts, t)
        if contact:
            return "call", (f"Calling your {contact.get('relation','contact')}, "
                           f"{contact['name']} ({contact.get('phone','')}) now...")
        if not profile.all_contacts:
            return "call", "You have no contacts saved. Please ask your caregiver to add some."
        names = ", ".join(c["name"] for c in profile.all_contacts)
        return "call", f"Who would you like to call? I have: {names}."

    if brain is None:
        return "llm_unavailable", "Leo's brain is not loaded. Please check the model path."

    reply = brain.chat(t, profile.data, memory.as_messages())
    return "llm", reply


# ═══════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════
app = FastAPI(
    title="LEO — AI Home Assistant API",
    description="FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "leo_brain_available": LEO_BRAIN_AVAILABLE,
        "yolo_available":      YOLO_AVAILABLE,
        "gpu":                 torch.cuda.is_available(),
        "gpu_name":            torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "timestamp":           datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest):
    """
    Send a message to LEO and get a response.
    Handles: greetings, emotions, emergencies, medications, memory, contacts, free chat.
    """
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules are not available. Check server logs.")

    username   = req.username.lower().strip()
    components = _get_user_components(username)

    intent, reply = _route_intent(req.message, components, username)

    # Persist to memory & logs
    components["memory"].add(req.message, reply)
    components["logger"].log("chat", f"User: {req.message} | Leo: {reply}")

    if leo_db.connected:
        leo_db.log_activity(username, "chat",
                            f"User: {req.message} | Leo: {reply}")

    return ChatResponse(
        username  = username,
        message   = req.message,
        reply     = reply,
        intent    = intent,
        timestamp = datetime.now().isoformat(),
    )


# ─────────────────────────────────────────────
# USER PROFILE
# ─────────────────────────────────────────────
@app.get("/user/{username}/profile", tags=["User"])
def get_profile(username: str):
    """Get the full user profile."""
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    return {"username": username, "profile": c["profile"].data}


@app.put("/user/{username}/profile", tags=["User"])
def update_profile(username: str, update: ProfileUpdate):
    """
    Update one or more sections of the user profile.
    Only supplied fields are overwritten.
    """
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    profile = c["profile"]

    for field, value in update.model_dump(exclude_none=True).items():
        if isinstance(value, dict):
            profile.data.setdefault(field, {}).update(value)
        else:
            profile.data[field] = value

    profile.save()
    return {"message": "Profile updated.", "profile": profile.data}


# ─────────────────────────────────────────────
# ACTIVITY LOGS
# ─────────────────────────────────────────────
@app.get("/user/{username}/logs", tags=["User"])
def get_logs(username: str, category: Optional[str] = None, severity: Optional[str] = None):
    """
    Return today's activity log.
    Optional filters: category (chat|emergency|medication|emotion|fall)
                      severity (info|warning|critical)
    """
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    entries = c["logger"].entries

    if category:
        entries = [e for e in entries if e["category"] == category]
    if severity:
        entries = [e for e in entries if e["severity"] == severity]

    return {"username": username, "date": datetime.now().strftime("%Y-%m-%d"), "logs": entries}


# ─────────────────────────────────────────────
# CONVERSATION MEMORY
# ─────────────────────────────────────────────
@app.get("/user/{username}/memory", tags=["User"])
def get_memory(username: str, last_n: int = 10):
    """Get the last N turns of conversation history."""
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    history = c["memory"].history
    return {"username": username, "history": history[-last_n * 2:]}


@app.delete("/user/{username}/memory", tags=["User"])
def clear_memory(username: str):
    """Clear the user's conversation memory."""
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    c["memory"].history = []
    c["memory"].save()
    return {"message": f"Memory cleared for {username}."}


# ─────────────────────────────────────────────
# MEDICATIONS
# ─────────────────────────────────────────────
@app.post("/user/{username}/medications", tags=["Medications"])
def set_medications(username: str, medications: list[MedicationItem]):
    """Replace the full medication schedule for a user."""
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c = _get_user_components(username)
    c["profile"].data["medications"] = [m.model_dump() for m in medications]
    c["profile"].save()
    return {"message": "Medications updated.", "medications": c["profile"].data["medications"]}


@app.get("/medications/{username}/due", tags=["Medications"])
def medications_due(username: str):
    """Return medications due within the current minute (HH:MM match)."""
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")
    c  = _get_user_components(username)
    now = datetime.now().strftime("%H:%M")
    due = [m for m in c["profile"].medications if m.get("time") == now]
    return {"username": username, "time": now, "due": due}


# ─────────────────────────────────────────────
# EMERGENCY
# ─────────────────────────────────────────────
@app.post("/emergency/alert", tags=["Emergency"])
def emergency_alert(req: EmergencyAlertRequest, background_tasks: BackgroundTasks):
    """
    Manually trigger an emergency alert.
    In production, wire this to Twilio / Firebase push notifications.
    Level: critical | fall | confusion
    """
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, "Leo modules not available.")

    c      = _get_user_components(req.username)
    handler = c["emergency"]
    profile = c["profile"]
    logger  = c["logger"]

    valid_levels = {"critical", "fall", "confusion"}
    if req.level not in valid_levels:
        raise HTTPException(400, f"level must be one of: {valid_levels}")

    response_text = handler.respond(req.level, profile.name, profile.emergency_contacts)
    logger.log("emergency", req.message or req.level, severity="critical")

    if leo_db.connected:
        leo_db.log_activity(req.username, "emergency",
                            req.message or req.level, severity="critical")
        if req.level == "fall":
            leo_db.log_fall(req.username, score=0,
                            reason=req.message or "manual alert", state="FALL")

    # TODO: background_tasks.add_task(send_twilio_sms, contacts, response_text)

    return {
        "username":  req.username,
        "level":     req.level,
        "message":   response_text,
        "contacts":  profile.emergency_contacts,
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# FALL DETECTION — Frame Analysis
# ─────────────────────────────────────────────
LYING_AR_THRESHOLD  = 1.2   # aspect ratio below this → horizontal / lying
FALL_CONF_THRESHOLD = 0.40  # minimum YOLO confidence to count detection

@app.post("/vision/analyze-frame", response_model=FallStatusResponse, tags=["Vision"])
def analyze_frame(req: FrameAnalysisRequest):
    """
    Accept a single base64-encoded camera frame.
    Run YOLO fall + posture detection and update the global fall state.
    Returns current state, posture, and fall flag.
    
    Frontend usage:
      - Call this every ~100 ms with the latest webcam frame (JPEG base64)
      - If fall_detected == true → show alert / call /emergency/alert
    """
    if not YOLO_AVAILABLE:
        raise HTTPException(503, "YOLO models not loaded.")

    # Decode frame
    try:
        img_bytes = base64.b64decode(req.frame_b64)
        nparr     = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("imdecode returned None")
    except Exception as e:
        raise HTTPException(400, f"Invalid image data: {e}")

    frame = cv2.resize(frame, (640, 480))
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ── Run YOLO models ──────────────────────────────
    fall_results    = fall_model(frame, verbose=False)
    posture_results = posture_model(frame, verbose=False)

    # Fall model detections
    fall_detected    = False
    fall_conf        = 0.0
    fall_box         = None

    for r in fall_results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf >= FALL_CONF_THRESHOLD:
                fall_detected = True
                fall_conf     = max(fall_conf, conf)
                fall_box      = [int(v) for v in box.xyxy[0].tolist()]

    # Posture model — dominant label
    posture_label = "unknown"
    posture_box   = None
    best_posture_conf = 0.0

    for r in posture_results:
        for box in r.boxes:
            conf  = float(box.conf[0])
            label = posture_model.names[int(box.cls[0])]
            if conf > best_posture_conf:
                best_posture_conf = conf
                posture_label     = label
                posture_box       = [int(v) for v in box.xyxy[0].tolist()]

    # Aspect-ratio lying heuristic
    if posture_box:
        ar = _get_aspect_ratio(posture_box)
        if ar < LYING_AR_THRESHOLD and posture_label not in ("lying", "fall"):
            posture_label = "lying"

    # Safe zone check (suppress fall if on bed/sofa)
    on_safe_zone = _person_in_safe_zone(fall_box or posture_box, _safe_zones)
    if on_safe_zone:
        fall_detected = False

    # Determine display state
    if fall_detected:
        state = "FALL"
    elif posture_label == "lying":
        state = "LYING (SAFE)" if not on_safe_zone else "LYING (ON SAFE ZONE)"
    elif posture_label == "standing":
        state = "STANDING"
    elif posture_label == "sitting":
        state = "SITTING"
    else:
        state = "UNKNOWN"

    result = FallStatusResponse(
        state        = state,
        fall_detected= fall_detected,
        on_safe_zone = on_safe_zone,
        posture      = posture_label,
        confidence   = round(fall_conf, 3),
        timestamp    = datetime.now().isoformat(),
    )

    # Update global state
    with _fall_lock:
        _fall_state.update(result.model_dump())

    # Auto-log if fall
    if fall_detected and req.username and LEO_BRAIN_AVAILABLE:
        try:
            c = _get_user_components(req.username)
            c["logger"].log("fall", f"Fall detected via vision — conf: {fall_conf:.2f}", severity="critical")
        except Exception:
            pass

    return result


@app.get("/vision/status", response_model=FallStatusResponse, tags=["Vision"])
def vision_status():
    """Get the most recent fall detection state (from last analyzed frame)."""
    with _fall_lock:
        return FallStatusResponse(**_fall_state)


# ─────────────────────────────────────────────
# SAFE ZONES
# ─────────────────────────────────────────────
@app.post("/vision/zones", tags=["Vision"])
def set_zones(payload: ZonesPayload):
    """Save bed / sofa safe zones. Falls inside these zones are suppressed."""
    global _safe_zones
    zones = [{"type": z.type, "box": tuple(z.box)} for z in payload.zones]
    _safe_zones = zones
    _save_zones(zones)
    return {"message": f"{len(zones)} zone(s) saved.", "zones": payload.zones}


@app.get("/vision/zones", tags=["Vision"])
def get_zones():
    """Return currently saved safe zones."""
    zones = [{"type": z["type"], "box": list(z["box"])} for z in _safe_zones]
    return {"zones": zones}


# ═══════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════
@app.on_event("startup")
def on_startup():
    print("\n╔══════════════════════════════════════════╗")
    print("║   LEO API — Starting up                 ║")
    print("╚══════════════════════════════════════════╝\n")
    print(f"  Leo Brain : {'OK' if LEO_BRAIN_AVAILABLE else 'Not loaded'}")
    print(f"  YOLO      : {'OK' if YOLO_AVAILABLE else 'Not loaded'}")
    print(f"  GPU       : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
    print(f"  MongoDB   : {'Connected' if leo_db.connected else 'Offline'}")
    print(f"  Safe zones: {len(_safe_zones)} loaded\n")


@app.on_event("shutdown")
def on_shutdown():
    if leo_db.connected:
        leo_db.close()
    print("\n[LEO API] Shutting down gracefully.")


# ═══════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)