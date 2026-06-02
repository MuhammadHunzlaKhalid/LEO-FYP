# """
# LEO — AI Home Assistant for the Elderly
# FastAPI Backend  (v2 — with rich MongoDB endpoints for Flutter)
# FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
# Supervisor: Dr. Zia Ul Rehman
# """

# from __future__ import annotations

# import os, json, time, base64, warnings, threading
# from datetime import datetime
# from pathlib  import Path
# from typing   import Optional

# import cv2, numpy as np, torch

# warnings.filterwarnings("ignore")
# os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import FileResponse, StreamingResponse
# from pydantic import BaseModel, Field

# # ─────────────────────────────────────────────
# BASE_DIR   = Path(__file__).parent
# ZONES_FILE = BASE_DIR / "safe_zones.json"

# LEO_MODEL_PATH = Path("D:/Python/FYP/models/qwen0.5b")
# FALL_MODEL_PATH = (
#     "D:\\Python\\FYP\\Trained Datasets\\"
#     "GPT_fyp_train_dataset_fall_v2.1\\runs_backup\\detect\\"
#     "runs\\train\\fall_stage1\\weights\\best.pt"
# )
# POSTURE_MODEL_PATH = (
#     "D:\\Python\\FYP\\Trained Datasets\\"
#     "GPT_fyp_train_dataset_lying1_posture_v2.1\\runs_backup\\detect\\"
#     "runs\\train\\siting_stage1\\weights\\best.pt"
# )

# import sys as _sys
# _sys.path.insert(0, str(BASE_DIR))
# from patient_storage import PatientDirs
# from mongo_storage   import leo_db

# # ═══════════════════════════════════════════════════════════════════
# # LEO BRAIN — background loader
# # ═══════════════════════════════════════════════════════════════════
# LEO_BRAIN_AVAILABLE   = False
# _leo_modules_imported = False
# _leo_ready            = False
# _leo_status_msg       = "Not started"
# _brain                = None
# _brain_lock           = threading.Lock()
# _user_cache: dict[str, dict] = {}
# _cache_lock = threading.Lock()

# def _try_import_leo():
#     global LEO_BRAIN_AVAILABLE, _leo_modules_imported, _leo_status_msg
#     _leo_status_msg = "Importing Leo modules..."
#     try:
#         global UserProfile, ConversationMemory, ActivityLogger
#         global IntentMatcher, EmergencyHandler, MedicationHandler
#         global EmotionHandler, ContactHandler, LeoBrain
#         from audio import (
#             UserProfile, ConversationMemory, ActivityLogger,
#             IntentMatcher, EmergencyHandler, MedicationHandler,
#             EmotionHandler, ContactHandler, LeoBrain,
#         )
#         LEO_BRAIN_AVAILABLE = True
#         _leo_status_msg = "Leo modules loaded — warming up LLM..."
#         print("[LEO] Audio modules imported successfully.")
#     except Exception as e:
#         LEO_BRAIN_AVAILABLE = False
#         _leo_status_msg = f"Leo import failed: {e}"
#         print(f"[WARNING] Could not import Leo modules: {e}")
#     finally:
#         _leo_modules_imported = True

# def _warm_up_brain():
#     global _brain, _leo_ready, _leo_status_msg
#     if not LEO_BRAIN_AVAILABLE:
#         return
#     try:
#         _leo_status_msg = "Loading Qwen LLM weights (1-3 min)..."
#         print("[LEO] Loading LLM brain...")
#         with _brain_lock:
#             if _brain is None:
#                 _brain = LeoBrain(LEO_MODEL_PATH)
#         _leo_ready = True
#         _leo_status_msg = "Leo is fully ready ✓"
#         print("[LEO] Brain loaded and ready ✓")
#     except Exception as e:
#         _leo_status_msg = f"Brain load failed: {e}"
#         print(f"[WARNING] Could not load Leo brain: {e}")

# def _background_leo_loader():
#     _try_import_leo()
#     if LEO_BRAIN_AVAILABLE:
#         _warm_up_brain()

# def _get_user_components(username: str) -> dict:
#     username = username.lower().strip()
#     with _cache_lock:
#         if username not in _user_cache:
#             _user_cache[username] = {
#                 "profile":   UserProfile(username)        if LEO_BRAIN_AVAILABLE else None,
#                 "memory":    ConversationMemory(username)  if LEO_BRAIN_AVAILABLE else None,
#                 "logger":    ActivityLogger(username)      if LEO_BRAIN_AVAILABLE else None,
#                 "matcher":   IntentMatcher()               if LEO_BRAIN_AVAILABLE else None,
#                 "emergency": EmergencyHandler()            if LEO_BRAIN_AVAILABLE else None,
#                 "meds":      MedicationHandler()           if LEO_BRAIN_AVAILABLE else None,
#                 "emotion":   EmotionHandler()              if LEO_BRAIN_AVAILABLE else None,
#                 "contact":   ContactHandler()              if LEO_BRAIN_AVAILABLE else None,
#             }
#             profile_obj = _user_cache[username]["profile"]
#             if profile_obj and leo_db.connected:
#                 leo_db.save_patient(profile_obj.data)
#     return _user_cache[username]

# # ═══════════════════════════════════════════════════════════════════
# # FILE-BASED HELPERS
# # ═══════════════════════════════════════════════════════════════════
# def _file_get_profile(username: str):
#     """Returns profile dict if file exists, None otherwise. Never returns a fake default."""
#     pd = PatientDirs(username)
#     if pd.profile_file.exists():
#         try:
#             return json.loads(pd.profile_file.read_text(encoding="utf-8"))
#         except Exception:
#             pass
#     return None

# def _file_save_profile(username: str, data: dict):
#     pd = PatientDirs(username)
#     pd.profile_file.write_text(
#         json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

# def _file_get_logs(username: str) -> list:
#     pd = PatientDirs(username)
#     lf = pd.log_file()
#     if not lf.exists():
#         return []
#     try:
#         raw = json.loads(lf.read_text(encoding="utf-8"))
#         if isinstance(raw, list):   return raw
#         if isinstance(raw, dict):   return raw.get("entries", raw.get("logs", []))
#     except Exception:
#         pass
#     return []

# def _default_profile(username: str) -> dict:
#     return {
#         "personal": {"name": username},
#         "emergency_contacts": [],
#         "contacts": [],
#         "medications": [],
#         "routine": {"wake": "07:00", "sleep": "22:00"},
#         "active_zones": ["Living Room", "Bedroom", "Kitchen"],
#         "preferences": {},
#     }

# def _fmt_dt(dt) -> Optional[str]:
#     if dt is None: return None
#     if isinstance(dt, datetime): return dt.strftime("%Y-%m-%d %H:%M:%S")
#     return str(dt)

# # ═══════════════════════════════════════════════════════════════════
# # YOLO
# # ═══════════════════════════════════════════════════════════════════
# fall_model = posture_model = None
# YOLO_AVAILABLE = False
# try:
#     from ultralytics import YOLO
#     fall_model    = YOLO(FALL_MODEL_PATH).to("cuda" if torch.cuda.is_available() else "cpu")
#     posture_model = YOLO(POSTURE_MODEL_PATH).to("cuda" if torch.cuda.is_available() else "cpu")
#     YOLO_AVAILABLE = True
#     print("[OK] YOLO fall/posture models loaded.")
# except Exception as e:
#     print(f"[WARNING] YOLO models not loaded: {e}")

# # ═══════════════════════════════════════════════════════════════════
# # SCHEMAS
# # ═══════════════════════════════════════════════════════════════════
# class ChatRequest(BaseModel):
#     username: str = Field(..., example="ahmed")
#     message:  str = Field(..., example="Hello Leo")

# class ChatResponse(BaseModel):
#     username: str; message: str; reply: str
#     intent: Optional[str] = None; timestamp: str

# class ProfileUpdate(BaseModel):
#     personal:           Optional[dict] = None
#     emergency_contacts: Optional[list] = None
#     contacts:           Optional[list] = None
#     medications:        Optional[list] = None
#     routine:            Optional[dict] = None
#     active_zones:       Optional[list] = None
#     preferences:        Optional[dict] = None

# class MedicationItem(BaseModel):
#     medicine: str; time: str
#     quantity_left: Optional[str] = None
#     notes: Optional[str] = None

# class EmergencyAlertRequest(BaseModel):
#     username: str
#     level:    Optional[str] = "fall"
#     reason:   Optional[str] = None
#     message:  Optional[str] = None

# class FrameAnalysisRequest(BaseModel):
#     frame_b64: str
#     username:  Optional[str] = "unknown"

# class ZoneItem(BaseModel):
#     type: str; box: list[int]

# class ZonesPayload(BaseModel):
#     zones: list[ZoneItem]

# class FallStatusResponse(BaseModel):
#     state: str; fall_detected: bool; on_safe_zone: bool
#     posture: str; confidence: float; timestamp: str

# # ═══════════════════════════════════════════════════════════════════
# # FALL STATE
# # ═══════════════════════════════════════════════════════════════════
# _fall_state = {
#     "state": "UNKNOWN", "fall_detected": False, "on_safe_zone": False,
#     "posture": "unknown", "confidence": 0.0,
#     "timestamp": datetime.now().isoformat(),
# }
# _fall_lock  = threading.Lock()

# # Live frame buffer — filled by analyze-frame, served by /video/live-frame
# _latest_jpeg: bytes = b""
# _frame_lock  = threading.Lock()
# _current_patient = "unknown"   # set when monitoring brain starts session

# def _load_zones(username: str = "") -> list:
#     """
#     Load zones trying multiple sources in order:
#     1. Exact username folder  (data/patients/{username}/safe_zones.json)
#     2. Username variants      (e.g. "ali" → also tries "muhammad_ali")
#     3. All patient folders    (scan for any safe_zones.json)
#     4. Global fallback        (safe_zones.json in backend root)
#     """
#     def _read_zone_file(path) -> list:
#         try:
#             with open(path) as f:
#                 data = json.load(f)
#             return [{"type": d["type"], "box": tuple(d["box"])} for d in data]
#         except Exception:
#             return []

#     patients_dir = BASE_DIR / "data" / "patients"

#     # 1 & 2 — exact username + variants
#     if username:
#         candidates = [username]
#         # scan all patient folders for names that contain this username
#         if patients_dir.exists():
#             for folder in patients_dir.iterdir():
#                 if folder.is_dir():
#                     fn = folder.name.lower()
#                     un = username.lower()
#                     if fn != un and (fn.endswith("_" + un) or fn.startswith(un + "_") or un in fn):
#                         candidates.append(folder.name)

#         for cand in candidates:
#             pf = patients_dir / cand / "safe_zones.json"
#             if pf.exists():
#                 z = _read_zone_file(pf)
#                 if z:
#                     return z

#     # 3 — scan ALL patient folders (pick the most recently modified)
#     if patients_dir.exists():
#         zone_files = sorted(
#             [p for p in patients_dir.rglob("safe_zones.json")],
#             key=lambda p: p.stat().st_mtime, reverse=True
#         )
#         for zf in zone_files:
#             z = _read_zone_file(zf)
#             if z:
#                 return z

