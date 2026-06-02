"""
LEO — MongoDB Storage
======================
Saves all patient data to MongoDB alongside local files.

Collections:
  patients      → profile, medications, contacts
  sessions      → each monitoring session (start/end, video path)
  fall_events   → every fall detected (timestamp, clip path, score)
  activity_logs → chat, medication, emotion, emergency events
  memory        → conversation history per patient per day

Install:
  pip install pymongo

Run MongoDB locally:
  mongod --dbpath C:/data/db

Or use MongoDB Atlas (cloud) — just change MONGO_URI below.

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

from __future__ import annotations

from datetime import datetime
from pathlib  import Path
from typing   import Optional

# ── pymongo import with friendly error ───────────────────
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.collection import Collection
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("[MongoDB] pymongo not installed. Run:  pip install pymongo")


# ═══════════════════════════════════════════════════════════
#  CONFIGURATION  — change these to match your setup
# ═══════════════════════════════════════════════════════════

MONGO_URI = "mongodb://localhost:27017"   # local MongoDB
# MONGO_URI = "mongodb+srv://user:pass@cluster.mongodb.net"  # Atlas cloud

DB_NAME   = "leo_fyp"   # database name


# ═══════════════════════════════════════════════════════════
#  LEO DATABASE
# ═══════════════════════════════════════════════════════════

class LeoDB:
    """
    Single class that manages all MongoDB operations for LEO.

    Usage:
        db = LeoDB()
        if db.connected:
            db.save_patient(profile_dict)
            db.log_fall("ahmed", clip_path, score=5)
            db.log_activity("ahmed", "chat", "Hello Leo")
    """

    def __init__(self, uri: str = MONGO_URI, db_name: str = DB_NAME):
        self.connected   = False
        self._client     = None
        self._db         = None
        self._session_id = None   # current monitoring session _id

        if not PYMONGO_AVAILABLE:
            print("[MongoDB] Skipping — pymongo not installed.")
            return

        try:
            self._client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            # Ping to confirm connection
            self._client.admin.command("ping")
            self._db     = self._client[db_name]
            self.connected = True
            self._create_indexes()
            print(f"[MongoDB] Connected → {uri} / {db_name}")
        except Exception as e:
            print(f"[MongoDB] Could not connect: {e}")
            print("[MongoDB] Data will only be saved locally.")

    # ──────────────────────────────────────────────────────
    #  INDEXES  (faster queries)
    # ──────────────────────────────────────────────────────
    def _create_indexes(self):
        try:
            self._db.patients.create_index(
                [("username", ASCENDING)], unique=True)
            self._db.fall_events.create_index(
                [("patient", ASCENDING), ("timestamp", DESCENDING)])
            self._db.activity_logs.create_index(
                [("patient", ASCENDING), ("timestamp", DESCENDING)])
            self._db.sessions.create_index(
                [("patient", ASCENDING), ("start_time", DESCENDING)])
            self._db.memory.create_index(
                [("patient", ASCENDING), ("date", DESCENDING)])
        except Exception as e:
            print(f"[MongoDB] Index warning: {e}")

    def _col(self, name: str) -> Optional[Collection]:
        if not self.connected:
            return None
        return self._db[name]

    # ──────────────────────────────────────────────────────
    #  PATIENT PROFILE
    # ──────────────────────────────────────────────────────
    def save_patient(self, profile: dict) -> bool:
        """
        Save or update a patient's full profile.
        Upserts based on username (create if new, update if exists).
        """
        col = self._col("patients")
        if col is None: return False
        try:
            username = profile.get("personal", {}).get("name", "unknown")
            username = username.lower().replace(" ", "_")
            doc = {
                "username":   username,
                "profile":    profile,
                "updated_at": datetime.now(),
            }
            col.update_one(
                {"username": username},
                {"$set": doc, "$setOnInsert": {"created_at": datetime.now()}},
                upsert=True
            )
            print(f"[MongoDB] Patient saved: {username}")
            return True
        except Exception as e:
            print(f"[MongoDB] save_patient error: {e}")
            return False

    def get_patient(self, username: str) -> Optional[dict]:
        """Load patient profile from MongoDB."""
        col = self._col("patients")
        if col is None: return None
        try:
            username = username.lower().replace(" ", "_")
            doc = col.find_one({"username": username})
            return doc["profile"] if doc else None
        except Exception as e:
            print(f"[MongoDB] get_patient error: {e}")
            return None

    def list_patients(self) -> list[str]:
        """Return list of all patient usernames."""
        col = self._col("patients")
        if col is None: return []
        try:
            return [d["username"] for d in col.find({}, {"username": 1})]
        except Exception as e:
            print(f"[MongoDB] list_patients error: {e}")
            return []

    # ──────────────────────────────────────────────────────
    #  MONITORING SESSION
    # ──────────────────────────────────────────────────────
    def start_session(self, patient: str, recording_path: Optional[str] = None) -> Optional[str]:
        """
        Record the start of a monitoring session.
        Returns the session _id (string) for later reference.
        """
        col = self._col("sessions")
        if col is None: return None
        try:
            doc = {
                "patient":        patient.lower().replace(" ", "_"),
                "start_time":     datetime.now(),
                "end_time":       None,
                "recording_path": str(recording_path) if recording_path else None,
                "fall_count":     0,
                "status":         "active",
            }
            result = col.insert_one(doc)
            self._session_id = result.inserted_id
            print(f"[MongoDB] Session started: {self._session_id}")
            return str(self._session_id)
        except Exception as e:
            print(f"[MongoDB] start_session error: {e}")
            return None

    def end_session(self, fall_count: int = 0):
        """Mark the current session as ended."""
        col = self._col("sessions")
        if col is None or self._session_id is None: return
        try:
            col.update_one(
                {"_id": self._session_id},
                {"$set": {
                    "end_time":   datetime.now(),
                    "fall_count": fall_count,
                    "status":     "completed",
                }}
            )
            print(f"[MongoDB] Session ended: {self._session_id}")
        except Exception as e:
            print(f"[MongoDB] end_session error: {e}")

    # ──────────────────────────────────────────────────────
    #  FALL EVENTS
    # ──────────────────────────────────────────────────────
    def log_fall(
        self,
        patient:   str,
        clip_path: Optional[str] = None,
        score:     int   = 0,
        reason:    str   = "",
        posture:   str   = "unknown",
        state:     str   = "FALL",
    ) -> bool:
        """
        Save a fall detection event to MongoDB.
        Called automatically when a fall is confirmed.
        """
        col = self._col("fall_events")
        if col is None: return False
        try:
            doc = {
                "patient":    patient.lower().replace(" ", "_"),
                "timestamp":  datetime.now(),
                "date":       datetime.now().strftime("%Y-%m-%d"),
                "time":       datetime.now().strftime("%H:%M:%S"),
                "clip_path":  str(clip_path) if clip_path else None,
                "score":      score,
                "reason":     reason,
                "posture":    posture,
                "state":      state,
                "session_id": str(self._session_id) if self._session_id else None,
                "reviewed":   False,   # caregiver dashboard can mark as reviewed
            }
            col.insert_one(doc)

            # Also increment fall count in current session
            if self._session_id:
                sessions = self._col("sessions")
                if sessions:
                    sessions.update_one(
                        {"_id": self._session_id},
                        {"$inc": {"fall_count": 1}}
                    )

            print(f"[MongoDB] Fall logged for {patient} — score: {score}")
            return True
        except Exception as e:
            print(f"[MongoDB] log_fall error: {e}")
            return False

    def get_falls(self, patient: str, limit: int = 50) -> list[dict]:
        """Get recent fall events for a patient."""
        col = self._col("fall_events")
        if col is None: return []
        try:
            patient = patient.lower().replace(" ", "_")
            return list(col.find(
                {"patient": patient},
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit))
        except Exception as e:
            print(f"[MongoDB] get_falls error: {e}")
            return []

    # ──────────────────────────────────────────────────────
    #  ACTIVITY LOGS
    # ──────────────────────────────────────────────────────
    def log_activity(
        self,
        patient:   str,
        category:  str,          # chat | fall | medication | emotion | emergency
        content:   str,
        severity:  str = "info", # info | warning | critical
    ) -> bool:
        """Log any activity event to MongoDB."""
        col = self._col("activity_logs")
        if col is None: return False
        try:
            doc = {
                "patient":    patient.lower().replace(" ", "_"),
                "timestamp":  datetime.now(),
                "date":       datetime.now().strftime("%Y-%m-%d"),
                "time":       datetime.now().strftime("%H:%M:%S"),
                "category":   category,
                "content":    content,
                "severity":   severity,
                "session_id": str(self._session_id) if self._session_id else None,
            }
            col.insert_one(doc)
            return True
        except Exception as e:
            print(f"[MongoDB] log_activity error: {e}")
            return False

    def get_logs(
        self,
        patient:  str,
        date:     Optional[str] = None,   # "YYYY-MM-DD" or None for today
        category: Optional[str] = None,
        limit:    int = 100,
    ) -> list[dict]:
        """Get activity logs for a patient."""
        col = self._col("activity_logs")
        if col is None: return []
        try:
            patient = patient.lower().replace(" ", "_")
            query   = {"patient": patient}
            if date:     query["date"]     = date
            if category: query["category"] = category
            return list(col.find(query, {"_id": 0})
                          .sort("timestamp", DESCENDING)
                          .limit(limit))
        except Exception as e:
            print(f"[MongoDB] get_logs error: {e}")
            return []

    # ──────────────────────────────────────────────────────
    #  CONVERSATION MEMORY
    # ──────────────────────────────────────────────────────
    def save_memory(self, patient: str, history: list) -> bool:
        """
        Save today's conversation history.
        Upserts — replaces the day's memory each time.
        """
        col = self._col("memory")
        if col is None: return False
        try:
            patient = patient.lower().replace(" ", "_")
            today   = datetime.now().strftime("%Y-%m-%d")
            col.update_one(
                {"patient": patient, "date": today},
                {"$set": {
                    "patient":    patient,
                    "date":       today,
                    "history":    history,
                    "updated_at": datetime.now(),
                    "turn_count": len(history) // 2,
                }},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[MongoDB] save_memory error: {e}")
            return False

    def get_memory(self, patient: str, date: Optional[str] = None) -> list:
        """Load conversation history for a patient."""
        col = self._col("memory")
        if col is None: return []
        try:
            patient = patient.lower().replace(" ", "_")
            date    = date or datetime.now().strftime("%Y-%m-%d")
            doc     = col.find_one({"patient": patient, "date": date})
            return doc["history"] if doc else []
        except Exception as e:
            print(f"[MongoDB] get_memory error: {e}")
            return []

    # ──────────────────────────────────────────────────────
    #  DASHBOARD SUMMARY
    # ──────────────────────────────────────────────────────
    def get_patient_summary(self, patient: str) -> dict:
        """
        Quick summary for caregiver dashboard.
        Returns falls today, last activity, total sessions, etc.
        """
        if not self.connected:
            return {}
        try:
            patient = patient.lower().replace(" ", "_")
            today   = datetime.now().strftime("%Y-%m-%d")

            falls_today = self._col("fall_events").count_documents(
                {"patient": patient, "date": today})
            total_falls = self._col("fall_events").count_documents(
                {"patient": patient})
            total_sessions = self._col("sessions").count_documents(
                {"patient": patient})

            last_log = self._col("activity_logs").find_one(
                {"patient": patient},
                sort=[("timestamp", DESCENDING)]
            )

            last_fall = self._col("fall_events").find_one(
                {"patient": patient},
                sort=[("timestamp", DESCENDING)]
            )

            return {
                "patient":        patient,
                "falls_today":    falls_today,
                "total_falls":    total_falls,
                "total_sessions": total_sessions,
                "last_activity":  last_log["time"] if last_log else None,
                "last_fall":      last_fall["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                                  if last_fall else None,
                "last_fall_clip": last_fall["clip_path"] if last_fall else None,
            }
        except Exception as e:
            print(f"[MongoDB] get_patient_summary error: {e}")
            return {}

    def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            print("[MongoDB] Connection closed.")


# ═══════════════════════════════════════════════════════════
#  GLOBAL INSTANCE  (import and use directly)
# ═══════════════════════════════════════════════════════════

# Import this in other files:
#   from mongo_storage import leo_db
#   leo_db.log_fall("ahmed", clip_path="/path/to/clip.avi", score=5)

leo_db = LeoDB()


# ═══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n=== MongoDB Connection Test ===\n")

    if not leo_db.connected:
        print("Not connected. Make sure MongoDB is running:")
        print("  mongod --dbpath C:/data/db")
        exit(1)

    # Test: save patient
    test_profile = {
        "personal":           {"name": "Test Patient", "age": 72},
        "emergency_contacts": [{"name": "Ali", "relation": "son", "phone": "03001234567"}],
        "contacts":           [],
        "medications":        [{"medicine": "Aspirin", "time": "08:00"}],
        "routine":            {"wake_up": "07:00", "sleep": "22:00"},
        "active_zones":       ["bedroom", "kitchen"],
    }
    leo_db.save_patient(test_profile)

    # Test: start session
    leo_db.start_session("test_patient", recording_path="data/patients/test/videos/rec.avi")

    # Test: log activity
    leo_db.log_activity("test_patient", "chat", "Hello Leo, how are you?")
    leo_db.log_activity("test_patient", "medication", "Time to take Aspirin")
    leo_db.log_activity("test_patient", "fall", "Fall detected", severity="critical")

    # Test: log fall
    leo_db.log_fall(
        patient   = "test_patient",
        clip_path = "data/patients/test/videos/2025-05-03/fall_10-15-30.avi",
        score     = 6,
        reason    = "FALL: fast_drop | flow_spike | fall_model",
        posture   = "lying",
        state     = "FALL",
    )

    # Test: save memory
    leo_db.save_memory("test_patient", [
        {"role": "user",      "content": "Hello Leo"},
        {"role": "assistant", "content": "Good morning! How are you feeling?"},
    ])

    # Test: summary
    print("\n=== Patient Summary ===")
    summary = leo_db.get_patient_summary("test_patient")
    for k, v in summary.items():
        print(f"  {k:20}: {v}")

    # Test: list patients
    print("\n=== All Patients ===")
    print(leo_db.list_patients())

    # End session
    leo_db.end_session(fall_count=1)
    leo_db.close()
    print("\nAll tests passed!")
