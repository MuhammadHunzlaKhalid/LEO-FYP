"""
LEO — Patient Info Collector
=============================
Startup flow:
  1. Ask for patient name
  2. If profile already exists → "Continue from existing? (y/n)"
       y → load existing profile and start
       n → create new profile
  3. If name is new → collect new patient info

Saves to:  data/patients/{name}/profile.json

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

import json
import re
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DATA_ROOT = BASE_DIR / "data" / "patients"


def _profile_path(name: str) -> Path:
    return DATA_ROOT / name.lower().replace(" ", "_") / "profile.json"

def _profile_exists(name: str) -> bool:
    return _profile_path(name).exists()

def _load_existing(name: str) -> dict:
    with open(_profile_path(name)) as f:
        return json.load(f)


class AIBrainProfile:

    EMPTY_PROFILE = {
        "personal":           {},
        "emergency_contacts": [],
        "contacts":           [],
        "medications":        [],
        "routine":            {},
        "active_zones":       []
    }

    def __init__(self):
        self.profile  = {}
        self.username = ""

    # ── STARTUP ───────────────────────────────────────────
    def startup(self):
        print("\n" + "="*45)
        print("   LEO — Patient Profile Setup")
        print("="*45)

        while True:
            name = input("\nEnter patient name: ").strip()
            if name:
                break
            print("  Name cannot be empty.")

        self.username = name.lower().replace(" ", "_")

        if _profile_exists(name):
            print(f"\n  Profile found for '{name}'.")
            self._show_existing_summary(name)

            choice = input("\nContinue with existing profile? (y/n): ").strip().lower()

            if choice == 'y':
                self.profile = _load_existing(name)
                print(f"\n  Profile loaded. LEO is ready for '{name}'.\n")
                return

            else:
                print("\n  A new profile will be created (existing will be replaced).")
                confirm = input("  Are you sure? (y/n): ").strip().lower()
                if confirm != 'y':
                    self.profile = _load_existing(name)
                    print(f"\n  Existing profile kept.\n")
                    return

        else:
            print(f"\n  No profile found for '{name}'. Creating a new one.\n")

        self.profile = {k: (list(v) if isinstance(v, list) else dict(v)) for k, v in self.EMPTY_PROFILE.items()}
        self.profile["personal"]["name"] = name
        self._collect_all()
        self.save_profile()

    # ── SUMMARY ───────────────────────────────────────────
    def _show_existing_summary(self, name: str):
        p = _load_existing(name)
        personal = p.get("personal", {})
        print(f"   Name               : {personal.get('name', '?')}")
        print(f"   Age                : {personal.get('age', '?')}")
        print(f"   Medications        : {len(p.get('medications', []))}")
        print(f"   Emergency contacts : {len(p.get('emergency_contacts', []))}")

    # ── COLLECT ALL ───────────────────────────────────────
    def _collect_all(self):
        self._collect_personal_info()
        self._collect_emergency_contacts()
        self._collect_general_contacts()
        self._collect_medications()
        self._collect_routine()
        self._collect_active_zones()

    # ── HELPERS ───────────────────────────────────────────
    def _safe_input(self, message, required=True):
        while True:
            value = input(message).strip()
            if value == "" and required:
                print("  This field cannot be empty.")
            else:
                return value

    def _validate_time(self, t):
        try:
            datetime.strptime(t, "%H:%M")
            return True
        except:
            return False

    def _validate_phone(self, phone):
        return re.match(r"^03\d{9}$", phone)

    def _ask_time(self, label):
        while True:
            t = self._safe_input(f"{label} (HH:MM): ")
            if self._validate_time(t):
                return t
            print("  Invalid format. Use HH:MM e.g. 08:30")

    def _ask_phone(self, label="Phone number (03XXXXXXXXX): "):
        while True:
            p = self._safe_input(label)
            if self._validate_phone(p):
                return p
            print("  Invalid phone. Correct format: 03001234567")

    def _ask_int(self, label):
        while True:
            v = self._safe_input(label)
            if v.isdigit():
                return int(v)
            print("  Please enter a number only.")

    # ── SECTION 1 — Personal Info ─────────────────────────
    def _collect_personal_info(self):
        print("\n" + "-"*40)
        print("  1. Personal Information")
        print("-"*40)
        self.profile["personal"]["age"] = self._ask_int("Age (years): ")

    # ── SECTION 2 — Emergency Contacts ───────────────────
    def _collect_emergency_contacts(self):
        print("\n" + "-"*40)
        print("  2. Emergency Contacts")
        print("-"*40)
        while True:
            name     = self._safe_input("Contact name: ")
            relation = self._safe_input("Relation (e.g. son, daughter, wife): ")
            phone    = self._ask_phone()
            self.profile["emergency_contacts"].append(
                {"name": name, "relation": relation, "phone": phone}
            )
            if input("Add another emergency contact? (y/n): ").lower() != 'y':
                break

    # ── SECTION 3 — General Contacts ─────────────────────
    def _collect_general_contacts(self):
        print("\n" + "-"*40)
        print("  3. General Contacts (for normal calls)")
        print("-"*40)
        while True:
            name     = self._safe_input("Contact name: ")
            relation = self._safe_input("Relation (friend, brother, etc): ")
            phone    = self._ask_phone()
            self.profile["contacts"].append(
                {"name": name, "relation": relation, "phone": phone}
            )
            if input("Add another contact? (y/n): ").lower() != 'y':
                break

    # ── SECTION 4 — Medications ───────────────────────────
    def _collect_medications(self):
        print("\n" + "-"*40)
        print("  4. Medication Schedule")
        print("-"*40)
        while True:
            med = {
                "medicine":          self._safe_input("Medicine name: "),
                "purpose":           self._safe_input("Purpose (what it is for): "),
                "dose":              self._safe_input("Dose (e.g. 1 tablet): "),
                "time":              self._ask_time("Time to take"),
                "frequency_per_day": self._ask_int("Times per day: "),
                "before_after_food": self._safe_input("Before or after food: "),
                "total_quantity":    self._ask_int("Total quantity purchased: "),
                "quantity_left":     self._ask_int("Quantity remaining: "),
                "doctor":            self._safe_input("Prescribed by (doctor name): "),
                "start_date":        self._safe_input("Start date (YYYY-MM-DD): "),
            }
            self.profile["medications"].append(med)
            if input("Add another medicine? (y/n): ").lower() != 'y':
                break

    # ── SECTION 5 — Routine ───────────────────────────────
    def _collect_routine(self):
        print("\n" + "-"*40)
        print("  5. Daily Routine")
        print("-"*40)
        self.profile["routine"] = {
            "wake_up": self._ask_time("Wake up time"),
            "sleep":   self._ask_time("Sleep time"),
        }

    # ── SECTION 6 — Active Zones ──────────────────────────
    def _collect_active_zones(self):
        print("\n" + "-"*40)
        print("  6. Active Zones (rooms in the house)")
        print("-"*40)
        while True:
            zone = self._safe_input("Room name (e.g. bedroom, kitchen): ")
            self.profile["active_zones"].append(zone)
            if input("Add another room? (y/n): ").lower() != 'y':
                break

    # ── SAVE ──────────────────────────────────────────────
    def save_profile(self):
        path = _profile_path(self.profile["personal"]["name"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.profile, f, indent=4, ensure_ascii=False)
        print(f"\n  Profile saved -> {path}")

    def get_profile(self) -> dict:
        return self.profile


# ── ENTRY POINT ───────────────────────────────────────────
if __name__ == "__main__":
    brain = AIBrainProfile()
    brain.startup()

    profile = brain.get_profile()
    print(f"\n  Patient    : {profile['personal'].get('name')}")
    print(f"  Medicines  : {len(profile['medications'])}")
    print(f"  Emergency  : {len(profile['emergency_contacts'])} contact(s)")
    print("\n  LEO is ready!")