#     # 4 — global fallback
#     if ZONES_FILE.exists():
#         z = _read_zone_file(ZONES_FILE)
#         if z:
#             return z

#     return []

# def _save_zones(zones: list, username: str = ""):
#     """Save zones to patient folder AND global file."""
#     data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
#     # Global file
#     with open(ZONES_FILE, "w") as f: json.dump(data, f, indent=2)
#     # Patient-specific file
#     if username:
#         pf = BASE_DIR / "data" / "patients" / username / "safe_zones.json"
#         pf.parent.mkdir(parents=True, exist_ok=True)
#         with open(pf, "w") as f: json.dump(data, f, indent=2)

# _safe_zones = _load_zones()

# def _person_in_safe_zone(box, zones):
#     if not box or not zones: return False
#     x1, y1, x2, y2 = box
#     cx, cy = (x1+x2)/2, (y1+y2)/2
#     for z in zones:
#         zx1,zy1,zx2,zy2 = z["box"]
#         if zx1<=cx<=zx2 and zy1<=cy<=zy2: return True
#     return False

# def _get_aspect_ratio(box):
#     x1,y1,x2,y2 = box
#     return max(y2-y1,1)/max(x2-x1,1)

# def _route_intent(text, components, username):
#     matcher=components["matcher"]; profile=components["profile"]
#     memory=components["memory"]; emergency=components["emergency"]
#     meds=components["meds"]; emotion_h=components["emotion"]
#     contact_h=components["contact"]
#     t = text.strip()
#     if matcher.is_greeting(t):
#         h = datetime.now().hour
#         g = "Good morning" if h<12 else ("Good afternoon" if h<18 else "Good evening")
#         return "greeting", f"{g}, {profile.name}! How are you feeling today?"
#     if matcher.is_memory_question(t):
#         recent = memory.recent_user_messages(3)
#         if not recent: return "memory", "We haven't talked much today. What's on your mind?"
#         return "memory", "Earlier you mentioned: " + " ... ".join(recent)
#     if "emergency contact" in t.lower() and any(w in t.lower() for w in ["show","list","who","what"]):
#         return "contacts", contact_h.list_contacts(profile.emergency_contacts, emergency_only=True)
#     emotion = matcher.detect_emotion(t)
#     if emotion == "hopeless":
#         return "emergency_critical", emergency.respond("critical", profile.name, profile.emergency_contacts)
#     if emotion:
#         return f"emotion_{emotion}", emotion_h.respond(emotion, profile.name)
#     level = matcher.detect_emergency_level(t)
#     if level:
#         return f"emergency_{level}", emergency.respond(level, profile.name, profile.emergency_contacts)
#     if matcher.is_medication(t):
#         return "medication", meds.respond(t, profile.medications)
#     if matcher.is_call_request(t):
#         contact = contact_h.find(profile.all_contacts, t)
#         if contact:
#             return "call", f"Calling {contact['name']} ({contact.get('phone','')}) now..."
#         names = ", ".join(c["name"] for c in profile.all_contacts) if profile.all_contacts else "none"
#         return "call", f"Who to call? I have: {names}."
#     if _brain is None:
#         return "llm_unavailable", "Leo's brain is still loading. Please wait a moment."
#     return "llm", _brain.chat(t, profile.data, memory.as_messages())

# # ═══════════════════════════════════════════════════════════════════
# # APP
# # ═══════════════════════════════════════════════════════════════════
# app = FastAPI(
#     title="LEO — AI Home Assistant API",
#     description="FYP 2024-25",
#     version="2.0.0",
# )
# app.add_middleware(CORSMiddleware, allow_origins=["*"],
#                    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# # ── HEALTH ────────────────────────────────────────────────
# @app.get("/health", tags=["System"])
# def health_check():
#     return {
#         "status": "ok",
#         "leo_modules_imported": LEO_BRAIN_AVAILABLE,
#         "leo_ready": _leo_ready,
#         "leo_status": _leo_status_msg,
#         "yolo_available": YOLO_AVAILABLE,
#         "gpu": torch.cuda.is_available(),
#         "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
#         "mongodb": leo_db.connected,
#         "timestamp": datetime.now().isoformat(),
#     }

# # ── CHAT ─────────────────────────────────────────────────
# @app.post("/chat", response_model=ChatResponse, tags=["Chat"])
# def chat(req: ChatRequest):
#     """
#     Always returns HTTP 200 — never 503.
#     If Leo isn't ready, returns a friendly loading/error message
#     so the Flutter app always gets a visible reply.
#     """
#     username = req.username.lower().strip()

#     # ── Wait up to 15s for import to finish ──────────────
#     waited = 0
#     while not _leo_modules_imported and waited < 15:
#         time.sleep(1); waited += 1

#     # ── Leo modules failed to import entirely ─────────────
#     if not LEO_BRAIN_AVAILABLE:
#         reply = (
#             f"⚠️ I'm having trouble starting up. "
#             f"Status: {_leo_status_msg}. "
#             f"Please check the backend terminal for errors "
#             f"(usually a numpy/scipy version mismatch)."
#         )
#         return ChatResponse(username=username, message=req.message,
#                             reply=reply, intent="error",
#                             timestamp=datetime.now().isoformat())

#     # ── Leo imported but LLM brain still loading ──────────
#     if not _leo_ready:
#         # Try simple intent matching without LLM
#         try:
#             components = _get_user_components(username)
#             matcher = components.get("matcher")
#             profile = components.get("profile")
#             if matcher and profile:
#                 t = req.message.strip()
#                 if matcher.is_greeting(t):
#                     h = datetime.now().hour
#                     g = "Good morning" if h < 12 else ("Good afternoon" if h < 18 else "Good evening")
#                     reply = f"{g}, {profile.name}! I'm still loading my full AI brain, but I'm here to help with basic requests."
#                     return ChatResponse(username=username, message=req.message,
#                                         reply=reply, intent="greeting",
#                                         timestamp=datetime.now().isoformat())
#                 if matcher.is_medication(t):
#                     meds_obj = components.get("meds")
#                     if meds_obj:
#                         reply = meds_obj.respond(t, profile.medications)
#                         return ChatResponse(username=username, message=req.message,
#                                             reply=reply, intent="medication",
#                                             timestamp=datetime.now().isoformat())
#         except Exception:
#             pass

#         reply = (
#             f"⏳ I'm still loading my AI brain ({_leo_status_msg}). "
#             f"Greetings and medication questions work now — "
#             f"full AI chat ready in about 1-2 minutes!"
#         )
#         return ChatResponse(username=username, message=req.message,
#                             reply=reply, intent="loading",
#                             timestamp=datetime.now().isoformat())

#     # ── Full Leo response ─────────────────────────────────
#     try:
#         components = _get_user_components(username)
#         intent, reply = _route_intent(req.message, components, username)
#         components["memory"].add(req.message, reply)
#         components["logger"].log("chat", f"User: {req.message} | Leo: {reply}")
#         if leo_db.connected:
#             leo_db.log_activity(username, "chat",
#                                 f"User: {req.message} | Leo: {reply}")
#     except Exception as e:
#         reply = f"I encountered an error: {str(e)[:100]}. Please try again."
#         intent = "error"

#     return ChatResponse(username=username, message=req.message,
#                         reply=reply, intent=intent,
#                         timestamp=datetime.now().isoformat())

# # ── LIST ALL PATIENTS ─────────────────────────────────────
# @app.get("/patients", tags=["User"])
# def list_patients():
#     """
#     Returns all registered patients from MongoDB + local files.
#     Used by the login page to show available usernames.
#     """
#     usernames = set()

#     # From MongoDB
#     if leo_db.connected:
#         try:
#             for u in leo_db.list_patients():
#                 usernames.add(u.lower())
#         except Exception as e:
#             print(f"[WARN] list_patients MongoDB: {e}")

#     # From local files
#     patients_dir = BASE_DIR / "data" / "patients"
#     if patients_dir.exists():
#         for folder in patients_dir.iterdir():
#             if folder.is_dir():
#                 pf = folder / "profile.json"
#                 if pf.exists():
#                     usernames.add(folder.name.lower())

#     # Get names for each username
#     result = []
#     for u in sorted(usernames):
#         name = u
#         try:
#             # Try file first
#             pf = BASE_DIR / "data" / "patients" / u / "profile.json"
#             if pf.exists():
#                 d = json.loads(pf.read_text(encoding="utf-8"))
#                 name = d.get("personal", {}).get("name", u)
#             elif leo_db.connected:
#                 d = leo_db.get_patient(u)
#                 if d:
#                     name = d.get("personal", {}).get("name", u)
#         except Exception:
#             pass
#         result.append({"username": u, "name": name})

#     return {"patients": result, "count": len(result)}


# # ── PROFILE ───────────────────────────────────────────────
# @app.get("/user/{username}/profile", tags=["User"])
# def get_profile(username: str):
#     """
#     Fetch patient profile.
#     Priority: 1) Leo cache  2) Local file  3) MongoDB (including username variants)
#     """
#     username = username.lower().strip()

#     # 1 — Leo in-memory cache
#     if LEO_BRAIN_AVAILABLE and username in _user_cache:
#         c = _user_cache[username]
#         if c.get("profile") and c["profile"].data.get("personal", {}).get("name"):
#             return {"username": username, "profile": c["profile"].data}

#     # 2 — Local file (only if file actually exists)
#     file_data = _file_get_profile(username)
#     if file_data and file_data.get("personal", {}).get("name"):
#         return {"username": username, "profile": file_data}

#     # 3 — MongoDB  (try exact username AND common variations)
#     if leo_db.connected:
#         candidates = [username]
#         # e.g. "ali" → also try "muhammad_ali" style variants from DB
#         if "_" not in username:
#             try:
#                 for u in leo_db.list_patients():
#                     if u.endswith("_" + username) or u.startswith(username + "_"):
#                         candidates.append(u)
#             except Exception:
#                 pass

#         best_profile = None
#         for candidate in candidates:
#             try:
#                 mongo_data = leo_db.get_patient(candidate)
#                 if mongo_data and isinstance(mongo_data, dict):
#                     if mongo_data.get("personal", {}).get("name"):
#                         if best_profile is None:
#                             best_profile = mongo_data
#                         else:
#                             # Merge: take whichever has more data in each field
#                             for field in ["medications", "emergency_contacts", "contacts", "active_zones"]:
#                                 existing = best_profile.get(field, [])
#                                 candidate_val = mongo_data.get(field, [])
#                                 if len(candidate_val) > len(existing):
#                                     best_profile[field] = candidate_val
#                             # Merge personal info
#                             for key in ["age", "gender", "condition", "phone"]:
#                                 if not best_profile.get("personal", {}).get(key):
#                                     best_profile.setdefault("personal", {})[key] = (
#                                         mongo_data.get("personal", {}).get(key, ""))
#             except Exception as e:
#                 print(f"[WARN] MongoDB get_profile ({candidate}): {e}")

