"""
LEO - AI-Powered Home Assistant for the Elderly
FYP Project | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman

Improvements over base version:
  - Modular class-based architecture
  - Robust intent routing with fallback chain
  - Medication reminders with snooze tracking
  - Inactivity monitoring (tracks last interaction time)
  - Routine logging to JSON file
  - Fall/emergency detection with severity levels
  - Voice-ready response formatting (short, natural sentences)
  - Caregiver alert stub (Twilio-ready)
  - Better LLM prompting with elderly-safe guardrails
  - Clean startup / shutdown handling

v2 Updates:
  - Uses patient_storage.py  → organized data/patients/{name}/ folders
  - Uses patait_info_collector → patient login/setup at startup
  - Uses mongo_storage        → all logs + memory saved to MongoDB too

v3 Updates:
  - Voice input via Whisper  → speak OR type to Leo
  - VoiceInput class         → mic capture + Whisper transcription
  - Mode toggle              → press V to switch voice/text anytime
"""

import os
import json
import joblib
import torch
import warnings
import cv2
import time
import threading
import tempfile
import queue
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# ── Voice imports (optional — graceful fallback if not installed) ──
try:
    import whisper as _whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("[Voice] whisper not installed. Run:  pip install openai-whisper")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[Voice] pyaudio not installed. Run:  pip install pyaudio")

try:
    from kokoro import KPipeline as _KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False
    print("[TTS] kokoro not installed. Run:  pip install kokoro")

# ─────────────────────────────────────────────
# ENV / WARNINGS
# ─────────────────────────────────────────────
os.environ['TRANSFORMERS_OFFLINE']   = "1"
os.environ['HF_DATASETS_OFFLINE']    = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore")

from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# ── New FYP modules ───────────────────────────
from patient_storage       import PatientDirs
from patait_info_collector import AIBrainProfile
from mongo_storage         import leo_db
from twilio_alerts         import twilio_alerts

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
MODEL_PATH = Path("D:/Python/FYP/models/qwen0.5b")

# Legacy dirs kept for backward compatibility
USERS_DIR  = BASE_DIR / "users"
MEMORY_DIR = BASE_DIR / "memory"
LOGS_DIR   = BASE_DIR / "logs"
for d in [USERS_DIR, MEMORY_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — VISION MODULE  (unchanged)
# ═══════════════════════════════════════════════════════════════════
class LeoVision:
    """
    Lightweight face/person detection using OpenCV Haar cascades.
    Can be extended with MediaPipe BlazePose for fall detection.
    """

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.body_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_fullbody.xml'
        )

    def analyze_frame(self, frame) -> dict:
        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces  = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        bodies = self.body_cascade.detectMultiScale(gray, 1.05, 3)

        result = {
            "faces":          int(len(faces)),
            "bodies":         int(len(bodies)),
            "fall_suspected": False,
            "message":        None
        }
        if len(faces) > 0:
            result["message"] = f"I can see {len(faces)} person(s) in front of me."
        if len(bodies) > 0 and len(faces) == 0:
            result["fall_suspected"] = True
            result["message"] = "I notice someone may be on the ground. Are you okay?"
        return result

    def get_text_description(self, frame) -> str | None:
        return self.analyze_frame(frame)["message"]


# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — USER PROFILE & MEMORY
# Updated: loads from data/patients/{name}/profile.json
#          saves memory to data/patients/{name}/memory/ + MongoDB
# ═══════════════════════════════════════════════════════════════════
class UserProfile:
    DEFAULTS = {
        "personal":           {"name": "User"},
        "emergency_contacts": [],
        "contacts":           [],
        "medications":        [],
        "routine":            {},
        "active_zones":       [],
        "preferences":        {
            "response_style": "simple",
            "language":       "english"
        }
    }

    def __init__(self, user_name: str, preloaded_data: dict = None):
        self.user_name = user_name.lower().strip()
        self.pd        = PatientDirs(self.user_name)

        if preloaded_data:
            # Profile already loaded by patait_info_collector — use it directly
            self.data = preloaded_data
            for k, v in self.DEFAULTS.items():
                self.data.setdefault(k, v)
        else:
            self.data = self._load()

    def _load(self) -> dict:
        # Try new patient folder first
        if self.pd.profile_file.exists():
            with open(self.pd.profile_file) as f:
                loaded = json.load(f)
            for k, v in self.DEFAULTS.items():
                loaded.setdefault(k, v)
            return loaded

        # Fallback: old users/ folder
        old_path = USERS_DIR / f"{self.user_name}.json"
        if old_path.exists():
            print(f"[Profile] Loading from legacy path: {old_path}")
            with open(old_path) as f:
                loaded = json.load(f)
            for k, v in self.DEFAULTS.items():
                loaded.setdefault(k, v)
            return loaded

        print(f"[Profile] No file for '{self.user_name}'. Using defaults.")
        return dict(self.DEFAULTS)

    def save(self):
        # Save to new organized folder
        self.pd.profile_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pd.profile_file, "w") as f:
            json.dump(self.data, f, indent=2)

    # ── Convenience accessors (unchanged) ────────
    @property
    def name(self) -> str:
        return self.data["personal"].get("name", self.user_name)

    @property
    def emergency_contacts(self) -> list:
        return self.data.get("emergency_contacts", [])

    @property
    def contacts(self) -> list:
        return self.data.get("contacts", [])

    @property
    def medications(self) -> list:
        return self.data.get("medications", [])

    @property
    def all_contacts(self) -> list:
        return self.contacts + self.emergency_contacts


