# """
# LEO — Twilio SMS Alerts
# FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
# """

# from datetime import datetime
# from pathlib  import Path


# try:
#     from twilio.rest import Client as _TwilioClient
#     TWILIO_AVAILABLE = True
# except ImportError:
#     TWILIO_AVAILABLE = False
#     print("[Twilio] Not installed. Run:  pip install twilio")


# class TwilioAlerts:

#     def __init__(self):
#         self.available = False

#         if not TWILIO_AVAILABLE:
#             print("[Twilio] Package not installed. Run: pip install twilio")
#             return

#         # Simple check — just make sure fields are not empty
#         if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
#             print("[Twilio] Credentials missing in twilio_alerts.py")
#             return

#         try:
#             self._client   = _TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
#             self.available = True
#             print("[Twilio] Connected — SMS alerts active.")
#         except Exception as e:
#             print(f"[Twilio] Connection failed: {e}")

#     def send_fall_alert(self, patient, contacts, clip_path=None, score=0, posture="lying"):
#         now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         clip_info = f"\nClip: {Path(clip_path).name}" if clip_path else ""
#         message   = (
#             f"FALL ALERT - LEO System\n"
#             f"{'='*28}\n"
#             f"Patient : {patient.replace('_',' ').title()}\n"
#             f"Time    : {now}\n"
#             f"Status  : FALL DETECTED\n"
#             f"Score   : {score}/4\n"
#             f"Posture : {posture}{clip_info}\n"
#             f"{'='*28}\n"
#             f"Please check on patient immediately!"
#         )
#         return self._send_to_all(contacts, message, "FALL")

#     def send_emergency_alert(self, patient, contacts, reason="Emergency", level="critical"):
#         now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         label   = "CRITICAL" if level == "critical" else "WARNING"
#         message = (
#             f"{label} - LEO System\n"
#             f"{'='*28}\n"
#             f"Patient : {patient.replace('_',' ').title()}\n"
#             f"Time    : {now}\n"
#             f"Event   : {reason}\n"
#             f"{'='*28}\n"
#             f"Patient needs immediate help!\n"
#             f"Call 1122 or 115 if needed."
#         )
#         return self._send_to_all(contacts, message, "EMERGENCY")

#     def send_inactivity_alert(self, patient, contacts, minutes=30):
#         now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         message = (
#             f"INACTIVITY ALERT - LEO\n"
#             f"{'='*28}\n"
#             f"Patient  : {patient.replace('_',' ').title()}\n"
#             f"Time     : {now}\n"
#             f"Inactive : {minutes} minutes\n"
#             f"{'='*28}\n"
#             f"No activity detected. Please check."
#         )
#         return self._send_to_all(contacts, message, "INACTIVITY")

#     def send_medication_alert(self, patient, contacts, medicine, scheduled):
#         now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         message = (
#             f"MEDICATION ALERT - LEO\n"
#             f"{'='*28}\n"
#             f"Patient  : {patient.replace('_',' ').title()}\n"
#             f"Time     : {now}\n"
#             f"Medicine : {medicine}\n"
#             f"Due at   : {scheduled}\n"
#             f"{'='*28}\n"
#             f"Patient may have missed medication."
#         )
#         return self._send_to_all(contacts, message, "MEDICATION")

#     def _send_to_all(self, contacts, message, alert_type="ALERT"):
#         if not self.available:
#             print(f"[Twilio] {alert_type} - SMS not sent (not configured)")
#             return False
#         if not contacts:
#             print(f"[Twilio] {alert_type} - No contacts to notify")
#             return False

#         success = False
#         for contact in contacts:
#             phone = contact.get("phone", "")
#             name  = contact.get("name", "Contact")
#             if not phone:
#                 continue
#             phone = self._format_phone(phone)
#             try:
#                 msg = self._client.messages.create(
#                     body  = message,
#                     from_ = f"whatsapp:{TWILIO_FROM_NUMBER}",
#                     to    = f"whatsapp:{phone}",
#                 )
#                 print(f"[Twilio] WhatsApp sent to {name} ({phone}) SID: {msg.sid}")
#                 success = True
#             except Exception as e:
#                 print(f"[Twilio] Failed to {name} ({phone}): {e}")
#         return success

#     @staticmethod
#     def _format_phone(phone: str) -> str:
#         phone = phone.strip().replace(" ", "").replace("-", "")
#         if phone.startswith("0"):
#             phone = "+92" + phone[1:]
#         elif not phone.startswith("+"):
#             phone = "+" + phone
#         return phone


# # Global instance
# twilio_alerts = TwilioAlerts()


# if __name__ == "__main__":
#     print("\n=== Twilio Test ===\n")

#     if not twilio_alerts.available:
#         print("Check credentials or run: pip install twilio")
#         exit(1)

#     # Change this to your verified number
#     test_contacts = [
#         {"name": "Hunzla", "relation": "caregiver", "phone": "03106646486"}
#     ]

