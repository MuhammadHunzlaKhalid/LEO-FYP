"""
LEO — Patient Storage Manager
==============================
Organized folder structure for all patient data.

Folder layout per patient:
    data/
      patients/
        {name}/
          profile.json          ← user profile & medications
          memory/
            chat_{YYYY-MM-DD}.json
          logs/
            {YYYY-MM-DD}.json
          videos/
            {YYYY-MM-DD}/
              recording_{HH-MM-SS}.avi   ← continuous recording
              fall_{HH-MM-SS}.avi        ← auto-saved fall clip

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────
#  ROOT — everything lives under  data/patients/
# ─────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).parent / "data" / "patients"


# ══════════════════════════════════════════════════════════
#  PATIENT DIRECTORY BUILDER
# ══════════════════════════════════════════════════════════

class PatientDirs:
    """
    Creates and returns paths for one patient's folder tree.

    Usage:
        pd = PatientDirs("ahmed")
        pd.profile_file          # data/patients/ahmed/profile.json
        pd.memory_dir            # data/patients/ahmed/memory/
        pd.logs_dir              # data/patients/ahmed/logs/
        pd.video_dir_today()     # data/patients/ahmed/videos/2025-05-03/
    """

    def __init__(self, patient_name: str):
        self.name = patient_name.lower().strip()
        self.root = DATA_ROOT / self.name

        # Sub-directories
        self.memory_dir = self.root / "memory"
        self.logs_dir   = self.root / "logs"
        self.videos_dir = self.root / "videos"

        # Profile file (single JSON at root level)
        self.profile_file = self.root / "profile.json"

        # Create all directories
        for d in [self.memory_dir, self.logs_dir, self.videos_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ── Date-specific paths ───────────────────────────────

    def today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def memory_file(self, date: str | None = None) -> Path:
        """chat_{date}.json"""
        d = date or self.today_str()
        return self.memory_dir / f"chat_{d}.json"

    def log_file(self, date: str | None = None) -> Path:
        """{date}.json"""
        d = date or self.today_str()
        return self.logs_dir / f"{d}.json"

    def video_dir_today(self) -> Path:
        """data/patients/{name}/videos/{YYYY-MM-DD}/"""
        vd = self.videos_dir / self.today_str()
        vd.mkdir(parents=True, exist_ok=True)
        return vd

    def new_recording_path(self) -> Path:
        """recording_{HH-MM-SS}.avi — for continuous recording"""
        ts = datetime.now().strftime("%H-%M-%S")
        return self.video_dir_today() / f"recording_{ts}.avi"

    def new_fall_clip_path(self) -> Path:
        """fall_{HH-MM-SS}.avi — for fall event clip"""
        ts = datetime.now().strftime("%H-%M-%S")
        return self.video_dir_today() / f"fall_{ts}.avi"

    # ── Convenience: list saved videos ───────────────────

    def list_videos(self, date: str | None = None) -> list[Path]:
        """Return all video files for a given date (default: today)."""
        vd = self.videos_dir / (date or self.today_str())
        if not vd.exists():
            return []
        return sorted(vd.glob("*.avi"))

    def list_all_dates(self) -> list[str]:
        """Return all dates that have video recordings."""
        return sorted(d.name for d in self.videos_dir.iterdir() if d.is_dir())

    # ── Convenience: profile read/write ──────────────────

    def load_profile(self) -> dict:
        if not self.profile_file.exists():
            return {}
        with open(self.profile_file) as f:
            return json.load(f)

    def save_profile(self, data: dict):
        with open(self.profile_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Storage] Profile saved → {self.profile_file}")

    def __repr__(self):
        return f"<PatientDirs name={self.name!r} root={self.root}>"


# ══════════════════════════════════════════════════════════
#  MIGRATION: move old flat layout → new patient layout
# ══════════════════════════════════════════════════════════

def migrate_old_data(
    old_users_dir:  Path,
    old_memory_dir: Path,
    old_logs_dir:   Path,
) -> int:
    """
    One-time migration from the old flat layout:
        users/{name}.json
        memory/{name}_chat.json
        logs/{name}_{date}.json

    Returns number of patients migrated.
    """
    migrated = 0

    if not old_users_dir.exists():
        print("[Migrate] No old users/ folder found — skipping.")
        return 0

    for profile_file in old_users_dir.glob("*.json"):
        name = profile_file.stem
        pd   = PatientDirs(name)

        # Profile
        if not pd.profile_file.exists():
            shutil.copy(profile_file, pd.profile_file)
            print(f"  [OK] {name}: profile migrated")

        # Memory files  {name}_chat.json → memory/chat_{today}.json
        old_chat = old_memory_dir / f"{name}_chat.json"
        if old_chat.exists():
            dest = pd.memory_dir / f"chat_migrated.json"
            if not dest.exists():
                shutil.copy(old_chat, dest)
                print(f"  [OK] {name}: memory migrated")

        # Log files  {name}_{date}.json → logs/{date}.json
        if old_logs_dir.exists():
            for lf in old_logs_dir.glob(f"{name}_*.json"):
                date_part = lf.stem.replace(f"{name}_", "")
                dest = pd.logs_dir / f"{date_part}.json"
                if not dest.exists():
                    shutil.copy(lf, dest)
                    print(f"  [OK] {name}: log {date_part} migrated")

        migrated += 1

    print(f"[Migrate] Done — {migrated} patient(s) migrated to new layout.")
    return migrated


# ══════════════════════════════════════════════════════════
#  QUICK SUMMARY (for dashboard / debugging)
# ══════════════════════════════════════════════════════════

def all_patients() -> list[str]:
    """Return names of all patients in the data folder."""
    if not DATA_ROOT.exists():
        return []
    return sorted(d.name for d in DATA_ROOT.iterdir() if d.is_dir())


def patient_summary(name: str) -> dict:
    """Return a quick summary dict for one patient."""
    pd     = PatientDirs(name)
    videos = {d: len(list((pd.videos_dir / d).glob("*.avi")))
              for d in pd.list_all_dates()}
    logs   = sorted(f.stem for f in pd.logs_dir.glob("*.json"))
    return {
        "name":        name,
        "profile":     pd.profile_file.exists(),
        "memory_days": len(list(pd.memory_dir.glob("*.json"))),
        "log_days":    logs,
        "video_days":  videos,
        "root":        str(pd.root),
    }


# ══════════════════════════════════════════════════════════
#  STANDALONE TEST
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pprint

    print("=== PatientDirs test ===")
    pd = PatientDirs("ahmed_test")
    print(f"  root          : {pd.root}")
    print(f"  profile_file  : {pd.profile_file}")
    print(f"  memory_file   : {pd.memory_file()}")
    print(f"  log_file      : {pd.log_file()}")
    print(f"  recording path: {pd.new_recording_path()}")
    print(f"  fall clip path: {pd.new_fall_clip_path()}")

    # Save a test profile
    pd.save_profile({"personal": {"name": "Ahmed Test"}, "medications": []})

    print("\n=== All patients ===")
    pprint.pprint(all_patients())