class ConversationMemory:
    MAX_TURNS = 20

    def __init__(self, user_name: str):
        self.user_name = user_name
        self.pd        = PatientDirs(user_name)
        # New path: data/patients/{name}/memory/chat_{date}.json
        self.file_path = self.pd.memory_file()
        self.history: list = self._load()

    def _load(self) -> list:
        # Try MongoDB first
        if leo_db.connected:
            hist = leo_db.get_memory(self.user_name)
            if hist:
                return hist
        # Fallback: local file (new path)
        if self.file_path.exists():
            with open(self.file_path) as f:
                return json.load(f)
        # Fallback: old memory folder
        old = MEMORY_DIR / f"{self.user_name}_chat.json"
        if old.exists():
            with open(old) as f:
                return json.load(f)
        return []

    def save(self):
        trimmed = self.history[-(self.MAX_TURNS * 2):]
        # Save to new organized folder
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w") as f:
            json.dump(trimmed, f, indent=2)
        # Save to MongoDB
        if leo_db.connected:
            leo_db.save_memory(self.user_name, trimmed)

    def add(self, user_text: str, bot_text: str):
        self.history.append({"role": "user",      "content": user_text})
        self.history.append({"role": "assistant", "content": bot_text})
        self.save()

    def recent_user_messages(self, n=3) -> list[str]:
        return [m["content"] for m in self.history if m["role"] == "user"][-n:]

    def as_messages(self) -> list[dict]:
        return self.history[-(self.MAX_TURNS * 2):]


# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — ACTIVITY LOGGER
# Updated: saves to data/patients/{name}/logs/{date}.json + MongoDB
# ═══════════════════════════════════════════════════════════════════
class ActivityLogger:
    """Log all interactions for caregiver dashboard / daily report."""

    def __init__(self, user_name: str):
        self.user_name = user_name
        self.pd        = PatientDirs(user_name)
        # New path: data/patients/{name}/logs/{date}.json
        self.log_file  = self.pd.log_file()
        self.entries: list = self._load()

    def _load(self) -> list:
        if self.log_file.exists():
            with open(self.log_file) as f:
                return json.load(f)
        return []

    def log(self, category: str, content: str, severity: str = "info"):
        entry = {
            "time":     datetime.now().strftime("%H:%M:%S"),
            "category": category,
            "content":  content,
            "severity": severity
        }
        self.entries.append(entry)
        # Save to local file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w") as f:
            json.dump(self.entries, f, indent=2)
        # Save to MongoDB
        if leo_db.connected:
            leo_db.log_activity(self.user_name, category,
                                content, severity=severity)

    def print_daily_summary(self):
        cats = {}
        for e in self.entries:
            cats.setdefault(e["category"], 0)
            cats[e["category"]] += 1
        print("\nToday's Activity Summary:")
        for cat, count in cats.items():
            print(f"   {cat}: {count} event(s)")


# ═══════════════════════════════════════════════════════════════════
# SECTION 4 — INACTIVITY MONITOR  (unchanged)
# ═══════════════════════════════════════════════════════════════════
class InactivityMonitor:
    THRESHOLD_MINUTES = 30

    def __init__(self, user_name: str, alert_callback):
        self.user_name      = user_name
        self.alert_callback = alert_callback
        self.last_active    = time.time()
        self._stop_event    = threading.Event()
        self._thread        = threading.Thread(target=self._run, daemon=True)

    def start(self):  self._thread.start()
    def stop(self):   self._stop_event.set()

    def heartbeat(self):
        self.last_active = time.time()

    def _run(self):
        while not self._stop_event.is_set():
            time.sleep(60)
            elapsed = (time.time() - self.last_active) / 60
            if elapsed >= self.THRESHOLD_MINUTES:
                self.alert_callback(
                    f"{self.user_name} has been inactive for {int(elapsed)} minutes."
                )
                self.last_active = time.time()


# ═══════════════════════════════════════════════════════════════════
# SECTION 5 — INTENT DETECTION HELPERS  (unchanged)
# ═══════════════════════════════════════════════════════════════════
class IntentMatcher:
    EMERGENCY_KEYWORDS = [
        "ambulance", "can't breathe", "cannot breathe", "not breathing",
        "chest pain", "heart attack", "stroke", "unconscious", "help me",
        "emergency", "i fell", "i'm falling"
    ]
    FALL_KEYWORDS     = ["fell", "fall", "slipped", "hit my head", "on the floor"]
    CONFUSED_KEYWORDS = ["dizzy", "spinning", "confused", "lost", "disoriented"]
    MEDICATION_WORDS  = ["medicine", "medication", "pill", "tablet", "dose",
                         "drug", "prescription", "refill", "took", "missed", "forgot"]
    CALL_WORDS        = ["call", "phone", "contact", "reach", "talk to", "ring"]
    MEMORY_WORDS      = ["what did i say", "earlier", "before", "remember what",
                         "what did we talk", "previous"]
    GREETING_WORDS    = ["hello", "hi", "hey", "good morning", "good evening",
                         "good night", "how are you"]
    EMOTION_MAP = {
        "lonely":   ["lonely", "alone", "no one to talk", "nobody cares"],
        "sad":      ["sad", "depressed", "unhappy", "feeling low", "crying"],
        "anxious":  ["anxious", "worried", "nervous", "panic", "scared", "afraid"],
        "tired":    ["tired", "exhausted", "weak", "no energy"],
        "hopeless": ["want to die", "end my life", "no reason to live",
                     "kill myself", "not worth living"]
    }

    @staticmethod
    def _contains(text: str, keywords: list) -> bool:
        t = text.lower()
        return any(k in t for k in keywords)

    def detect_emergency_level(self, text: str) -> str | None:
        if self._contains(text, self.EMERGENCY_KEYWORDS): return "critical"
        if self._contains(text, self.FALL_KEYWORDS):      return "fall"
        if self._contains(text, self.CONFUSED_KEYWORDS):  return "confusion"
        return None

    def detect_emotion(self, text: str) -> str | None:
        for emotion, keywords in self.EMOTION_MAP.items():
            if self._contains(text, keywords):
                return emotion
        return None

    def is_medication(self, text)     -> bool: return self._contains(text, self.MEDICATION_WORDS)
    def is_call_request(self, text)   -> bool: return self._contains(text, self.CALL_WORDS)
    def is_memory_question(self, text) -> bool: return self._contains(text, self.MEMORY_WORDS)
    def is_greeting(self, text: str) -> bool:
        """
        True ONLY for short pure greetings with no request mixed in.
        "hello" → True | "hello tell me a story" → False (→ LLM)
        """
        words = text.strip().split()
        if len(words) > 6:
            return False
        REQUEST_INDICATORS = {
            "tell","explain","what","how","why","when","where","who","which",
            "show","give","find","help","make","write","read","play","sing",
            "call","remind","medicine","story","joke","news","weather","time",
            "do","can","could","would","should","is","are","will","please",
            "want","need","like","get","take","bring","talk","speak","say",
        }
        for w in words[1:]:
            if w.lower().rstrip("?!.,") in REQUEST_INDICATORS:
                return False
        return self._contains(text, self.GREETING_WORDS)