#         if best_profile:
#             try: _file_save_profile(username, best_profile)
#             except Exception: pass
#             return {"username": username, "profile": best_profile}

#     raise HTTPException(404, detail=f"User '{username}' not found. Register first.")

# @app.put("/user/{username}/profile", tags=["User"])
# def update_profile(username: str, update: ProfileUpdate):
#     username = username.lower().strip()
#     existing = _file_get_profile(username) or _default_profile(username)
#     patch = update.model_dump(exclude_none=True)
#     for field, value in patch.items():
#         if isinstance(value, dict) and isinstance(existing.get(field), dict):
#             existing[field].update(value)
#         else:
#             existing[field] = value
#     _file_save_profile(username, existing)
#     if LEO_BRAIN_AVAILABLE and username in _user_cache:
#         try:
#             c = _user_cache[username]
#             if c.get("profile"):
#                 c["profile"].data.update(existing)
#                 c["profile"].save()
#         except Exception as e:
#             print(f"[WARN] Leo cache sync: {e}")
#     if leo_db.connected:
#         try: leo_db.save_patient(existing)
#         except: pass
#     return {"username": username, "status": "updated", "profile": existing}

# # ── LOGS ─────────────────────────────────────────────────
# @app.get("/user/{username}/logs", tags=["User"])
# def get_logs(username: str, category: Optional[str] = None,
#              severity: Optional[str] = None, limit: int = 100):
#     username = username.lower().strip()
#     # MongoDB first (richest data)
#     if leo_db.connected:
#         try:
#             from pymongo import DESCENDING as DESC
#             query = {"patient": username}
#             if category: query["category"] = category
#             if severity: query["severity"] = severity
#             entries = []
#             for l in leo_db._col("activity_logs").find(query).sort(
#                     "timestamp", DESC).limit(limit):
#                 entries.append({
#                     "category":  l.get("category", "info"),
#                     "severity":  l.get("severity", "info"),
#                     "message":   l.get("content", l.get("message", "")),
#                     "timestamp": _fmt_dt(l.get("timestamp")),
#                     "date":      l.get("date", ""),
#                     "time":      l.get("time", ""),
#                 })
#             return {"username": username,
#                     "date": datetime.now().strftime("%Y-%m-%d"),
#                     "logs": entries}
#         except Exception as e:
#             print(f"[WARN] MongoDB logs: {e}")
#     # Leo cache fallback
#     if LEO_BRAIN_AVAILABLE and username in _user_cache:
#         c = _user_cache[username]
#         if c.get("logger"):
#             entries = c["logger"].entries
#             if category: entries = [e for e in entries if e.get("category")==category]
#             if severity:  entries = [e for e in entries if e.get("severity")==severity]
#             return {"username": username,
#                     "date": datetime.now().strftime("%Y-%m-%d"),
#                     "logs": entries}
#     # File fallback
#     entries = _file_get_logs(username)
#     return {"username": username,
#             "date": datetime.now().strftime("%Y-%m-%d"),
#             "logs": entries}

# # ── MEMORY ───────────────────────────────────────────────
# @app.get("/user/{username}/memory", tags=["User"])
# def get_memory(username: str, last_n: int = 10):
#     if not LEO_BRAIN_AVAILABLE:
#         return {"username": username, "history": [], "note": _leo_status_msg}
#     c = _get_user_components(username)
#     return {"username": username, "history": c["memory"].history[-last_n*2:]}

# @app.delete("/user/{username}/memory", tags=["User"])
# def clear_memory(username: str):
#     if not LEO_BRAIN_AVAILABLE:
#         raise HTTPException(503, _leo_status_msg)
#     c = _get_user_components(username)
#     c["memory"].history = []; c["memory"].save()
#     return {"message": f"Memory cleared for {username}."}

# # ── MEDICATIONS ───────────────────────────────────────────
# @app.post("/user/{username}/medications", tags=["Medications"])
# def set_medications(username: str, medications: list[MedicationItem]):
#     username = username.lower().strip()
#     existing = _file_get_profile(username) or _default_profile(username)
#     existing["medications"] = [m.model_dump() for m in medications]
#     _file_save_profile(username, existing)
#     if leo_db.connected:
#         try: leo_db.save_patient(existing)
#         except: pass
#     return {"message": "Medications updated.",
#             "medications": existing["medications"]}

# @app.get("/medications/{username}/due", tags=["Medications"])
# def medications_due(username: str):
#     username = username.lower().strip()
#     now = datetime.now().strftime("%H:%M")
#     profile = _file_get_profile(username) or _default_profile(username)
#     due = [m for m in profile.get("medications", []) if m.get("time")==now]
#     return {"username": username, "time": now, "due": due}

# # ── EMERGENCY ─────────────────────────────────────────────
# @app.post("/emergency/alert", tags=["Emergency"])
# def emergency_alert(req: EmergencyAlertRequest, background_tasks: BackgroundTasks):
#     username = req.username.lower().strip()
#     level    = req.level or "fall"
#     message  = req.reason or req.message or level
#     if level not in {"critical","fall","confusion"}: level = "fall"
#     profile  = _file_get_profile(username) or _default_profile(username)
#     contacts = profile.get("emergency_contacts", [])
#     name     = profile.get("personal", {}).get("name", username)
#     names    = ", ".join(c.get("name","?") for c in contacts) if contacts else "no contacts saved"
#     response_text = f"Emergency alert for {name}! Notifying: {names}. Level: {level}."
#     print(f"[EMERGENCY] {username} | {level} | {message}")
#     # File log
#     try:
#         pd = PatientDirs(username); lf = pd.log_file()
#         logs = []
#         if lf.exists():
#             try:
#                 raw = json.loads(lf.read_text(encoding="utf-8"))
#                 logs = raw if isinstance(raw, list) else raw.get("entries", [])
#             except: pass
#         logs.append({"category":"emergency","severity":"critical",
#                      "message":message,"timestamp":datetime.now().isoformat()})
#         lf.write_text(json.dumps(logs,indent=2,ensure_ascii=False),encoding="utf-8")
#     except Exception as e:
#         print(f"[WARN] Emergency log: {e}")
#     # MongoDB
#     if leo_db.connected:
#         try:
#             leo_db.log_activity(username,"emergency",message,severity="critical")
#             if level=="fall":
#                 leo_db.log_fall(username,score=0,reason=message,state="FALL")
#         except: pass
#     return {"username":username,"level":level,"message":response_text,
#             "contacts":contacts,"timestamp":datetime.now().isoformat()}

# # ══════════════════════════════════════════════════════════
# # ★ NEW ENDPOINTS — Rich MongoDB data for Flutter app
# # ══════════════════════════════════════════════════════════

# @app.get("/user/{username}/summary", tags=["Dashboard"])
# def get_summary(username: str):
#     """
#     Rich summary card data pulled from MongoDB.
#     Returns: falls_today, total_falls, total_sessions, last_activity, last_fall.
#     Used by Flutter Home screen stats cards.
#     """
#     username = username.lower().strip()
#     if leo_db.connected:
#         try:
#             data = leo_db.get_patient_summary(username)
#             return data if data else _empty_summary(username)
#         except Exception as e:
#             print(f"[WARN] summary: {e}")
#     return _empty_summary(username)

# def _empty_summary(username):
#     return {"patient": username, "falls_today": 0, "total_falls": 0,
#             "total_sessions": 0, "last_activity": None, "last_fall": None,
#             "last_fall_clip": None}

# @app.get("/user/{username}/falls", tags=["Dashboard"])
# def get_falls(username: str, limit: int = 30):
#     """
#     All fall events for this patient from MongoDB.
#     Includes: date, time, reason, posture, score, state, clip_path.
#     Used by Flutter Detection / Alerts screens.
#     """
#     username = username.lower().strip()
#     falls = []
#     if leo_db.connected:
#         try:
#             from pymongo import DESCENDING as DESC
#             for f in leo_db._col("fall_events").find(
#                     {"patient": username}).sort("timestamp", DESC).limit(limit):
#                 falls.append({
#                     "date":      f.get("date", ""),
#                     "time":      f.get("time", ""),
#                     "score":     f.get("score", 0),
#                     "reason":    f.get("reason", ""),
#                     "posture":   f.get("posture", ""),
#                     "state":     f.get("state", ""),
#                     "clip_path": f.get("clip_path"),
#                     "timestamp": _fmt_dt(f.get("timestamp")),
#                 })
#         except Exception as e:
#             print(f"[WARN] falls: {e}")
#     return {"username": username, "count": len(falls), "falls": falls}

# @app.get("/user/{username}/sessions", tags=["Dashboard"])
# def get_sessions(username: str, limit: int = 10):
#     """
#     Monitoring sessions from MongoDB.
#     Includes: start_time, end_time, fall_count, status, recording_path.
#     Used by Flutter Alerts screen Sessions tab.
#     """
#     username = username.lower().strip()
#     sessions = []
#     if leo_db.connected:
#         try:
#             from pymongo import DESCENDING as DESC
#             for s in leo_db._col("sessions").find(
#                     {"patient": username}).sort("start_time", DESC).limit(limit):
#                 sessions.append({
#                     "start_time":     _fmt_dt(s.get("start_time")),
#                     "end_time":       _fmt_dt(s.get("end_time")),
#                     "fall_count":     s.get("fall_count", 0),
#                     "status":         s.get("status", ""),
#                     "recording_path": s.get("recording_path", ""),
#                 })
#         except Exception as e:
#             print(f"[WARN] sessions: {e}")
#     return {"username": username, "count": len(sessions), "sessions": sessions}

# # ── VISION ────────────────────────────────────────────────
# LYING_AR_THRESHOLD  = 1.2
# FALL_CONF_THRESHOLD = 0.40