#     print("Sending test SMS...")
#     twilio_alerts.send_fall_alert(
#         patient  = "ahmed",
#         contacts = test_contacts,
#         score    = 6,
#         posture  = "lying",
#     )
#     print("\nCheck your phone!")

"""
LEO — Twilio SMS Alerts
FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti

Setup: Create a .env file in FYP_Backend/ with:
    TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    TWILIO_FROM_NUMBER=+14155238886
"""

import os
from datetime import datetime
from pathlib  import Path

# ── LOAD CREDENTIALS FROM ENVIRONMENT ─────────────
TWILIO_ACCOUNT_SID  = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN   = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER  = os.environ.get("TWILIO_FROM_NUMBER", "")

try:
    from twilio.rest import Client as _TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("[Twilio] Not installed. Run:  pip install twilio")


class TwilioAlerts:

    def __init__(self):
        self.available = False

        if not TWILIO_AVAILABLE:
            print("[Twilio] Package not installed. Run: pip install twilio")
            return

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_FROM_NUMBER:
            print("[Twilio] Credentials missing. Set environment variables or .env file.")
            return

        try:
            self._client   = _TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            self.available = True
            print("[Twilio] Connected — SMS alerts active.")
        except Exception as e:
            print(f"[Twilio] Connection failed: {e}")

    def send_fall_alert(self, patient, contacts, clip_path=None, score=0, posture="lying"):
        now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clip_info = f"\nClip: {Path(clip_path).name}" if clip_path else ""
        message   = (
            f"FALL ALERT - LEO System\n"
            f"{'='*28}\n"
            f"Patient : {patient.replace('_',' ').title()}\n"
            f"Time    : {now}\n"
            f"Status  : FALL DETECTED\n"
            f"Score   : {score}/4\n"
            f"Posture : {posture}{clip_info}\n"
            f"{'='*28}\n"
            f"Please check on patient immediately!"
        )
        return self._send_to_all(contacts, message, "FALL")

    def send_emergency_alert(self, patient, contacts, reason="Emergency", level="critical"):
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        label   = "CRITICAL" if level == "critical" else "WARNING"
        message = (
            f"{label} - LEO System\n"
            f"{'='*28}\n"
            f"Patient : {patient.replace('_',' ').title()}\n"
            f"Time    : {now}\n"
            f"Event   : {reason}\n"
            f"{'='*28}\n"
            f"Patient needs immediate help!\n"
            f"Call 1122 or 115 if needed."
        )
        return self._send_to_all(contacts, message, "EMERGENCY")

    def send_inactivity_alert(self, patient, contacts, minutes=30):
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"INACTIVITY ALERT - LEO\n"
            f"{'='*28}\n"
            f"Patient  : {patient.replace('_',' ').title()}\n"
            f"Time     : {now}\n"
            f"Inactive : {minutes} minutes\n"
            f"{'='*28}\n"
            f"No activity detected. Please check."
        )
        return self._send_to_all(contacts, message, "INACTIVITY")

    def send_medication_alert(self, patient, contacts, medicine, scheduled):
        now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"MEDICATION ALERT - LEO\n"
            f"{'='*28}\n"
            f"Patient  : {patient.replace('_',' ').title()}\n"
            f"Time     : {now}\n"
            f"Medicine : {medicine}\n"
            f"Due at   : {scheduled}\n"
            f"{'='*28}\n"
            f"Patient may have missed medication."
        )
        return self._send_to_all(contacts, message, "MEDICATION")

    def _send_to_all(self, contacts, message, alert_type="ALERT"):
        if not self.available:
            print(f"[Twilio] {alert_type} - SMS not sent (not configured)")
            return False
        if not contacts:
            print(f"[Twilio] {alert_type} - No contacts to notify")
            return False

        success = False
        for contact in contacts:
            phone = contact.get("phone", "")
            name  = contact.get("name", "Contact")
            if not phone:
                continue
            phone = self._format_phone(phone)
            try:
                msg = self._client.messages.create(
                    body  = message,
                    from_ = f"whatsapp:{TWILIO_FROM_NUMBER}",
                    to    = f"whatsapp:{phone}",
                )
                print(f"[Twilio] WhatsApp sent to {name} ({phone}) SID: {msg.sid}")
                success = True
            except Exception as e:
                print(f"[Twilio] Failed to {name} ({phone}): {e}")
        return success

    @staticmethod
    def _format_phone(phone: str) -> str:
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("0"):
            phone = "+92" + phone[1:]
        elif not phone.startswith("+"):
            phone = "+" + phone
        return phone


# Global instance
twilio_alerts = TwilioAlerts()


if __name__ == "__main__":
    print("\n=== Twilio Test ===\n")

    if not twilio_alerts.available:
        print("Check credentials in .env file or run: pip install twilio")
        exit(1)

    test_contacts = [
        {"name": "Hunzla", "relation": "caregiver", "phone": "03106646486"}
    ]

    print("Sending test SMS...")
    twilio_alerts.send_fall_alert(
        patient  = "ahmed",
        contacts = test_contacts,
        score    = 6,
        posture  = "lying",
    )
    print("\nCheck your phone!")