# ═══════════════════════════════════════════════════════════════════
# SECTION 6 — DOMAIN HANDLERS  (unchanged)
# ═══════════════════════════════════════════════════════════════════
class EmergencyHandler:
    @staticmethod
    def respond(level: str, user_name: str, contacts: list) -> str:
        names = ", ".join(c["name"] for c in contacts) if contacts else "your emergency contacts"
        if level == "critical":
            return (
                f"EMERGENCY! I am alerting {names} right now. "
                f"Please stay calm, {user_name}. Help is on the way. "
                f"If you can, call 1122 or 115 for an ambulance."
            )
        elif level == "fall":
            return (
                f"It sounds like you may have fallen, {user_name}. "
                f"Please do not try to get up too quickly. "
                f"I am notifying {names} immediately."
            )
        elif level == "confusion":
            return (
                f"You sound confused, {user_name}. Please sit or lie down safely. "
                f"I am letting {names} know so they can check on you."
            )
        return f"Emergency detected! Contacting {names} now."


class MedicationHandler:
    def respond(self, text: str, medications: list) -> str:
        now = datetime.now().strftime("%H:%M")
        t   = text.lower()

        if not medications:
            return "I don't have any medication schedule saved for you. Please ask your caregiver to set one up."

        if any(w in t for w in ["overdose", "too much", "extra dose", "twice already"]):
            return ("This sounds like a possible medication overdose. "
                    "Please call your doctor or emergency services immediately. "
                    "Do not take any more medicine right now.")

        if any(w in t for w in ["forgot", "missed", "skip"]):
            return ("If you missed a dose, take it as soon as you remember "
                    "unless it is almost time for your next dose. "
                    "When in doubt, call your doctor. Never double up.")

        due = [m["medicine"] for m in medications if m.get("time") == now]
        if due:
            return f"It is time to take: {', '.join(due)}. Please take it with a glass of water."

        if any(w in t for w in ["remaining", "left", "how much", "run out"]):
            info = [f"{m['medicine']}: {m.get('quantity_left', 'unknown')} remaining"
                    for m in medications]
            return "Medication stock: " + "; ".join(info)

        if any(w in t for w in ["when", "next", "what time"]):
            future = sorted(
                [m for m in medications if m.get("time", "23:59") > now],
                key=lambda x: x.get("time", "23:59")
            )
            if future:
                m = future[0]
                return f"Your next medicine is {m['medicine']} at {m['time']}."
            return "You have no more medicines scheduled for today. Good night!"

        schedule = [f"{m['medicine']} at {m.get('time', 'unscheduled')}" for m in medications]
        return "Your medication schedule: " + "; ".join(schedule) + "."


class EmotionHandler:
    @staticmethod
    def respond(emotion: str, user_name: str) -> str:
        responses = {
            "lonely":   f"I am right here with you, {user_name}. You are never truly alone. "
                        f"Would you like to chat, or shall I call someone for you?",
            "sad":      f"I am really sorry you are feeling this way, {user_name}. "
                        f"It is okay to feel sad sometimes. Would you like to talk about it?",
            "anxious":  f"Take a slow, deep breath with me, {user_name}. In... and out. "
                        f"You are safe right now. I am here.",
            "tired":    f"You sound tired, {user_name}. Rest is very important. "
                        f"Can I get you a reminder to take a nap, or would you like some water?",
            "hopeless": None
        }
        return responses.get(emotion, f"I hear you, {user_name}. I am here for you.")


class ContactHandler:
    @staticmethod
    def find(contacts: list, text: str) -> dict | None:
        t = text.lower()
        for c in contacts:
            if c.get("relation", "").lower() in t or c.get("name", "").lower() in t:
                return c
        return None

    @staticmethod
    def list_contacts(contacts: list, emergency_only=False) -> str:
        if not contacts:
            return "No contacts saved."
        items = [f"{c['name']} ({c.get('relation','')}) -- {c.get('phone','no number')}"
                 for c in contacts]
        label = "Emergency contacts" if emergency_only else "Contacts"
        return label + ":\n" + "\n".join(f"  * {i}" for i in items)