# @app.post("/vision/analyze-frame", response_model=FallStatusResponse, tags=["Vision"])
# def analyze_frame(req: FrameAnalysisRequest):
#     global _latest_jpeg, _safe_zones, _current_patient
#     if not YOLO_AVAILABLE: raise HTTPException(503, "YOLO models not loaded.")
#     try:
#         img_bytes = base64.b64decode(req.frame_b64)
#         nparr = np.frombuffer(img_bytes, np.uint8)
#         frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#         if frame is None: raise ValueError("imdecode returned None")
#     except Exception as e:
#         raise HTTPException(400, f"Invalid image: {e}")
#     frame = cv2.resize(frame, (640, 480))
#     # Track current patient and reload their zones if changed
#     username = (req.username or "").lower().strip()
#     if username and username != _current_patient:
#         _current_patient = username
#         new_zones = _load_zones(username)
#         if new_zones:
#             _safe_zones = new_zones
#     fall_results    = fall_model(frame, verbose=False)
#     posture_results = posture_model(frame, verbose=False)
#     fall_detected=False; fall_conf=0.0; fall_box=None
#     for r in fall_results:
#         for box in r.boxes:
#             conf = float(box.conf[0])
#             if conf >= FALL_CONF_THRESHOLD:
#                 fall_detected=True; fall_conf=max(fall_conf,conf)
#                 fall_box=[int(v) for v in box.xyxy[0].tolist()]
#     posture_label="unknown"; posture_box=None; best_conf=0.0
#     for r in posture_results:
#         for box in r.boxes:
#             conf=float(box.conf[0]); label=posture_model.names[int(box.cls[0])]
#             if conf>best_conf:
#                 best_conf=conf; posture_label=label
#                 posture_box=[int(v) for v in box.xyxy[0].tolist()]
#     if posture_box:
#         ar=_get_aspect_ratio(posture_box)
#         if ar<LYING_AR_THRESHOLD and posture_label not in("lying","fall"):
#             posture_label="lying"
#     on_safe_zone=_person_in_safe_zone(fall_box or posture_box,_safe_zones)
#     if on_safe_zone: fall_detected=False
#     state=("FALL" if fall_detected else
#            ("LYING"if posture_label=="lying" else
#             ("STANDING" if posture_label=="standing" else
#              ("SITTING" if posture_label=="sitting" else "UNKNOWN"))))
#     result=FallStatusResponse(state=state,fall_detected=fall_detected,
#         on_safe_zone=on_safe_zone,posture=posture_label,
#         confidence=round(fall_conf,3),timestamp=datetime.now().isoformat())
#     with _fall_lock: _fall_state.update(result.model_dump())

#     # Store annotated frame as JPEG for live streaming
#     try:
#         annotated = frame.copy()
#         color = (0,0,220) if fall_detected else (0,200,0)
#         label = f"{result.state}  conf:{result.confidence:.2f}"
#         cv2.putText(annotated, label, (10,30),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#         if result.posture != "unknown":
#             cv2.putText(annotated, f"Posture: {result.posture}", (10,60),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,200,0), 2)
#         # Draw safe zones on frame
#         for z in _safe_zones:
#             bx = [int(v) for v in z["box"]]
#             if len(bx) == 4:
#                 x1,y1,x2,y2 = bx
#                 cv2.rectangle(annotated,(x1,y1),(x2,y2),(255,165,0),2)
#                 cv2.putText(annotated, z["type"].upper(), (x1,y1-5),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,165,0), 1)
#         _, jpeg_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
#         with _frame_lock:
#             _latest_jpeg = jpeg_buf.tobytes()
#     except Exception: pass

#     if fall_detected and req.username and LEO_BRAIN_AVAILABLE:
#         try:
#             c=_get_user_components(req.username)
#             c["logger"].log("fall",f"Fall — conf:{fall_conf:.2f}",severity="critical")
#         except: pass
#     return result

# @app.get("/vision/status", response_model=FallStatusResponse, tags=["Vision"])
# def vision_status():
#     with _fall_lock: return FallStatusResponse(**_fall_state)

# @app.post("/vision/zones", tags=["Vision"])
# def set_zones(payload: ZonesPayload):
#     global _safe_zones
#     _safe_zones=[{"type":z.type,"box":tuple(z.box)} for z in payload.zones]
#     _save_zones(_safe_zones)
#     return {"message":f"{len(_safe_zones)} zone(s) saved.","zones":payload.zones}

# @app.get("/vision/zones", tags=["Vision"])
# def get_zones():
#     # Return in-memory zones (may be patient-specific if brain is running)
#     all_zones = _safe_zones
#     if not all_zones and _current_patient:
#         all_zones = _load_zones(_current_patient)
#     return {"zones": [{"type": z["type"], "box": list(z["box"])} for z in all_zones]}


# @app.get("/user/{username}/videos", tags=["Dashboard"])
# def get_videos(username: str):
#     """
#     List all saved video recordings for this patient from disk.
#     Returns: date, filename, path, type (fall/recording), size_mb.
#     """
#     username = username.lower().strip()
#     videos = []
#     folder = BASE_DIR / "data" / "patients" / username / "videos"
#     if folder.exists():
#         try:
#             for date_dir in sorted(folder.iterdir(), reverse=True):
#                 if not date_dir.is_dir():
#                     continue
#                 for vid in sorted(date_dir.glob("*.avi"), reverse=True):
#                     videos.append({
#                         "date":      date_dir.name,
#                         "filename":  vid.name,
#                         "path":      str(vid),
#                         "type":      "fall" if vid.name.startswith("fall_") else "recording",
#                         "size_mb":   round(vid.stat().st_size / (1024 * 1024), 1),
#                     })
#         except Exception as e:
#             print(f"[WARN] videos listing error: {e}")
#     return {"username": username, "count": len(videos), "videos": videos}


# @app.get("/video/stream", tags=["Videos"])
# def stream_video(path: str, request: Request):
#     """
#     Stream a saved video file from local disk to the browser / Flutter app.
#     Supports HTTP Range requests (needed for seek/scrub in browser video player).

#     Usage:  GET /video/stream?path=D:\\...\\fall_clip.avi
#     Flutter: open  http://localhost:8000/video/stream?path=<encoded_path>
#     """
#     video_path = Path(path)

#     if not video_path.exists():
#         raise HTTPException(status_code=404, detail=f"Video not found: {path}")

#     suffix = video_path.suffix.lower()
#     if suffix not in ('.avi', '.mp4', '.mkv', '.mov', '.webm'):
#         raise HTTPException(status_code=400, detail="Not a supported video file")

#     content_type_map = {
#         '.avi':  'video/x-msvideo',
#         '.mp4':  'video/mp4',
#         '.mkv':  'video/x-matroska',
#         '.mov':  'video/quicktime',
#         '.webm': 'video/webm',
#     }
#     content_type = content_type_map.get(suffix, 'application/octet-stream')
#     file_size = video_path.stat().st_size

#     # ── Range request support (browser seek/scrub) ────────
#     range_header = request.headers.get("range")
#     if range_header:
#         try:
#             range_val  = range_header.strip().lower().replace("bytes=", "")
#             start, end = range_val.split("-")
#             start = int(start)
#             end   = int(end) if end else file_size - 1
#             end   = min(end, file_size - 1)
#             length = end - start + 1

#             def iter_chunk():
#                 with open(video_path, "rb") as f:
#                     f.seek(start)
#                     remaining = length
#                     while remaining > 0:
#                         chunk = f.read(min(65536, remaining))
#                         if not chunk:
#                             break
#                         remaining -= len(chunk)
#                         yield chunk

#             headers = {
#                 "Content-Range":  f"bytes {start}-{end}/{file_size}",
#                 "Accept-Ranges":  "bytes",
#                 "Content-Length": str(length),
#                 "Content-Type":   content_type,
#             }
#             return StreamingResponse(iter_chunk(), status_code=206, headers=headers)
#         except Exception as e:
#             print(f"[WARN] Range request error: {e}")

#     # ── Full file response ────────────────────────────────
#     return FileResponse(
#         path=str(video_path),
#         media_type=content_type,
#         headers={"Accept-Ranges": "bytes",
#                  "Content-Length": str(file_size)},
#     )


# @app.get("/video/thumbnail", tags=["Videos"])
# def video_thumbnail(path: str):
#     """
#     Extract a JPEG thumbnail from a video file using OpenCV.
#     Returns a JPEG image of the first frame.
#     Falls back to a 1x1 placeholder if extraction fails.
#     """
#     import base64, io
#     video_path = Path(path)
#     placeholder = (
#         b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
#         b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
#         b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
#         b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
#         b'\x1b@Roh\xff\xd9'
#     )
#     if not video_path.exists():
#         from fastapi.responses import Response
#         return Response(content=placeholder, media_type="image/jpeg")
#     try:
#         cap = cv2.VideoCapture(str(video_path))
#         ret, frame = cap.read()
#         cap.release()
#         if ret and frame is not None:
#             frame = cv2.resize(frame, (320, 240))
#             _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
#             from fastapi.responses import Response
#             return Response(content=buf.tobytes(), media_type="image/jpeg")
#     except Exception as e:
#         print(f"[WARN] Thumbnail error: {e}")
#     from fastapi.responses import Response
#     return Response(content=placeholder, media_type="image/jpeg")


# # ── LIVE VIDEO STREAMING ─────────────────────────────────────
# @app.get("/video/live-frame", tags=["Vision"])
# def live_frame_jpeg():
#     """
#     Returns the latest camera frame as JPEG.
#     Flutter polls this every ~150ms to show live video.
#     Falls back to a placeholder if camera is not running.
#     """
#     from fastapi.responses import Response
#     with _frame_lock:
#         jpeg = _latest_jpeg

#     if not jpeg:
#         # Return a 1x1 dark placeholder
#         placeholder = (
#             b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
#             b"\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07"
#             b"\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c"
#             b"\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
#             b"\x1d\x1a\x1c\x1c $.' ",#\x1c\x1c(7),01444\x1f\'9=82<"
#             b".342\x1e\x1b@Roh\xff\xd9"
#         )
#         return Response(content=placeholder, media_type="image/jpeg",
#                        headers={"Cache-Control": "no-cache, no-store"})

#     return Response(content=jpeg, media_type="image/jpeg",
#                    headers={"Cache-Control": "no-cache, no-store",
#                             "Access-Control-Allow-Origin": "*"})


# @app.get("/video/live-stream", tags=["Vision"])
# async def live_mjpeg_stream():
#     """
#     MJPEG stream — open in browser or <img> tag for live video.
#     URL: http://localhost:8000/video/live-stream
#     """
#     import asyncio
#     from fastapi.responses import StreamingResponse as SR

#     async def generate():
#         while True:
#             with _frame_lock:
#                 jpeg = _latest_jpeg
#             if jpeg:
#                 yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
#                        + jpeg + b"\r\n")
#             await asyncio.sleep(0.1)   # 10fps

#     return SR(generate(),
#               media_type="multipart/x-mixed-replace;boundary=frame",
#               headers={"Access-Control-Allow-Origin": "*"})


# @app.get("/user/{username}/zones", tags=["Vision"])
# def get_user_zones(username: str):
#     """
#     Get safe zones for a specific patient.
#     Reads from data/patients/{username}/safe_zones.json first,
#     then falls back to global safe_zones.json.
#     """
#     username = username.lower().strip()
#     zones = _load_zones(username)
#     return {"username": username, "count": len(zones),
#             "zones": [{"type": z["type"], "box": list(z["box"])} for z in zones]}



# @app.post("/video/push-frame", tags=["Vision"])
# async def push_frame_direct(request: Request):
#     """
#     Called by final_monitering_brain.py every frame.
#     Receives the FULLY ANNOTATED frame (YOLO boxes + banner + zones already drawn)
#     plus the current detection state. No YOLO needed here — monitoring brain
#     already did all the heavy lifting.

#     This is the bridge between the monitoring brain and the Flutter app:
#       monitoring brain → POST /video/push-frame → _latest_jpeg → GET /video/live-frame → Flutter
#     """
#     global _latest_jpeg
#     try:
#         data = await request.json()
#     except Exception:
#         return {"status": "error", "detail": "Invalid JSON"}