# ═══════════════════════════════════════════════════════════════════
# SECTION 7 — LLM BRAIN  (unchanged)
# ═══════════════════════════════════════════════════════════════════
class LeoBrain:
    SYSTEM_TEMPLATE = """You are Leo, a warm, caring AI home assistant for elderly people. You were built by Hunzla Khalid, Ayesha Abaidullah, and Shaiq Bhatti — FYP 2024-25.

YOUR ROLE:
- Be a friendly companion — chat, tell stories, answer questions, give reminders.
- If asked to tell a story, tell a short engaging one immediately.
- If asked a general question, answer it helpfully and simply.
- If asked about hobbies, history, news or any life topic, engage warmly.

COMMUNICATION STYLE:
- Short, simple sentences. Warm and patient. No jargon.
- NEVER refuse or deflect a normal request. Always respond helpfully.
- Greetings: 1-2 sentences. Stories/explanations: up to 5-6 sentences.
- Lists (contacts, medicines): plain text, one item per line.

SAFETY:
- Never give medical diagnoses. Say "please consult your doctor" for health decisions.
- For medications, use ONLY the profile schedule below. Never invent doses.
- If user sounds distressed, acknowledge feelings first.

User profile:
{profile}
"""

    def __init__(self, model_path: Path):
        print("\nLoading Leo's Brain (offline mode)...")
        self._has_cuda = torch.cuda.is_available()
        print(f"   Device: {'cuda' if self._has_cuda else 'cpu'}")
        if self._has_cuda:
            print(f"   GPU: {torch.cuda.get_device_name(0)}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True)

        if self._has_cuda:
            self.model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                torch_dtype=torch.float16,
                device_map="auto",
                local_files_only=True
            )
            self.model.generation_config.max_new_tokens = 100
            self.model.generation_config.pad_token_id   = self.tokenizer.eos_token_id
            self.pipe = pipeline("text-generation",
                                 model=self.model, tokenizer=self.tokenizer)
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                torch_dtype=torch.float32,
                device_map=None,
                local_files_only=True
            )
            self.model.generation_config.max_new_tokens = 100
            self.model.generation_config.pad_token_id   = self.tokenizer.eos_token_id
            self.pipe = pipeline("text-generation",
                                 model=self.model, tokenizer=self.tokenizer,
                                 device=-1)
        print("   Brain loaded.\n")

    def chat(self, user_input: str, profile: dict, history: list) -> str:
        system = self.SYSTEM_TEMPLATE.format(profile=json.dumps(profile, indent=2))
        messages = [{"role": "system", "content": system}]
        messages += history
        messages.append({"role": "user", "content": user_input})

        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)

        outputs = self.pipe(prompt, do_sample=True, temperature=0.75,
                            top_p=0.9, num_return_sequences=1)

        full  = outputs[0]["generated_text"]
        reply = full.split("<|im_start|>assistant")[-1].strip()
        reply = reply.replace("<|im_end|>", "").strip()
        return reply



# ═══════════════════════════════════════════════════════════════════
# SECTION 7B — VOICE INPUT  (Whisper + PyAudio)
# ═══════════════════════════════════════════════════════════════════
class VoiceInput:
    """
    Captures microphone audio and transcribes with OpenAI Whisper.

    Usage:
        v = VoiceInput()
        if v.available:
            text = v.listen()   # returns transcribed string or None
    """

    CHUNK     = 1024
    FORMAT    = pyaudio.paInt16 if PYAUDIO_AVAILABLE else None
    CHANNELS  = 1
    RATE      = 16000          # Whisper expects 16kHz
    SILENCE_THRESHOLD = 500    # RMS below this = silence
    SILENCE_SECONDS   = 2.0    # stop after this many seconds of silence
    MAX_SECONDS       = 15     # max recording length

    def __init__(self, whisper_model: str = "base"):
        self.available = WHISPER_AVAILABLE and PYAUDIO_AVAILABLE

        if not self.available:
            print("[Voice] Not available — text input only.")
            return

        print("[Voice] Loading Whisper model (base)...")
        self._model = _whisper.load_model(whisper_model)
        self._pa    = pyaudio.PyAudio()
        print("[Voice] Ready. Press V to speak.")

    def listen(self) -> str | None:
        """
        Record from mic until silence, transcribe with Whisper.
        Shows live recording bar and clearly displays what was heard.
        """
        if not self.available:
            return None

        line = "-" * 44
        print(f"\n  {line}")
        print("  RECORDING  --  Speak now...")
        print(f"  {line}")
        print("  ", end="", flush=True)

        stream = self._pa.open(
            format            = self.FORMAT,
            channels          = self.CHANNELS,
            rate              = self.RATE,
            input             = True,
            frames_per_buffer = self.CHUNK,
        )

        frames        = []
        silent_chunks = 0
        max_chunks    = int(self.RATE / self.CHUNK * self.MAX_SECONDS)
        silence_limit = int(self.RATE / self.CHUNK * self.SILENCE_SECONDS)
        started       = False

        try:
            for _ in range(max_chunks):
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)

                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(arr ** 2))) if len(arr) > 0 else 0

                if rms > self.SILENCE_THRESHOLD:
                    started       = True
                    silent_chunks = 0
                    # Show volume level
                    level = min(int(rms / 600), 4)
                    bar   = ["v", "vv", "VV", "VVV", "VVV!"][level]
                    print(f"[{bar}]", end=" ", flush=True)
                elif started:
                    silent_chunks += 1
                    print("...", end=" ", flush=True)
                    if silent_chunks >= silence_limit:
                        break
                else:
                    print(".", end="", flush=True)  # waiting for speech

        finally:
            stream.stop_stream()
            stream.close()

        print()  # newline

        if not started:
            print(f"  {line}")
            print("  No speech detected. Try again.")
            print(f"  {line}\n")
            return None

        # Transcribing
        print(f"  Transcribing... (please wait)")

        import wave
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self._pa.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b"".join(frames))

            result = self._model.transcribe(tmp_path, language="en", fp16=False)
            text   = result["text"].strip()

            if not text:
                print(f"  {line}")
                print("  Could not understand. Try again.")
                print(f"  {line}\n")
                return None

            # Show what was heard clearly
            print(f"  {line}")
            print(f"  LEO HEARD  :  {text}")
            print(f"  {line}\n")
            return text

        except Exception as e:
            print(f"  [Voice] Error: {e}")
            return None
        finally:
            os.unlink(tmp_path)


    def close(self):
        if PYAUDIO_AVAILABLE and hasattr(self, "_pa"):
            self._pa.terminate()



# ═══════════════════════════════════════════════════════════════════
# SECTION 7C — VOICE OUTPUT  (Kokoro TTS)
# Leo speaks responses aloud using Kokoro text-to-speech
#
# Model file check order:
#   1. FYP_Backend/models/kokoro/   ← your downloaded files
#   2. ~/.cache/huggingface/hub/    ← HuggingFace auto-cache
#   3. Auto-download from HuggingFace (first run only, ~300 MB)
#
# To pre-download manually:
#   pip install huggingface_hub
#   python -c "from huggingface_hub import snapshot_download;
#              snapshot_download('hexgrad/Kokoro-82M',
#              local_dir='models/kokoro')"
# ═══════════════════════════════════════════════════════════════════
class VoiceOutput:
    """
    Kokoro ONNX TTS — Leo speaks responses aloud.

    Model files (auto-downloaded if missing):
      kokoro-v1.0.onnx    (~300 MB)
      voices-v1.0.bin     (~10 MB)

    Files are saved next to audio.py so they only
    download once.

    Voices:
      af_heart, af_bella, af_nicole, af_nova,
      af_river, af_sarah, af_sky, af_alloy,
      am_adam, am_echo, am_michael,
      bf_emma, bf_isabella, bm_george, bm_lewis
    """

    # KPipeline voices (PyTorch kokoro package)
    # American English: af_heart, af_bella, af_nicole, am_adam, am_echo
    # British:          bf_emma, bf_isabella, bm_george, bm_lewis
    VOICE = "af_heart"
    SPEED = 1.0
    LANG_CODE = "a"   # 'a' = American English, 'b' = British English

    def __init__(self):
        self.available      = KOKORO_AVAILABLE
        self._pipeline      = None   # KPipeline instance
        self._audio_backend = None   # detected at startup

        if not self.available:
            print("[TTS] kokoro not installed — text only.")
            print("      Fix:  pip install kokoro")
            return

        try:
            print(f"[TTS] Loading KPipeline (lang_code='{self.LANG_CODE}')...")
            self._pipeline = _KPipeline(lang_code=self.LANG_CODE)
            print(f"[TTS] Ready — voice: {self.VOICE}")
        except Exception as e:
            print(f"[TTS] KPipeline load failed: {e}")
            print("      If you see espeak-ng errors, install it from:")
            print("      https://github.com/espeak-ng/espeak-ng/releases")
            self.available = False
            return

        # Detect which audio backend works on this machine
        self._audio_backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """
        Try each audio playback method in order.
        Prints which one works so the user can see it in console.
        Returns the name of the working backend (or 'none').
        """
        import numpy as np, tempfile, os

        # Generate 0.1s of silence as a test signal
        test_audio = np.zeros(2400, dtype=np.float32)
        sample_rate = 24000

        # 1. sounddevice — best, no file I/O
        try:
            import sounddevice as _sd
            _sd.play(test_audio, sample_rate)
            _sd.wait()
            print("[TTS] Audio backend: sounddevice ✓")
            return "sounddevice"
        except Exception as e:
            print(f"[TTS] sounddevice unavailable: {e}")

        # 2. pygame — very reliable on Windows
        try:
            import pygame
            pygame.mixer.init(frequency=sample_rate, size=-16, channels=1, buffer=512)
            pygame.mixer.quit()
            print("[TTS] Audio backend: pygame ✓")
            return "pygame"
        except Exception as e:
            print(f"[TTS] pygame unavailable: {e}")

        # 3. VLC
        try:
            import vlc as _vlc
            self._vlc = _vlc
            # Quick test: create an instance
            _vlc.Instance()
            print("[TTS] Audio backend: VLC ✓")
            return "vlc"
        except Exception as e:
            print(f"[TTS] VLC unavailable: {e}")

        # 4. winsound (Windows only, WAV files only)
        try:
            import winsound, wave
            # Write a tiny silent WAV and play it
            tmp = os.path.join(tempfile.gettempdir(), "_leo_test.wav")
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000)
                wf.writeframes(b"\x00\x00" * 2400)
            winsound.PlaySound(tmp, winsound.SND_FILENAME)
            os.unlink(tmp)
            print("[TTS] Audio backend: winsound ✓")
            return "winsound"
        except Exception as e:
            print(f"[TTS] winsound unavailable: {e}")

        # 5. playsound
        try:
            from playsound import playsound
            print("[TTS] Audio backend: playsound ✓")
            return "playsound"
        except Exception as e:
            print(f"[TTS] playsound unavailable: {e}")

        print("[TTS] ⚠ NO AUDIO BACKEND FOUND — voice output disabled.")
        print("      Fix: pip install sounddevice   or   pip install pygame")
        return "none"

    # _ensure_files removed — KPipeline (kokoro package) handles model
    # download automatically via HuggingFace on first run.

    def speak(self, text: str):
        """
        Generate speech using KPipeline, concatenate all chunks, play once.
        Uses sounddevice (confirmed working from test_tts_voice_testing.py).
        """
        if not self.available or not self._pipeline or not text:
            return
        try:
            import numpy as np

            SAMPLE_RATE = 24000
            all_chunks  = []
            silence_gap = np.zeros(int(SAMPLE_RATE * 0.08), dtype=np.float32)

            # KPipeline generator — yields (graphemes, phonemes, audio_chunk)
            generator = self._pipeline(
                text,
                voice = self.VOICE,
                speed = self.SPEED,
            )

            for _, _, audio_chunk in generator:
                if audio_chunk is not None and len(audio_chunk) > 0:
                    # KPipeline may return a PyTorch Tensor — convert to numpy first
                    if hasattr(audio_chunk, 'detach'):
                        audio_chunk = audio_chunk.detach().cpu().numpy()
                    all_chunks.append(np.array(audio_chunk, dtype=np.float32))
                    all_chunks.append(silence_gap)

            if not all_chunks:
                print("[TTS] No audio generated.")
                return

            full_audio = np.concatenate(all_chunks)
            self._play_audio(full_audio, SAMPLE_RATE)

        except Exception as e:
            print(f"[TTS] Speak error: {e}")
            import traceback; traceback.print_exc()

    def _play_audio(self, audio, sample_rate: int):
        """
        Play numpy float32 audio array using the detected backend.
        Falls back through all methods if the detected one fails.
        Each method prints a clear error so you can see exactly what fails.
        """
        import numpy as np, tempfile, os, time

        backend = self._audio_backend or "sounddevice"

        # ── Helper: write WAV file ────────────────────────────────────────────
        def write_wav(path):
            """Write float32 audio as 16-bit PCM WAV (universally compatible)."""
            import wave
            pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)        # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())

        # ── Method 1: sounddevice ─────────────────────────────────────────────
        if backend in ("sounddevice", None):
            try:
                import sounddevice as _sd
                _sd.play(audio, sample_rate)
                _sd.wait()
                return
            except Exception as e:
                print(f"[TTS] sounddevice failed: {e}")
                self._audio_backend = "pygame"   # try next on future calls

        # ── Method 2: pygame ─────────────────────────────────────────────────
        tmp_path = os.path.join(tempfile.gettempdir(), "leo_tts.wav")
        write_wav(tmp_path)

        if backend in ("pygame", "sounddevice"):
            try:
                import pygame
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=sample_rate, size=-16,
                                      channels=1, buffer=1024)
                sound = pygame.mixer.Sound(tmp_path)
                channel = sound.play()
                while channel.get_busy():
                    time.sleep(0.05)
                try: os.unlink(tmp_path)
                except: pass
                return
            except Exception as e:
                print(f"[TTS] pygame failed: {e}")
                self._audio_backend = "vlc"

        # ── Method 3: VLC ─────────────────────────────────────────────────────
        if backend in ("vlc", "pygame", "sounddevice"):
            try:
                import vlc as _vlc
                player = _vlc.MediaPlayer(tmp_path)
                player.play()
                time.sleep(0.25)
                while True:
                    state = player.get_state()
                    if state in [_vlc.State.Ended, _vlc.State.Stopped,
                                 _vlc.State.Error]:
                        break
                    time.sleep(0.05)
                player.stop()
                try: os.unlink(tmp_path)
                except: pass
                return
            except Exception as e:
                print(f"[TTS] VLC failed: {e}")
                self._audio_backend = "winsound"

        # ── Method 4: winsound (Windows built-in) ────────────────────────────
        try:
            import winsound
            if not os.path.exists(tmp_path):
                write_wav(tmp_path)
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
            try: os.unlink(tmp_path)
            except: pass
            return
        except Exception as e:
            print(f"[TTS] winsound failed: {e}")
            self._audio_backend = "playsound"

        # ── Method 5: playsound ───────────────────────────────────────────────
        try:
            from playsound import playsound
            if not os.path.exists(tmp_path):
                write_wav(tmp_path)
            playsound(tmp_path)
            try: os.unlink(tmp_path)
            except: pass
            return
        except Exception as e:
            print(f"[TTS] playsound failed: {e}")

        print("[TTS] ⚠ All audio methods failed — cannot play voice output.")
        print("      Run:  pip install sounddevice   or   pip install pygame")

    def stop(self):
        try:
            import sounddevice as _sd
            _sd.stop()
        except Exception:
            pass
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# SECTION 7D — BACKGROUND AUDIO MONITOR
# Mic always listening — detects distress keywords automatically
# ═══════════════════════════════════════════════════════════════════
class BackgroundListener:
    """
    Background thread that continuously listens to mic.
    When distress keywords detected → callback() fires automatically.
    No ENTER needed — patient just says 'help' and Leo responds.
    """

    DISTRESS_KEYWORDS = [
        "help", "help me", "i fell", "i fall", "falling",
        "chest pain", "heart attack", "emergency",
        "call ambulance", "i need help", "somebody help",
        "i can't breathe", "can't breathe", "i'm dying"
    ]

    CHUNK             = 1024
    RATE              = 16000
    SILENCE_THRESHOLD = 400
    SPEECH_SECONDS    = 0.3
    SILENCE_SECONDS   = 1.5
    MAX_SECONDS       = 12

    def __init__(self, callback, whisper_model="base", distress_only=False):
        """
        distress_only=False (default, GUI mode):
            Fires callback for EVERY detected utterance.
        distress_only=True (terminal mode):
            Only fires callback when distress keywords detected.
        """
        self.callback      = callback
        self.distress_only = distress_only
        self.available     = WHISPER_AVAILABLE and PYAUDIO_AVAILABLE
        self._running  = False
        self._thread   = None
        self._model    = None
        self._pa       = None

        if not self.available:
            print("[BG] Not available — whisper or pyaudio missing.")
            return

        self._model = _whisper.load_model(whisper_model)
        self._pa    = pyaudio.PyAudio()
        print("[BG] Background listener ready.")

    def start(self):
        if not self.available or self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[BG] Listening in background — say 'help' anytime.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[BG] Background listener stopped.")

    def _run(self):
        FORMAT = pyaudio.paInt16
        try:
            stream = self._pa.open(
                format=FORMAT, channels=1, rate=self.RATE,
                input=True, frames_per_buffer=self.CHUNK)
        except Exception as e:
            print(f"[BG] Mic error: {e}")
            return

        speech_chunks = int(self.RATE / self.CHUNK * self.SPEECH_SECONDS)
        silence_limit = int(self.RATE / self.CHUNK * self.SILENCE_SECONDS)
        max_chunks    = int(self.RATE / self.CHUNK * self.MAX_SECONDS)

        while self._running:
            try:
                # Wait for speech start
                loud_count = 0
                frames     = []
                while self._running:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    arr  = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    rms  = float(np.sqrt(np.mean(arr**2))) if len(arr) > 0 else 0
                    if rms > self.SILENCE_THRESHOLD:
                        frames.append(data)
                        loud_count += 1
                        if loud_count >= speech_chunks:
                            break
                    else:
                        frames = []; loud_count = 0

                if not self._running:
                    break

                # Record until silence
                silent_count = 0
                count = len(frames)
                while self._running and count < max_chunks:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    frames.append(data); count += 1
                    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(arr**2))) if len(arr) > 0 else 0
                    if rms < self.SILENCE_THRESHOLD:
                        silent_count += 1
                        if silent_count >= silence_limit:
                            break
                    else:
                        silent_count = 0

                # Transcribe
                text = self._transcribe(frames)
                if not text:
                    continue

                lower = text.lower()
                is_distress = any(kw in lower for kw in self.DISTRESS_KEYWORDS)

                if self.distress_only:
                    # Terminal mode: only fire for distress keywords
                    if is_distress:
                        print(f"\n  [BG] DISTRESS DETECTED: {text}")
                        try:    self.callback(text)
                        except Exception as e: print(f"  [BG] Callback error: {e}")
                else:
                    # GUI mode: fire for ALL speech — LEO responds to everything
                    if is_distress:
                        print(f"\n  [BG] DISTRESS DETECTED: {text}")
                    else:
                        print(f"\n  [BG] Heard: {text}")
                    try:    self.callback(text)
                    except Exception as e: print(f"  [BG] Callback error: {e}")

            except Exception as e:
                if self._running:
                    print(f"[BG] Error: {e}")
                time.sleep(0.5)

        stream.stop_stream()
        stream.close()

    def _transcribe(self, frames) -> str | None:
        import wave
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.RATE)
                wf.writeframes(b"".join(frames))
            result = self._model.transcribe(tmp_path, language="en", fp16=False)
            os.unlink(tmp_path)
            return result["text"].strip() or None
        except Exception:
            return None