#     # ── Store annotated JPEG ──────────────────────────────────────
#     jpeg_b64 = data.get("frame_b64", "")
#     if jpeg_b64:
#         try:
#             jpeg_bytes = base64.b64decode(jpeg_b64)
#             with _frame_lock:
#                 _latest_jpeg = jpeg_bytes
#         except Exception as e:
#             print(f"[WARN] push-frame decode error: {e}")

#     # ── Update live fall state from monitoring brain ──────────────
#     state         = data.get("state",          "UNKNOWN")
#     posture       = data.get("posture",         "unknown")
#     fall_detected = bool(data.get("fall_detected", False))
#     on_safe_zone  = bool(data.get("on_safe_zone",  False))
#     confidence    = float(data.get("confidence",   0.0))

#     with _fall_lock:
#         _fall_state.update({
#             "state":         state,
#             "fall_detected": fall_detected,
#             "on_safe_zone":  on_safe_zone,
#             "posture":       posture,
#             "confidence":    confidence,
#             "timestamp":     datetime.now().isoformat(),
#         })

#     # ── Log fall to MongoDB if it's a new fall ─────────────────────
#     patient = data.get("patient", "unknown").lower().strip()
#     if fall_detected and patient and leo_db.connected:
#         try:
#             leo_db.log_activity(patient, "fall",
#                                 f"Fall via monitoring brain — state:{state}",
#                                 severity="critical")
#         except Exception:
#             pass

#     return {"status": "ok", "state": state}

# # ── STARTUP / SHUTDOWN ────────────────────────────────────
# @app.on_event("startup")
# def on_startup():
#     print("\n╔══════════════════════════════════════════╗")
#     print("║   LEO API v2 — Starting up              ║")
#     print("╚══════════════════════════════════════════╝\n")
#     print(f"  YOLO      : {'OK' if YOLO_AVAILABLE else 'Not loaded'}")
#     print(f"  GPU       : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
#     print(f"  MongoDB   : {'Connected' if leo_db.connected else 'Offline'}")
#     print(f"  Safe zones: {len(_safe_zones)} loaded")
#     print(f"  Leo Brain : Loading in background...\n")
#     threading.Thread(target=_background_leo_loader, daemon=True, name="LeoLoader").start()

# @app.on_event("shutdown")
# def on_shutdown():
#     if leo_db.connected: leo_db.close()
#     print("\n[LEO API] Shutdown complete.")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)