class Leo:
    """Main orchestrator — routes every user input to the right handler."""

    BANNER = """
╔══════════════════════════════════════════╗
║        LEO -- Home Assistant            ║
║   AI-Powered Elder Care System          ║
║   FYP 2024-25 | BSCS                   ║
╚══════════════════════════════════════════╝
"""

    def __init__(self, user_name: str, preloaded_profile: dict = None):
        self.user_name = user_name   # stored for Twilio alerts
        # Pass preloaded_profile so UserProfile skips file loading
        self.profile   = UserProfile(user_name, preloaded_data=preloaded_profile)
        self.memory    = ConversationMemory(user_name)
        self.logger    = ActivityLogger(user_name)
        self.matcher   = IntentMatcher()
        self.vision    = LeoVision()
        self.brain     = LeoBrain(MODEL_PATH)
        self.emergency = EmergencyHandler()
        self.meds      = MedicationHandler()
        self.emotion_h = EmotionHandler()
        self.contact_h = ContactHandler()

        # ML intent model (trained separately)
        intent_model_path = BASE_DIR / "leo_intent_model.pkl"
        if intent_model_path.exists():
            self.intent_model = joblib.load(intent_model_path)
        else:
            print("[WARNING] Intent model not found. Using rule-based routing only.")
            self.intent_model = None

        # Inactivity monitor
        self.inactivity = InactivityMonitor(user_name, self._on_inactivity_alert)
        self.inactivity.start()

    # ── PUBLIC ──────────────────────────────────────────────
    def respond(self, user_input: str) -> str:
        self.inactivity.heartbeat()

        text = user_input.strip()
        if not text:
            return "I didn't catch that. Could you please repeat?"

        response = self._route(text)

        self.memory.add(text, response)
        self.logger.log("chat", f"User: {text} | Leo: {response}")
        return response

    def shutdown(self):
        self.inactivity.stop()
        self.logger.print_daily_summary()
        print("\nLeo: Take care! I'll be here whenever you need me.")

    # ── ROUTING  (unchanged logic) ───────────────────────────
    def _route(self, text: str) -> str:

        # 1. PURE GREETING — LLM responds naturally for variety
        # is_greeting() only fires for short pure greetings with no request.
        # Mixed inputs like "hello tell me a story" skip here → go to LLM.
        if self.matcher.is_greeting(text):
            hour = datetime.now().hour
            tod  = "morning" if hour<12 else ("afternoon" if hour<18 else "evening")
            greeting_ctx = (f"The user greeted you. It is {tod}. "
                           f"Greet {self.profile.name} warmly and ask what they need. "
                           f"Keep it to 1-2 sentences.")
            return self.brain.chat(greeting_ctx, self.profile.data,
                                   self.memory.as_messages())

        # 2. MEMORY RECALL
        if self.matcher.is_memory_question(text):
            return self._handle_memory()

        # 3. CONTACT INFO REQUEST
        if "emergency contact" in text.lower() and any(
            w in text.lower() for w in ["show", "list", "who", "what"]
        ):
            return self.contact_h.list_contacts(
                self.profile.emergency_contacts, emergency_only=True)

        # 4. EMOTION CHECK
        emotion = self.matcher.detect_emotion(text)
        if emotion == "hopeless":
            resp = self.emergency.respond(
                "critical", self.profile.name, self.profile.emergency_contacts)
            self.logger.log("emergency", text, severity="critical")
            return resp
        if emotion:
            self.logger.log("emotion", f"{emotion}: {text}", severity="warning")
            return self.emotion_h.respond(emotion, self.profile.name)

        # 5. EMERGENCY DETECTION
        level = self.matcher.detect_emergency_level(text)
        if level:
            resp = self.emergency.respond(
                level, self.profile.name, self.profile.emergency_contacts)
            self.logger.log("emergency", text, severity="critical")
            # Send SMS to emergency contacts
            twilio_alerts.send_emergency_alert(
                patient  = self.user_name if hasattr(self, 'user_name') else "patient",
                contacts = self.profile.emergency_contacts,
                reason   = text,
                level    = level,
            )
            return resp

        # 6. ML INTENT MODEL
        ml_intent = None
        if self.intent_model:
            ml_intent = self.intent_model.predict([text])[0]
            print(f"   [Intent: {ml_intent}]")

        # 7. MEDICATION
        if ml_intent == "medication" or self.matcher.is_medication(text):
            resp = self.meds.respond(text, self.profile.medications)
            self.logger.log("medication", text)
            return resp

        # 8. CALL / CONTACT
        if self.matcher.is_call_request(text):
            return self._handle_call(text)

        # 9. FALLBACK — LLM
        return self.brain.chat(text, self.profile.data, self.memory.as_messages())

    # ── HELPERS  (unchanged) ─────────────────────────────────
    def _handle_memory(self) -> str:
        recent = self.memory.recent_user_messages(3)
        if not recent:
            return "We haven't talked much yet today. What's on your mind?"
        return f"Earlier you mentioned: {' ... '.join(recent)}"

    def _handle_call(self, text: str) -> str:
        contact = self.contact_h.find(self.profile.all_contacts, text)
        if contact:
            return (f"Calling your {contact.get('relation','contact')}, "
                    f"{contact['name']} ({contact.get('phone','')}) now...")
        if not self.profile.all_contacts:
            return "You have no contacts saved. Please ask your caregiver to add some."
        names = ", ".join(c["name"] for c in self.profile.all_contacts)
        return f"Who would you like to call? I have: {names}."

    def _on_inactivity_alert(self, message: str):
        self.logger.log("inactivity", message, severity="warning")
        print(f"\n  INACTIVITY ALERT: {message}\n")
        # Send SMS to emergency contacts
        import re
        mins = re.search(r"(\d+) minutes", message)
        minutes = int(mins.group(1)) if mins else 30
        twilio_alerts.send_inactivity_alert(
            patient  = self.profile.user_name,
            contacts = self.profile.emergency_contacts,
            minutes  = minutes,
        )


# ═══════════════════════════════════════════════════════════════════
# SECTION 9 — ENTRY POINT
# Updated: uses patait_info_collector for patient login/setup
# ═══════════════════════════════════════════════════════════════════
def main():
    print("\n" + "="*50)
    print("   LEO -- AI Home Assistant for the Elderly")
    print("   FYP 2024-25 | BSCS")
    print("="*50)

    # Step 1: Patient login / setup
    collector = AIBrainProfile()
    collector.startup()
    profile      = collector.get_profile()
    patient_name = profile["personal"]["name"].lower().replace(" ", "_")

    # Step 2: Save to MongoDB
    if leo_db.connected:
        leo_db.save_patient(profile)

    # Step 3: Start Leo with the already-loaded profile
    leo   = Leo(patient_name, preloaded_profile=profile)
    voice = VoiceInput(whisper_model="base")
    tts   = VoiceOutput()

    # Background listener — always on, no ENTER needed for emergencies
    def _on_bg_speech(text: str):
        """Called when background listener detects distress keywords."""
        print(f"\n  [AUTO] Heard: {text}")
        response = leo.respond(text)
        print(f"  Leo: {response}\n")
        tts.speak(response)

    bg_listener = BackgroundListener(_on_bg_speech, whisper_model="base")

    print(Leo.BANNER)
    name = leo.profile.name

    # ── Mode selection ────────────────────────────────
    print(f"  Hello, {name}! I am Leo, your home assistant.")
    print()
    print("  INPUT MODE:")
    print("    [T] Type  — keyboard input (default)")
    print("    [V] Voice — speak to Leo using microphone")
    print()
    print("  OUTPUT (Leo's voice):")
    print(f"    Kokoro TTS: {'ON' if tts.available else 'OFF (install kokoro)'}")
    print()

    mode_choice = input("  Choose input mode (T/V): ").strip().upper()
    voice_mode  = (mode_choice == "V" and voice.available)

    if voice_mode:
        print("\n  Voice mode ON. Press ENTER to speak, or type your message.")
    else:
        if mode_choice == "V" and not voice.available:
            print("\n  Voice not available. Switching to text mode.")
        print("\n  Text mode. Type your message and press ENTER.")
        print("  (Type V anytime to switch to voice mode)")

    print("  Type 'exit' or 'quit' to stop.\n")

    # Start background listener
    if voice_mode:
        print("  [BG Listener] OFF in voice mode (mic shared with VoiceInput)")
    else:
        bg_listener.start()

    greeting = f"Good {_time_greeting()}, {name}! How are you feeling today?"
    print(f"  Leo: {greeting}\n")
    tts.speak(greeting)

    try:
        while True:

            # ── Voice mode ────────────────────────────
            if voice_mode:
                print(f"  {name} [Voice — press ENTER to speak, or type]: ", end="", flush=True)
                # Check if user typed something instead
                import select, sys
                typed = input().strip()

                if typed.lower() in ("exit","quit","bye","goodbye"): break
                if typed.lower() == "t":
                    voice_mode = False
                    print("  Switched to TEXT mode.\n")
                    continue

                if typed:
                    # User typed something directly
                    user_input = typed
                else:
                    # User pressed ENTER → start listening
                    user_input = voice.listen()
                    if not user_input:
                        continue

            # ── Text mode ─────────────────────────────
            else:
                user_input = input(f"  {name}: ").strip()
                if not user_input: continue
                if user_input.lower() in ("exit","quit","bye","goodbye"): break
                if user_input.lower() == "v":
                    if voice.available:
                        voice_mode = True
                        print("  Switched to VOICE mode. Press ENTER to speak.\n")
                    else:
                        print("  Voice not available. Install: pip install openai-whisper pyaudio\n")
                    continue

            if not user_input: continue

            response = leo.respond(user_input)
            print(f"\n  Leo: {response}\n")
            tts.speak(response)

    except KeyboardInterrupt:
        pass
    finally:
        leo.shutdown()
        bg_listener.stop()
        voice.close()
        tts.stop()
        if leo_db.connected:
            leo_db.close()


def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:  return "morning"
    if hour < 18:  return "afternoon"
    return "evening"


if __name__ == "__main__":
    main()