"""
LEO — AI Home Assistant for the Elderly
FastAPI Backend  (v2 — with rich MongoDB endpoints for Flutter)
FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

from __future__ import annotations

import os, json, time, base64, warnings, threading
from datetime import datetime
from pathlib  import Path
from typing   import Optional

import cv2, numpy as np, torch

warnings.filterwarnings("ignore")
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
ZONES_FILE = BASE_DIR / "safe_zones.json"

LEO_MODEL_PATH = Path("D:/Python/FYP/models/qwen0.5b")
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

import sys as _sys
_sys.path.insert(0, str(BASE_DIR))
from patient_storage import PatientDirs
from mongo_storage   import leo_db

# ═══════════════════════════════════════════════════════════════════
# LEO BRAIN — background loader
# ═══════════════════════════════════════════════════════════════════
LEO_BRAIN_AVAILABLE   = False
_leo_modules_imported = False
_leo_ready            = False
_leo_status_msg       = "Not started"
_brain                = None
_brain_lock           = threading.Lock()
_user_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()

def _try_import_leo():
    global LEO_BRAIN_AVAILABLE, _leo_modules_imported, _leo_status_msg
    _leo_status_msg = "Importing Leo modules..."
    try:
        global UserProfile, ConversationMemory, ActivityLogger
        global IntentMatcher, EmergencyHandler, MedicationHandler
        global EmotionHandler, ContactHandler, LeoBrain
        from audio import (
            UserProfile, ConversationMemory, ActivityLogger,
            IntentMatcher, EmergencyHandler, MedicationHandler,
            EmotionHandler, ContactHandler, LeoBrain,
        )
        LEO_BRAIN_AVAILABLE = True
        _leo_status_msg = "Leo modules loaded — warming up LLM..."
        print("[LEO] Audio modules imported successfully.")
    except Exception as e:
        LEO_BRAIN_AVAILABLE = False
        _leo_status_msg = f"Leo import failed: {e}"
        print(f"[WARNING] Could not import Leo modules: {e}")
    finally:
        _leo_modules_imported = True

def _warm_up_brain():
    global _brain, _leo_ready, _leo_status_msg
    if not LEO_BRAIN_AVAILABLE:
        return
    try:
        _leo_status_msg = "Loading Qwen LLM weights (1-3 min)..."
        print("[LEO] Loading LLM brain...")
        with _brain_lock:
            if _brain is None:
                _brain = LeoBrain(LEO_MODEL_PATH)
        _leo_ready = True
        _leo_status_msg = "Leo is fully ready ✓"
        print("[LEO] Brain loaded and ready ✓")
    except Exception as e:
        _leo_status_msg = f"Brain load failed: {e}"
        print(f"[WARNING] Could not load Leo brain: {e}")

def _background_leo_loader():
    _try_import_leo()
    if LEO_BRAIN_AVAILABLE:
        _warm_up_brain()

def _get_user_components(username: str) -> dict:
    username = username.lower().strip()
    with _cache_lock:
        if username not in _user_cache:
            _user_cache[username] = {
                "profile":   UserProfile(username)        if LEO_BRAIN_AVAILABLE else None,
                "memory":    ConversationMemory(username)  if LEO_BRAIN_AVAILABLE else None,
                "logger":    ActivityLogger(username)      if LEO_BRAIN_AVAILABLE else None,
                "matcher":   IntentMatcher()               if LEO_BRAIN_AVAILABLE else None,
                "emergency": EmergencyHandler()            if LEO_BRAIN_AVAILABLE else None,
                "meds":      MedicationHandler()           if LEO_BRAIN_AVAILABLE else None,
                "emotion":   EmotionHandler()              if LEO_BRAIN_AVAILABLE else None,
                "contact":   ContactHandler()              if LEO_BRAIN_AVAILABLE else None,
            }
            profile_obj = _user_cache[username]["profile"]
            if profile_obj and leo_db.connected:
                leo_db.save_patient(profile_obj.data)
    return _user_cache[username]

# ═══════════════════════════════════════════════════════════════════
# FILE-BASED HELPERS
# ═══════════════════════════════════════════════════════════════════
def _file_get_profile(username: str):
    """Returns profile dict if file exists, None otherwise. Never returns a fake default."""
    pd = PatientDirs(username)
    if pd.profile_file.exists():
        try:
            return json.loads(pd.profile_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None

def _file_save_profile(username: str, data: dict):
    pd = PatientDirs(username)
    pd.profile_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _file_get_logs(username: str) -> list:
    pd = PatientDirs(username)
    lf = pd.log_file()
    if not lf.exists():
        return []
    try:
        raw = json.loads(lf.read_text(encoding="utf-8"))
        if isinstance(raw, list):   return raw
        if isinstance(raw, dict):   return raw.get("entries", raw.get("logs", []))
    except Exception:
        pass
    return []

def _default_profile(username: str) -> dict:
    return {
        "personal": {"name": username},
        "emergency_contacts": [],
        "contacts": [],
        "medications": [],
        "routine": {"wake": "07:00", "sleep": "22:00"},
        "active_zones": ["Living Room", "Bedroom", "Kitchen"],
        "preferences": {},
    }

def _fmt_dt(dt) -> Optional[str]:
    if dt is None: return None
    if isinstance(dt, datetime): return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)

# ═══════════════════════════════════════════════════════════════════
# YOLO
# ═══════════════════════════════════════════════════════════════════
fall_model = posture_model = None
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
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════
class ChatRequest(BaseModel):
    username: str = Field(..., example="ahmed")
    message:  str = Field(..., example="Hello Leo")

class ChatResponse(BaseModel):
    username: str; message: str; reply: str
    intent: Optional[str] = None; timestamp: str

class ProfileUpdate(BaseModel):
    personal:           Optional[dict] = None
    emergency_contacts: Optional[list] = None
    contacts:           Optional[list] = None
    medications:        Optional[list] = None
    routine:            Optional[dict] = None
    active_zones:       Optional[list] = None
    preferences:        Optional[dict] = None

class MedicationItem(BaseModel):
    medicine: str; time: str
    quantity_left: Optional[str] = None
    notes: Optional[str] = None

class EmergencyAlertRequest(BaseModel):
    username: str
    level:    Optional[str] = "fall"
    reason:   Optional[str] = None
    message:  Optional[str] = None

class FrameAnalysisRequest(BaseModel):
    frame_b64: str
    username:  Optional[str] = "unknown"

class ZoneItem(BaseModel):
    type: str; box: list[int]

class ZonesPayload(BaseModel):
    zones: list[ZoneItem]

class FallStatusResponse(BaseModel):
    state: str; fall_detected: bool; on_safe_zone: bool
    posture: str; confidence: float; timestamp: str

# ═══════════════════════════════════════════════════════════════════
# FALL STATE
# ═══════════════════════════════════════════════════════════════════
_fall_state = {
    "state": "UNKNOWN", "fall_detected": False, "on_safe_zone": False,
    "posture": "unknown", "confidence": 0.0,
    "timestamp": datetime.now().isoformat(),
}
_fall_lock  = threading.Lock()

# Live frame buffer — filled by analyze-frame, served by /video/live-frame
_latest_jpeg: bytes = b""
_frame_lock  = threading.Lock()
_current_patient = "unknown"   # set when monitoring brain starts session

def _load_zones(username: str = "") -> list:
    """
    Load zones trying multiple sources in order:
    1. Exact username folder  (data/patients/{username}/safe_zones.json)
    2. Username variants      (e.g. "ali" → also tries "muhammad_ali")
    3. All patient folders    (scan for any safe_zones.json)
    4. Global fallback        (safe_zones.json in backend root)
    """
    def _read_zone_file(path) -> list:
        try:
            with open(path) as f:
                data = json.load(f)
            return [{"type": d["type"], "box": tuple(d["box"])} for d in data]
        except Exception:
            return []

    patients_dir = BASE_DIR / "data" / "patients"

    # 1 & 2 — exact username + variants
    if username:
        candidates = [username]
        # scan all patient folders for names that contain this username
        if patients_dir.exists():
            for folder in patients_dir.iterdir():
                if folder.is_dir():
                    fn = folder.name.lower()
                    un = username.lower()
                    if fn != un and (fn.endswith("_" + un) or fn.startswith(un + "_") or un in fn):
                        candidates.append(folder.name)

        for cand in candidates:
            pf = patients_dir / cand / "safe_zones.json"
            if pf.exists():
                z = _read_zone_file(pf)
                if z:
                    return z

    # 3 — scan ALL patient folders (pick the most recently modified)
    if patients_dir.exists():
        zone_files = sorted(
            [p for p in patients_dir.rglob("safe_zones.json")],
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        for zf in zone_files:
            z = _read_zone_file(zf)
            if z:
                return z

    # 4 — global fallback
    if ZONES_FILE.exists():
        z = _read_zone_file(ZONES_FILE)
        if z:
            return z

    return []

def _save_zones(zones: list, username: str = ""):
    """Save zones to patient folder AND global file."""
    data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
    # Global file
    with open(ZONES_FILE, "w") as f: json.dump(data, f, indent=2)
    # Patient-specific file
    if username:
        pf = BASE_DIR / "data" / "patients" / username / "safe_zones.json"
        pf.parent.mkdir(parents=True, exist_ok=True)
        with open(pf, "w") as f: json.dump(data, f, indent=2)

_safe_zones = _load_zones()

def _person_in_safe_zone(box, zones):
    if not box or not zones: return False
    x1, y1, x2, y2 = box
    cx, cy = (x1+x2)/2, (y1+y2)/2
    for z in zones:
        zx1,zy1,zx2,zy2 = z["box"]
        if zx1<=cx<=zx2 and zy1<=cy<=zy2: return True
    return False

def _get_aspect_ratio(box):
    x1,y1,x2,y2 = box
    return max(y2-y1,1)/max(x2-x1,1)

def _route_intent(text, components, username):
    matcher=components["matcher"]; profile=components["profile"]
    memory=components["memory"]; emergency=components["emergency"]
    meds=components["meds"]; emotion_h=components["emotion"]
    contact_h=components["contact"]
    t = text.strip()
    if matcher.is_greeting(t):
        h = datetime.now().hour
        g = "Good morning" if h<12 else ("Good afternoon" if h<18 else "Good evening")
        return "greeting", f"{g}, {profile.name}! How are you feeling today?"
    if matcher.is_memory_question(t):
        recent = memory.recent_user_messages(3)
        if not recent: return "memory", "We haven't talked much today. What's on your mind?"
        return "memory", "Earlier you mentioned: " + " ... ".join(recent)
    if "emergency contact" in t.lower() and any(w in t.lower() for w in ["show","list","who","what"]):
        return "contacts", contact_h.list_contacts(profile.emergency_contacts, emergency_only=True)
    emotion = matcher.detect_emotion(t)
    if emotion == "hopeless":
        return "emergency_critical", emergency.respond("critical", profile.name, profile.emergency_contacts)
    if emotion:
        return f"emotion_{emotion}", emotion_h.respond(emotion, profile.name)
    level = matcher.detect_emergency_level(t)
    if level:
        return f"emergency_{level}", emergency.respond(level, profile.name, profile.emergency_contacts)
    if matcher.is_medication(t):
        return "medication", meds.respond(t, profile.medications)
    if matcher.is_call_request(t):
        contact = contact_h.find(profile.all_contacts, t)
        if contact:
            return "call", f"Calling {contact['name']} ({contact.get('phone','')}) now..."
        names = ", ".join(c["name"] for c in profile.all_contacts) if profile.all_contacts else "none"
        return "call", f"Who to call? I have: {names}."
    if _brain is None:
        return "llm_unavailable", "Leo's brain is still loading. Please wait a moment."
    return "llm", _brain.chat(t, profile.data, memory.as_messages())

# ═══════════════════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════════════════
app = FastAPI(
    title="LEO — AI Home Assistant API",
    description="FYP 2024-25",
    version="2.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ── MOBILE APP REQUEST LOGGER ────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _Req
import time as _time

# Emoji map for different endpoints
_ICONS = {
    "/vision/status":  "", "/video/live":     "", "/video/push":    "",
    "/user":           "", "/chat":            "", "/falls":         "",
    "/emergency":      "", "/videos":          "", "/zones":         "",
    "/summary":        "", "/logs":            "", "/sessions":      "",
    "/health":         " ", "/patients":        "", "/medications":   "",
}

class _MobileLogger(BaseHTTPMiddleware):
    async def dispatch(self, request: _Req, call_next):
        # Skip noisy live-frame polling
        if "live-frame" in request.url.path or "live-stream" in request.url.path:
            return await call_next(request)

        t0   = _time.time()
        resp = await call_next(request)
        ms   = int((_time.time() - t0) * 1000)

        path   = request.url.path
        method = request.method
        status = resp.status_code

        # Pick icon
        icon = "🔹"
        for k, v in _ICONS.items():
            if k in path:
                icon = v; break

        # Color by status
        if status < 300:   col = "[92m"   # green
        elif status < 400: col = "[93m"   # yellow
        else:              col = "[91m"   # red

        rst = "[0m"
        dim = "[2m"
        ts  = datetime.now().strftime("%H:%M:%S")

        print(
            f"{dim}{ts}{rst}  {icon}  "
            f"{col}{method:6} {path}{rst}"
            f"{dim}  {status}  {ms}ms{rst}",
            flush=True
        )
        return resp

app.add_middleware(_MobileLogger)
# ─────────────────────────────────────────────────────────

# ── HEALTH ────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "leo_modules_imported": LEO_BRAIN_AVAILABLE,
        "leo_ready": _leo_ready,
        "leo_status": _leo_status_msg,
        "yolo_available": YOLO_AVAILABLE,
        "gpu": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "mongodb": leo_db.connected,
        "timestamp": datetime.now().isoformat(),
    }

# ── CHAT ─────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest):
    """
    Always returns HTTP 200 — never 503.
    If Leo isn't ready, returns a friendly loading/error message
    so the Flutter app always gets a visible reply.
    """
    username = req.username.lower().strip()

    # ── Wait up to 15s for import to finish ──────────────
    waited = 0
    while not _leo_modules_imported and waited < 15:
        time.sleep(1); waited += 1

    # ── Leo modules failed to import entirely ─────────────
    if not LEO_BRAIN_AVAILABLE:
        reply = (
            f"⚠️ I'm having trouble starting up. "
            f"Status: {_leo_status_msg}. "
            f"Please check the backend terminal for errors "
            f"(usually a numpy/scipy version mismatch)."
        )
        return ChatResponse(username=username, message=req.message,
                            reply=reply, intent="error",
                            timestamp=datetime.now().isoformat())

    # ── Leo imported but LLM brain still loading ──────────
    if not _leo_ready:
        # Try simple intent matching without LLM
        try:
            components = _get_user_components(username)
            matcher = components.get("matcher")
            profile = components.get("profile")
            if matcher and profile:
                t = req.message.strip()
                if matcher.is_greeting(t):
                    h = datetime.now().hour
                    g = "Good morning" if h < 12 else ("Good afternoon" if h < 18 else "Good evening")
                    reply = f"{g}, {profile.name}! I'm still loading my full AI brain, but I'm here to help with basic requests."
                    return ChatResponse(username=username, message=req.message,
                                        reply=reply, intent="greeting",
                                        timestamp=datetime.now().isoformat())
                if matcher.is_medication(t):
                    meds_obj = components.get("meds")
                    if meds_obj:
                        reply = meds_obj.respond(t, profile.medications)
                        return ChatResponse(username=username, message=req.message,
                                            reply=reply, intent="medication",
                                            timestamp=datetime.now().isoformat())
        except Exception:
            pass

        reply = (
            f"⏳ I'm still loading my AI brain ({_leo_status_msg}). "
            f"Greetings and medication questions work now — "
            f"full AI chat ready in about 1-2 minutes!"
        )
        return ChatResponse(username=username, message=req.message,
                            reply=reply, intent="loading",
                            timestamp=datetime.now().isoformat())

    # ── Full Leo response ─────────────────────────────────
    try:
        components = _get_user_components(username)
        intent, reply = _route_intent(req.message, components, username)
        components["memory"].add(req.message, reply)
        components["logger"].log("chat", f"User: {req.message} | Leo: {reply}")
        if leo_db.connected:
            leo_db.log_activity(username, "chat",
                                f"User: {req.message} | Leo: {reply}")
    except Exception as e:
        reply = f"I encountered an error: {str(e)[:100]}. Please try again."
        intent = "error"

    return ChatResponse(username=username, message=req.message,
                        reply=reply, intent=intent,
                        timestamp=datetime.now().isoformat())

# ── LIST ALL PATIENTS ─────────────────────────────────────
@app.get("/patients", tags=["User"])
def list_patients():
    """
    Returns all registered patients from MongoDB + local files.
    Used by the login page to show available usernames.
    """
    usernames = set()

    # From MongoDB
    if leo_db.connected:
        try:
            for u in leo_db.list_patients():
                usernames.add(u.lower())
        except Exception as e:
            print(f"[WARN] list_patients MongoDB: {e}")

    # From local files
    patients_dir = BASE_DIR / "data" / "patients"
    if patients_dir.exists():
        for folder in patients_dir.iterdir():
            if folder.is_dir():
                pf = folder / "profile.json"
                if pf.exists():
                    usernames.add(folder.name.lower())

    # Get names for each username
    result = []
    for u in sorted(usernames):
        name = u
        try:
            # Try file first
            pf = BASE_DIR / "data" / "patients" / u / "profile.json"
            if pf.exists():
                d = json.loads(pf.read_text(encoding="utf-8"))
                name = d.get("personal", {}).get("name", u)
            elif leo_db.connected:
                d = leo_db.get_patient(u)
                if d:
                    name = d.get("personal", {}).get("name", u)
        except Exception:
            pass
        result.append({"username": u, "name": name})

    return {"patients": result, "count": len(result)}


# ── PROFILE ───────────────────────────────────────────────
@app.get("/user/{username}/profile", tags=["User"])
def get_profile(username: str):
    """
    Fetch patient profile.
    Priority: 1) Leo cache  2) Local file  3) MongoDB (including username variants)
    """
    username = username.lower().strip()

    # 1 — Leo in-memory cache
    if LEO_BRAIN_AVAILABLE and username in _user_cache:
        c = _user_cache[username]
        if c.get("profile") and c["profile"].data.get("personal", {}).get("name"):
            return {"username": username, "profile": c["profile"].data}

    # 2 — Local file (only if file actually exists)
    file_data = _file_get_profile(username)
    if file_data and file_data.get("personal", {}).get("name"):
        return {"username": username, "profile": file_data}

    # 3 — MongoDB  (try exact username AND common variations)
    if leo_db.connected:
        candidates = [username]
        # e.g. "ali" → also try "muhammad_ali" style variants from DB
        if "_" not in username:
            try:
                for u in leo_db.list_patients():
                    if u.endswith("_" + username) or u.startswith(username + "_"):
                        candidates.append(u)
            except Exception:
                pass

        best_profile = None
        for candidate in candidates:
            try:
                mongo_data = leo_db.get_patient(candidate)
                if mongo_data and isinstance(mongo_data, dict):
                    if mongo_data.get("personal", {}).get("name"):
                        if best_profile is None:
                            best_profile = mongo_data
                        else:
                            # Merge: take whichever has more data in each field
                            for field in ["medications", "emergency_contacts", "contacts", "active_zones"]:
                                existing = best_profile.get(field, [])
                                candidate_val = mongo_data.get(field, [])
                                if len(candidate_val) > len(existing):
                                    best_profile[field] = candidate_val
                            # Merge personal info
                            for key in ["age", "gender", "condition", "phone"]:
                                if not best_profile.get("personal", {}).get(key):
                                    best_profile.setdefault("personal", {})[key] = (
                                        mongo_data.get("personal", {}).get(key, ""))
            except Exception as e:
                print(f"[WARN] MongoDB get_profile ({candidate}): {e}")

        if best_profile:
            try: _file_save_profile(username, best_profile)
            except Exception: pass
            return {"username": username, "profile": best_profile}

    raise HTTPException(404, detail=f"User '{username}' not found. Register first.")

@app.put("/user/{username}/profile", tags=["User"])
def update_profile(username: str, update: ProfileUpdate):
    username = username.lower().strip()
    existing = _file_get_profile(username) or _default_profile(username)
    patch = update.model_dump(exclude_none=True)
    for field, value in patch.items():
        if isinstance(value, dict) and isinstance(existing.get(field), dict):
            existing[field].update(value)
        else:
            existing[field] = value
    _file_save_profile(username, existing)
    if LEO_BRAIN_AVAILABLE and username in _user_cache:
        try:
            c = _user_cache[username]
            if c.get("profile"):
                c["profile"].data.update(existing)
                c["profile"].save()
        except Exception as e:
            print(f"[WARN] Leo cache sync: {e}")
    if leo_db.connected:
        try: leo_db.save_patient(existing)
        except: pass
    return {"username": username, "status": "updated", "profile": existing}

# ── LOGS ─────────────────────────────────────────────────
@app.get("/user/{username}/logs", tags=["User"])
def get_logs(username: str, category: Optional[str] = None,
             severity: Optional[str] = None, limit: int = 100):
    username = username.lower().strip()
    # MongoDB first (richest data)
    if leo_db.connected:
        try:
            from pymongo import DESCENDING as DESC
            query = {"patient": username}
            if category: query["category"] = category
            if severity: query["severity"] = severity
            entries = []
            for l in leo_db._col("activity_logs").find(query).sort(
                    "timestamp", DESC).limit(limit):
                entries.append({
                    "category":  l.get("category", "info"),
                    "severity":  l.get("severity", "info"),
                    "message":   l.get("content", l.get("message", "")),
                    "timestamp": _fmt_dt(l.get("timestamp")),
                    "date":      l.get("date", ""),
                    "time":      l.get("time", ""),
                })
            return {"username": username,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "logs": entries}
        except Exception as e:
            print(f"[WARN] MongoDB logs: {e}")
    # Leo cache fallback
    if LEO_BRAIN_AVAILABLE and username in _user_cache:
        c = _user_cache[username]
        if c.get("logger"):
            entries = c["logger"].entries
            if category: entries = [e for e in entries if e.get("category")==category]
            if severity:  entries = [e for e in entries if e.get("severity")==severity]
            return {"username": username,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "logs": entries}
    # File fallback
    entries = _file_get_logs(username)
    return {"username": username,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "logs": entries}

# ── MEMORY ───────────────────────────────────────────────
@app.get("/user/{username}/memory", tags=["User"])
def get_memory(username: str, last_n: int = 10):
    if not LEO_BRAIN_AVAILABLE:
        return {"username": username, "history": [], "note": _leo_status_msg}
    c = _get_user_components(username)
    return {"username": username, "history": c["memory"].history[-last_n*2:]}

@app.delete("/user/{username}/memory", tags=["User"])
def clear_memory(username: str):
    if not LEO_BRAIN_AVAILABLE:
        raise HTTPException(503, _leo_status_msg)
    c = _get_user_components(username)
    c["memory"].history = []; c["memory"].save()
    return {"message": f"Memory cleared for {username}."}

# ── MEDICATIONS ───────────────────────────────────────────
@app.post("/user/{username}/medications", tags=["Medications"])
def set_medications(username: str, medications: list[MedicationItem]):
    username = username.lower().strip()
    existing = _file_get_profile(username) or _default_profile(username)
    existing["medications"] = [m.model_dump() for m in medications]
    _file_save_profile(username, existing)
    if leo_db.connected:
        try: leo_db.save_patient(existing)
        except: pass
    return {"message": "Medications updated.",
            "medications": existing["medications"]}

@app.get("/medications/{username}/due", tags=["Medications"])
def medications_due(username: str):
    username = username.lower().strip()
    now = datetime.now().strftime("%H:%M")
    profile = _file_get_profile(username) or _default_profile(username)
    due = [m for m in profile.get("medications", []) if m.get("time")==now]
    return {"username": username, "time": now, "due": due}

# ── EMERGENCY ─────────────────────────────────────────────
@app.post("/emergency/alert", tags=["Emergency"])
def emergency_alert(req: EmergencyAlertRequest, background_tasks: BackgroundTasks):
    username = req.username.lower().strip()
    level    = req.level or "fall"
    message  = req.reason or req.message or level
    if level not in {"critical","fall","confusion"}: level = "fall"
    profile  = _file_get_profile(username) or _default_profile(username)
    contacts = profile.get("emergency_contacts", [])
    name     = profile.get("personal", {}).get("name", username)
    names    = ", ".join(c.get("name","?") for c in contacts) if contacts else "no contacts saved"
    response_text = f"Emergency alert for {name}! Notifying: {names}. Level: {level}."
    print(f"[EMERGENCY] {username} | {level} | {message}")
    # File log
    try:
        pd = PatientDirs(username); lf = pd.log_file()
        logs = []
        if lf.exists():
            try:
                raw = json.loads(lf.read_text(encoding="utf-8"))
                logs = raw if isinstance(raw, list) else raw.get("entries", [])
            except: pass
        logs.append({"category":"emergency","severity":"critical",
                     "message":message,"timestamp":datetime.now().isoformat()})
        lf.write_text(json.dumps(logs,indent=2,ensure_ascii=False),encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Emergency log: {e}")
    # MongoDB
    if leo_db.connected:
        try:
            leo_db.log_activity(username,"emergency",message,severity="critical")
            if level=="fall":
                leo_db.log_fall(username,score=0,reason=message,state="FALL")
        except: pass
    return {"username":username,"level":level,"message":response_text,
            "contacts":contacts,"timestamp":datetime.now().isoformat()}

# ══════════════════════════════════════════════════════════
# ★ NEW ENDPOINTS — Rich MongoDB data for Flutter app
# ══════════════════════════════════════════════════════════

@app.get("/user/{username}/summary", tags=["Dashboard"])
def get_summary(username: str):
    """
    Rich summary card data pulled from MongoDB.
    Returns: falls_today, total_falls, total_sessions, last_activity, last_fall.
    Used by Flutter Home screen stats cards.
    """
    username = username.lower().strip()
    if leo_db.connected:
        try:
            data = leo_db.get_patient_summary(username)
            return data if data else _empty_summary(username)
        except Exception as e:
            print(f"[WARN] summary: {e}")
    return _empty_summary(username)

def _empty_summary(username):
    return {"patient": username, "falls_today": 0, "total_falls": 0,
            "total_sessions": 0, "last_activity": None, "last_fall": None,
            "last_fall_clip": None}

@app.get("/user/{username}/falls", tags=["Dashboard"])
def get_falls(username: str, limit: int = 30):
    """
    All fall events for this patient from MongoDB.
    Includes: date, time, reason, posture, score, state, clip_path.
    Used by Flutter Detection / Alerts screens.
    """
    username = username.lower().strip()
    falls = []
    if leo_db.connected:
        try:
            from pymongo import DESCENDING as DESC
            for f in leo_db._col("fall_events").find(
                    {"patient": username}).sort("timestamp", DESC).limit(limit):
                falls.append({
                    "date":      f.get("date", ""),
                    "time":      f.get("time", ""),
                    "score":     f.get("score", 0),
                    "reason":    f.get("reason", ""),
                    "posture":   f.get("posture", ""),
                    "state":     f.get("state", ""),
                    "clip_path": f.get("clip_path"),
                    "timestamp": _fmt_dt(f.get("timestamp")),
                })
        except Exception as e:
            print(f"[WARN] falls: {e}")
    return {"username": username, "count": len(falls), "falls": falls}

@app.get("/user/{username}/sessions", tags=["Dashboard"])
def get_sessions(username: str, limit: int = 10):
    """
    Monitoring sessions from MongoDB.
    Includes: start_time, end_time, fall_count, status, recording_path.
    Used by Flutter Alerts screen Sessions tab.
    """
    username = username.lower().strip()
    sessions = []
    if leo_db.connected:
        try:
            from pymongo import DESCENDING as DESC
            for s in leo_db._col("sessions").find(
                    {"patient": username}).sort("start_time", DESC).limit(limit):
                sessions.append({
                    "start_time":     _fmt_dt(s.get("start_time")),
                    "end_time":       _fmt_dt(s.get("end_time")),
                    "fall_count":     s.get("fall_count", 0),
                    "status":         s.get("status", ""),
                    "recording_path": s.get("recording_path", ""),
                })
        except Exception as e:
            print(f"[WARN] sessions: {e}")
    return {"username": username, "count": len(sessions), "sessions": sessions}

# ── VISION ────────────────────────────────────────────────
LYING_AR_THRESHOLD  = 1.2
FALL_CONF_THRESHOLD = 0.40

@app.post("/vision/analyze-frame", response_model=FallStatusResponse, tags=["Vision"])
def analyze_frame(req: FrameAnalysisRequest):
    global _latest_jpeg, _safe_zones, _current_patient
    if not YOLO_AVAILABLE: raise HTTPException(503, "YOLO models not loaded.")
    try:
        img_bytes = base64.b64decode(req.frame_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None: raise ValueError("imdecode returned None")
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {e}")
    frame = cv2.resize(frame, (640, 480))
    # Track current patient and reload their zones if changed
    username = (req.username or "").lower().strip()
    if username and username != _current_patient:
        _current_patient = username
        new_zones = _load_zones(username)
        if new_zones:
            _safe_zones = new_zones
    fall_results    = fall_model(frame, verbose=False)
    posture_results = posture_model(frame, verbose=False)
    fall_detected=False; fall_conf=0.0; fall_box=None
    for r in fall_results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf >= FALL_CONF_THRESHOLD:
                fall_detected=True; fall_conf=max(fall_conf,conf)
                fall_box=[int(v) for v in box.xyxy[0].tolist()]
    posture_label="unknown"; posture_box=None; best_conf=0.0
    for r in posture_results:
        for box in r.boxes:
            conf=float(box.conf[0]); label=posture_model.names[int(box.cls[0])]
            if conf>best_conf:
                best_conf=conf; posture_label=label
                posture_box=[int(v) for v in box.xyxy[0].tolist()]
    if posture_box:
        ar=_get_aspect_ratio(posture_box)
        if ar<LYING_AR_THRESHOLD and posture_label not in("lying","fall"):
            posture_label="lying"
    on_safe_zone=_person_in_safe_zone(fall_box or posture_box,_safe_zones)
    if on_safe_zone: fall_detected=False
    state=("FALL" if fall_detected else
           ("LYING"if posture_label=="lying" else
            ("STANDING" if posture_label=="standing" else
             ("SITTING" if posture_label=="sitting" else "UNKNOWN"))))
    result=FallStatusResponse(state=state,fall_detected=fall_detected,
        on_safe_zone=on_safe_zone,posture=posture_label,
        confidence=round(fall_conf,3),timestamp=datetime.now().isoformat())
    with _fall_lock: _fall_state.update(result.model_dump())

    # Store annotated frame as JPEG for live streaming
    try:
        annotated = frame.copy()
        color = (0,0,220) if fall_detected else (0,200,0)
        label = f"{result.state}  conf:{result.confidence:.2f}"
        cv2.putText(annotated, label, (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        if result.posture != "unknown":
            cv2.putText(annotated, f"Posture: {result.posture}", (10,60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,200,0), 2)
        # Draw safe zones on frame
        for z in _safe_zones:
            bx = [int(v) for v in z["box"]]
            if len(bx) == 4:
                x1,y1,x2,y2 = bx
                cv2.rectangle(annotated,(x1,y1),(x2,y2),(255,165,0),2)
                cv2.putText(annotated, z["type"].upper(), (x1,y1-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,165,0), 1)
        _, jpeg_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
        with _frame_lock:
            _latest_jpeg = jpeg_buf.tobytes()
    except Exception: pass

    if fall_detected and req.username and LEO_BRAIN_AVAILABLE:
        try:
            c=_get_user_components(req.username)
            c["logger"].log("fall",f"Fall — conf:{fall_conf:.2f}",severity="critical")
        except: pass
    return result

@app.get("/vision/status", response_model=FallStatusResponse, tags=["Vision"])
def vision_status():
    with _fall_lock: return FallStatusResponse(**_fall_state)

@app.post("/vision/zones", tags=["Vision"])
def set_zones(payload: ZonesPayload):
    global _safe_zones
    _safe_zones=[{"type":z.type,"box":tuple(z.box)} for z in payload.zones]
    _save_zones(_safe_zones)
    return {"message":f"{len(_safe_zones)} zone(s) saved.","zones":payload.zones}

@app.get("/vision/zones", tags=["Vision"])
def get_zones():
    # Return in-memory zones (may be patient-specific if brain is running)
    all_zones = _safe_zones
    if not all_zones and _current_patient:
        all_zones = _load_zones(_current_patient)
    return {"zones": [{"type": z["type"], "box": list(z["box"])} for z in all_zones]}


@app.get("/user/{username}/videos", tags=["Dashboard"])
def get_videos(username: str):
    """
    List all saved video recordings for this patient from disk.
    Returns: date, filename, path, type (fall/recording), size_mb.
    """
    username = username.lower().strip()
    videos = []
    folder = BASE_DIR / "data" / "patients" / username / "videos"
    if folder.exists():
        try:
            for date_dir in sorted(folder.iterdir(), reverse=True):
                if not date_dir.is_dir():
                    continue
                for vid in sorted(date_dir.glob("*.avi"), reverse=True):
                    videos.append({
                        "date":      date_dir.name,
                        "filename":  vid.name,
                        "path":      str(vid),
                        "type":      "fall" if vid.name.startswith("fall_") else "recording",
                        "size_mb":   round(vid.stat().st_size / (1024 * 1024), 1),
                    })
        except Exception as e:
            print(f"[WARN] videos listing error: {e}")
    return {"username": username, "count": len(videos), "videos": videos}


@app.get("/video/stream", tags=["Videos"])
def stream_video(path: str, request: Request):
    """
    Stream a saved video file from local disk to the browser / Flutter app.
    Supports HTTP Range requests (needed for seek/scrub in browser video player).

    Usage:  GET /video/stream?path=D:\\...\\fall_clip.avi
    Flutter: open  http://localhost:8000/video/stream?path=<encoded_path>
    """
    video_path = Path(path)

    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {path}")

    suffix = video_path.suffix.lower()
    if suffix not in ('.avi', '.mp4', '.mkv', '.mov', '.webm'):
        raise HTTPException(status_code=400, detail="Not a supported video file")

    content_type_map = {
        '.avi':  'video/x-msvideo',
        '.mp4':  'video/mp4',
        '.mkv':  'video/x-matroska',
        '.mov':  'video/quicktime',
        '.webm': 'video/webm',
    }
    content_type = content_type_map.get(suffix, 'application/octet-stream')
    file_size = video_path.stat().st_size

    # ── Range request support (browser seek/scrub) ────────
    range_header = request.headers.get("range")
    if range_header:
        try:
            range_val  = range_header.strip().lower().replace("bytes=", "")
            start, end = range_val.split("-")
            start = int(start)
            end   = int(end) if end else file_size - 1
            end   = min(end, file_size - 1)
            length = end - start + 1

            def iter_chunk():
                with open(video_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            headers = {
                "Content-Range":  f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges":  "bytes",
                "Content-Length": str(length),
                "Content-Type":   content_type,
            }
            return StreamingResponse(iter_chunk(), status_code=206, headers=headers)
        except Exception as e:
            print(f"[WARN] Range request error: {e}")

    # ── Full file response ────────────────────────────────
    return FileResponse(
        path=str(video_path),
        media_type=content_type,
        headers={"Accept-Ranges": "bytes",
                 "Content-Length": str(file_size)},
    )


@app.get("/video/thumbnail", tags=["Videos"])
def video_thumbnail(path: str):
    """
    Extract a JPEG thumbnail from a video file using OpenCV.
    Returns a JPEG image of the first frame.
    Falls back to a 1x1 placeholder if extraction fails.
    """
    import base64, io
    video_path = Path(path)
    placeholder = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
        b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
        b'\x1b@Roh\xff\xd9'
    )
    if not video_path.exists():
        from fastapi.responses import Response
        return Response(content=placeholder, media_type="image/jpeg")
    try:
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            frame = cv2.resize(frame, (320, 240))
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            from fastapi.responses import Response
            return Response(content=buf.tobytes(), media_type="image/jpeg")
    except Exception as e:
        print(f"[WARN] Thumbnail error: {e}")
    from fastapi.responses import Response
    return Response(content=placeholder, media_type="image/jpeg")


# ── LIVE VIDEO STREAMING ─────────────────────────────────────
@app.get("/video/live-frame", tags=["Vision"])
def live_frame_jpeg():
    """
    Returns the latest camera frame as JPEG.
    Flutter polls this every ~150ms to show live video.
    Falls back to a placeholder if camera is not running.
    """
    from fastapi.responses import Response
    with _frame_lock:
        jpeg = _latest_jpeg

    if not jpeg:
        # Return a 1x1 dark placeholder
        placeholder = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07"
            b"\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c"
            b"\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
            b"\x1d\x1a\x1c\x1c $.' ",#\x1c\x1c(7),01444\x1f\'9=82<"
            b".342\x1e\x1b@Roh\xff\xd9"
        )
        return Response(content=placeholder, media_type="image/jpeg",
                       headers={"Cache-Control": "no-cache, no-store"})

    return Response(content=jpeg, media_type="image/jpeg",
                   headers={"Cache-Control": "no-cache, no-store",
                            "Access-Control-Allow-Origin": "*"})


@app.get("/video/live-stream", tags=["Vision"])
async def live_mjpeg_stream():
    """
    MJPEG stream — open in browser or <img> tag for live video.
    URL: http://localhost:8000/video/live-stream
    """
    import asyncio
    from fastapi.responses import StreamingResponse as SR

    async def generate():
        while True:
            with _frame_lock:
                jpeg = _latest_jpeg
            if jpeg:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + jpeg + b"\r\n")
            await asyncio.sleep(0.1)   # 10fps

    return SR(generate(),
              media_type="multipart/x-mixed-replace;boundary=frame",
              headers={"Access-Control-Allow-Origin": "*"})


@app.get("/user/{username}/zones", tags=["Vision"])
def get_user_zones(username: str):
    """
    Get safe zones for a specific patient.
    Reads from data/patients/{username}/safe_zones.json first,
    then falls back to global safe_zones.json.
    """
    username = username.lower().strip()
    zones = _load_zones(username)
    return {"username": username, "count": len(zones),
            "zones": [{"type": z["type"], "box": list(z["box"])} for z in zones]}



@app.post("/video/push-frame", tags=["Vision"])
async def push_frame_direct(request: Request):
    """
    Called by final_monitering_brain.py every frame.
    Receives the FULLY ANNOTATED frame (YOLO boxes + banner + zones already drawn)
    plus the current detection state. No YOLO needed here — monitoring brain
    already did all the heavy lifting.

    This is the bridge between the monitoring brain and the Flutter app:
      monitoring brain → POST /video/push-frame → _latest_jpeg → GET /video/live-frame → Flutter
    """
    global _latest_jpeg
    try:
        data = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    # ── Store annotated JPEG ──────────────────────────────────────
    jpeg_b64 = data.get("frame_b64", "")
    if jpeg_b64:
        try:
            jpeg_bytes = base64.b64decode(jpeg_b64)
            with _frame_lock:
                _latest_jpeg = jpeg_bytes
        except Exception as e:
            print(f"[WARN] push-frame decode error: {e}")

    # ── Update live fall state from monitoring brain ──────────────
    state         = data.get("state",          "UNKNOWN")
    posture       = data.get("posture",         "unknown")
    fall_detected = bool(data.get("fall_detected", False))
    on_safe_zone  = bool(data.get("on_safe_zone",  False))
    confidence    = float(data.get("confidence",   0.0))

    with _fall_lock:
        _fall_state.update({
            "state":         state,
            "fall_detected": fall_detected,
            "on_safe_zone":  on_safe_zone,
            "posture":       posture,
            "confidence":    confidence,
            "timestamp":     datetime.now().isoformat(),
        })

    # ── Log fall to MongoDB if it's a new fall ─────────────────────
    patient = data.get("patient", "unknown").lower().strip()
    if fall_detected and patient and leo_db.connected:
        try:
            leo_db.log_activity(patient, "fall",
                                f"Fall via monitoring brain — state:{state}",
                                severity="critical")
        except Exception:
            pass

    return {"status": "ok", "state": state}

# ── STARTUP / SHUTDOWN ────────────────────────────────────
@app.on_event("startup")
def on_startup():
    print("\n╔══════════════════════════════════════════╗")
    print("║   LEO API v2 — Starting up              ║")
    print("╚══════════════════════════════════════════╝\n")
    print(f"  YOLO      : {'OK' if YOLO_AVAILABLE else 'Not loaded'}")
    print(f"  GPU       : {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    print(f"  MongoDB   : {'Connected' if leo_db.connected else 'Offline'}")
    print(f"  Safe zones: {len(_safe_zones)} loaded")
    print(f"  Leo Brain : Loading in background...\n")
    threading.Thread(target=_background_leo_loader, daemon=True, name="LeoLoader").start()

@app.on_event("shutdown")
def on_shutdown():
    if leo_db.connected: leo_db.close()
    print("\n[LEO API] Shutdown complete.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)