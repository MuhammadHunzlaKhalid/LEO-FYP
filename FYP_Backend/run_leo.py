"""
LEO — Desktop GUI v2
All-in-one window: camera feed, chat, alerts, patient setup.
No separate dialogs. Voice + text simultaneously.
"""

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import cv2, threading, queue, subprocess, sys, os, time, json, re, webbrowser
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
PYTHON   = sys.executable

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Colors
C = dict(
    bg="#090b12", panel="#0f1120", card="#151827",
    input="#1a1e30", accent="#00c8ff", purple="#7c3aed",
    green="#00e676", red="#ff3d3d", orange="#ff9800",
    text="#dde1f5", dim="#566080", border="#1e2340",
)


# ═══════════════════════════════════════════════════════
# CAMERA THREAD — live feed in GUI
# ═══════════════════════════════════════════════════════
class CameraThread(threading.Thread):
    def __init__(self, frame_cb, src=0):
        super().__init__(daemon=True)
        self.frame_cb = frame_cb
        self.src      = src
        self.running  = False
        self.cap      = None

    def run(self):
        self.cap     = cv2.VideoCapture(self.src)
        self.running = True
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            frame = cv2.resize(frame, (320, 220))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(frame)
            self.frame_cb(img)
            time.sleep(0.033)   # ~30 fps
        if self.cap: self.cap.release()

    def stop(self):
        self.running = False


# ═══════════════════════════════════════════════════════
# LEO BRAIN THREAD
# ═══════════════════════════════════════════════════════
class LeoBrain(threading.Thread):
    def __init__(self, out_q):
        super().__init__(daemon=True)
        self.out_q  = out_q
        self.in_q   = queue.Queue()
        self.leo    = None
        self.tts    = None
        self.bg     = None
        self.ready  = False
        self.patient_name = None

    def set_patient(self, name):
        self.patient_name = name.lower().replace(" ", "_")

    def run(self):
        try:
            while not self.patient_name:
                time.sleep(0.1)

            self.out_q.put(("sys", "Loading patient profile..."))
            sys.path.insert(0, str(BASE_DIR))

            from patait_info_collector import _profile_exists, _load_existing
            from mongo_storage import leo_db
            from audio import Leo, VoiceOutput, BackgroundListener

            if _profile_exists(self.patient_name):
                profile = _load_existing(self.patient_name)
            else:
                profile = {"personal": {"name": self.patient_name},
                           "emergency_contacts": [], "contacts": [],
                           "medications": [], "routine": {}, "active_zones": []}

            if leo_db.connected:
                leo_db.save_patient(profile)
                self.out_q.put(("db", "Connected"))
            else:
                self.out_q.put(("db", "Offline"))

            self.out_q.put(("sys", "Loading LEO brain (Qwen LLM)..."))
            self.leo = Leo(self.patient_name, preloaded_profile=profile)

            self.out_q.put(("sys", "Loading Kokoro TTS..."))
            self.tts = VoiceOutput()

            self.out_q.put(("sys", "Starting background listener (Whisper)..."))

            def on_voice(text):
                self.out_q.put(("voice", text))
                self._respond(text)

            self.bg = BackgroundListener(on_voice, whisper_model="base")
            self.bg.start()

            self.ready = True
            name = profile.get("personal", {}).get("name", self.patient_name)
            meds = profile.get("medications", [])
            contacts = profile.get("emergency_contacts", [])
            self.out_q.put(("ready", {"name": name, "meds": meds,
                                       "contacts": contacts, "profile": profile}))

            hour = datetime.now().hour
            g = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
            msg = f"{g}, {name}! I am Leo. Type or speak — I am always listening."
            self.out_q.put(("leo", msg))
            self._speak(msg)

            # Message loop
            while True:
                try:
                    text = self.in_q.get(timeout=0.5)
                    self._respond(text)
                except queue.Empty:
                    pass

        except Exception as e:
            self.out_q.put(("error", str(e)))

    def _respond(self, text):
        if not self.leo or not text:
            return
        try:
            resp = self.leo.respond(text)
            self.out_q.put(("leo", resp))
            self._speak(resp)
        except Exception as e:
            self.out_q.put(("error", str(e)))

    def _speak(self, text):
        if self.tts and self.tts.available:
            threading.Thread(target=self.tts.speak, args=(text,), daemon=True).start()

    def send(self, text):
        self.in_q.put(text)

    def stop(self):
        if self.bg:
            self.bg.stop()


# ═══════════════════════════════════════════════════════
# FALL MONITOR — polls MongoDB for new falls
# ═══════════════════════════════════════════════════════
class FallMonitor(threading.Thread):
    def __init__(self, patient, out_q):
        super().__init__(daemon=True)
        self.patient = patient
        self.out_q   = out_q
        self.running = True
        self.last_seen = None

    def run(self):
        try:
            sys.path.insert(0, str(BASE_DIR))
            from mongo_storage import leo_db
            if not leo_db.connected:
                return

            # Get latest fall timestamp at start
            last = leo_db._col("fall_events").find_one(
                {"patient": self.patient},
                sort=[("timestamp", -1)]
            )
            self.last_seen = last["timestamp"] if last else datetime.min

            while self.running:
                time.sleep(4)
                new = leo_db._col("fall_events").find_one(
                    {"patient": self.patient,
                     "timestamp": {"$gt": self.last_seen}},
                    sort=[("timestamp", -1)]
                )
                if new:
                    self.last_seen = new["timestamp"]
                    self.out_q.put(("fall", new))
        except Exception as e:
            pass

    def stop(self):
        self.running = False


# ═══════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════
class LeoApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("LEO — AI Home Assistant")
        self.geometry("1380x840")
        self.minsize(1200, 720)
        self.configure(fg_color=C["bg"])

        self.out_q      = queue.Queue()
        self.brain      = LeoBrain(self.out_q)
        self.cam_thread = None
        self.mon_proc   = None
        self.fall_mon   = None
        self.fall_count = 0
        self.patient    = ""
        self._photo     = None   # keep tkinter image reference

        self._build()
        self.after(200, self._poll)

    # ────────────────────────────────────────
    # BUILD LAYOUT
    # ────────────────────────────────────────
    def _build(self):
        # TOP BAR
        top = ctk.CTkFrame(self, fg_color=C["panel"], height=56, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="LEO", font=("Courier New", 22, "bold"),
                     text_color=C["accent"]).pack(side="left", padx=18)
        ctk.CTkLabel(top, text="AI-Powered Elder Care  |  FYP 2024-25",
                     font=("Courier New", 10), text_color=C["dim"]).pack(side="left")

        self.status_lbl = ctk.CTkLabel(top, text="● Starting...",
                                        font=("Courier New", 10), text_color=C["orange"])
        self.status_lbl.pack(side="right", padx=20)

        ctk.CTkButton(top, text="Dashboard", width=110, height=30,
                      fg_color=C["card"], hover_color=C["input"],
                      border_width=1, border_color=C["accent"],
                      text_color=C["accent"], font=("Courier New", 10),
                      command=lambda: webbrowser.open("http://localhost:5000")
                      ).pack(side="right", padx=8, pady=12)

        # MAIN AREA
        main = ctk.CTkFrame(self, fg_color=C["bg"])
        main.pack(fill="both", expand=True, padx=10, pady=(0,10))
        main.columnconfigure(0, weight=0, minsize=220)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0, minsize=250)
        main.rowconfigure(0, weight=1)

        self._build_left(main)
        self._build_center(main)
        self._build_right(main)

    # ── LEFT PANEL ────────────────────────────
    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=C["panel"], corner_radius=12, width=220)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,6))
        left.pack_propagate(False)

        # Patient setup card
        setup = ctk.CTkFrame(left, fg_color=C["card"], corner_radius=10)
        setup.pack(fill="x", padx=10, pady=(12,6))

        ctk.CTkLabel(setup, text="PATIENT", font=("Courier New", 8),
                     text_color=C["dim"]).pack(pady=(8,2))

        self.name_entry = ctk.CTkEntry(setup, placeholder_text="Patient name...",
                                        font=("Courier New", 12), fg_color=C["input"],
                                        border_color=C["accent"], text_color=C["text"],
                                        height=34, width=180)
        self.name_entry.pack(padx=10, pady=(0,6))
        self.name_entry.bind("<Return>", self._start)

        self.start_btn = ctk.CTkButton(setup, text="▶  Start LEO", height=34,
                                        fg_color=C["accent"], hover_color="#00a0cc",
                                        text_color="#000", font=("Courier New", 11, "bold"),
                                        command=self._start)
        self.start_btn.pack(fill="x", padx=10, pady=(0,10))

        self.patient_name_lbl = ctk.CTkLabel(setup, text="", font=("Courier New", 14, "bold"),
                                              text_color=C["accent"])
        self.age_lbl = ctk.CTkLabel(setup, text="", font=("Courier New", 10),
                                     text_color=C["dim"])

        # Status
        ctk.CTkLabel(left, text="SYSTEM STATUS", font=("Courier New", 8),
                     text_color=C["dim"]).pack(padx=10, pady=(10,3), anchor="w")

        self.s_leo  = self._scard(left, "LEO Brain", "—")
        self.s_cam  = self._scard(left, "Camera",    "Off")
        self.s_mic  = self._scard(left, "Microphone","—")
        self.s_db   = self._scard(left, "MongoDB",   "—")
        self.s_sms  = self._scard(left, "WhatsApp",  "Ready")

        # Falls
        ctk.CTkLabel(left, text="FALLS TODAY", font=("Courier New", 8),
                     text_color=C["dim"]).pack(padx=10, pady=(12,2), anchor="w")
        fcard = ctk.CTkFrame(left, fg_color=C["card"], corner_radius=10)
        fcard.pack(fill="x", padx=10)
        self.fall_lbl = ctk.CTkLabel(fcard, text="0",
                                      font=("Courier New", 38, "bold"), text_color=C["green"])
        self.fall_lbl.pack(pady=8)

        # Camera button
        ctk.CTkLabel(left, text="MONITORING", font=("Courier New", 8),
                     text_color=C["dim"]).pack(padx=10, pady=(12,3), anchor="w")
        self.cam_btn = ctk.CTkButton(left, text="▶  Start Camera", height=36,
                                      fg_color=C["green"], hover_color="#00b050",
                                      text_color="#000", font=("Courier New", 11, "bold"),
                                      command=self._toggle_cam)
        self.cam_btn.pack(fill="x", padx=10, pady=(0,10))

    def _scard(self, parent, label, val):
        f = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=7)
        f.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(f, text=label, font=("Courier New", 10),
                     text_color=C["dim"]).pack(side="left", padx=8, pady=5)
        lbl = ctk.CTkLabel(f, text=val, font=("Courier New", 10, "bold"),
                            text_color=C["orange"])
        lbl.pack(side="right", padx=8)
        return lbl

    # ── CENTER PANEL ──────────────────────────
    def _build_center(self, parent):
        center = ctk.CTkFrame(parent, fg_color=C["panel"], corner_radius=12)
        center.grid(row=0, column=1, sticky="nsew", padx=6)
        center.rowconfigure(0, weight=0)  # video
        center.rowconfigure(1, weight=1)  # chat
        center.rowconfigure(2, weight=0)  # input
        center.columnconfigure(0, weight=1)

        # VIDEO ROW — camera + mini info side by side
        vid_row = ctk.CTkFrame(center, fg_color=C["bg"], corner_radius=10)
        vid_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,6))
        vid_row.columnconfigure(0, weight=0)
        vid_row.columnconfigure(1, weight=1)

        # Camera canvas
        cam_wrap = ctk.CTkFrame(vid_row, fg_color=C["card"], corner_radius=8,
                                 width=324, height=224)
        cam_wrap.grid(row=0, column=0)
        cam_wrap.pack_propagate(False)

        self.cam_canvas = tk.Canvas(cam_wrap, width=320, height=220,
                                     bg="#0a0a0a", highlightthickness=0)
        self.cam_canvas.pack(padx=2, pady=2)

        self.cam_placeholder = ctk.CTkLabel(cam_wrap,
                                             text="📷\nCamera Off\n\nClick 'Start Camera'\nto begin monitoring",
                                             font=("Courier New", 11), text_color=C["dim"],
                                             justify="center")
        self.cam_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # Mini stats next to video
        stats_col = ctk.CTkFrame(vid_row, fg_color=C["bg"])
        stats_col.grid(row=0, column=1, padx=(10,0), sticky="nsew")

        self.mini_state = ctk.CTkLabel(stats_col, text="STATE\n—",
                                        font=("Courier New", 12, "bold"),
                                        text_color=C["accent"], justify="center")
        self.mini_state.pack(pady=(10,4))

        mini_cards = [
            ("Detection", "—"),
            ("Posture",   "—"),
            ("Zone",      "—"),
        ]
        self.mini_lbls = {}
        for k, v in mini_cards:
            f = ctk.CTkFrame(stats_col, fg_color=C["card"], corner_radius=7)
            f.pack(fill="x", padx=6, pady=2)
            ctk.CTkLabel(f, text=k, font=("Courier New", 9),
                         text_color=C["dim"]).pack(side="left", padx=8, pady=4)
            lbl = ctk.CTkLabel(f, text=v, font=("Courier New", 10, "bold"),
                                text_color=C["text"])
            lbl.pack(side="right", padx=8)
            self.mini_lbls[k] = lbl

        self.voice_indicator = ctk.CTkLabel(stats_col, text="🎤 Listening...",
                                             font=("Courier New", 10),
                                             text_color=C["green"])
        self.voice_indicator.pack(pady=8)

        # CHAT AREA
        chat_hdr = ctk.CTkFrame(center, fg_color=C["card"], height=36, corner_radius=0)
        chat_hdr.grid(row=1, column=0, sticky="new", padx=0)
        chat_hdr.pack_propagate(False)
        ctk.CTkLabel(chat_hdr, text="💬  Conversation",
                     font=("Courier New", 11, "bold"), text_color=C["accent"]
                     ).pack(side="left", padx=14, pady=8)

        self.chat = tk.Text(center, bg=C["bg"], fg=C["text"],
                            font=("Courier New", 12), wrap="word",
                            relief="flat", borderwidth=0,
                            padx=14, pady=8, state="disabled")
        self.chat.grid(row=1, column=0, sticky="nsew", padx=0, pady=(36,0))

        sb = ctk.CTkScrollbar(center, command=self.chat.yview)
        sb.grid(row=1, column=1, sticky="ns", pady=(36,0))
        self.chat.configure(yscrollcommand=sb.set)
        center.columnconfigure(1, weight=0)

        # Tags
        self.chat.tag_configure("you",  foreground=C["accent"],  font=("Courier New", 9, "bold"))
        self.chat.tag_configure("leo",  foreground=C["purple"],  font=("Courier New", 9, "bold"))
        self.chat.tag_configure("msg",  foreground=C["text"],    font=("Courier New", 12))
        self.chat.tag_configure("sys",  foreground=C["orange"],  font=("Courier New", 10, "italic"))
        self.chat.tag_configure("time", foreground=C["dim"],     font=("Courier New", 9))
        self.chat.tag_configure("mic",  foreground=C["green"],   font=("Courier New", 10, "italic"))

        # INPUT
        inp = ctk.CTkFrame(center, fg_color=C["card"], height=64, corner_radius=0)
        inp.grid(row=2, column=0, columnspan=2, sticky="ew")
        inp.pack_propagate(False)

        self.entry = ctk.CTkEntry(inp, placeholder_text="Type here, or just speak — both work at the same time...",
                                   font=("Courier New", 12), fg_color=C["input"],
                                   border_color=C["purple"], text_color=C["text"],
                                   placeholder_text_color=C["dim"], height=40)
        self.entry.pack(side="left", fill="x", expand=True, padx=(12,8), pady=12)
        self.entry.bind("<Return>", self._send)

        ctk.CTkButton(inp, text="Send ▶", width=90, height=40,
                      fg_color=C["purple"], hover_color="#6020c0",
                      font=("Courier New", 12, "bold"),
                      command=self._send).pack(side="right", padx=(0,12))

    # ── RIGHT PANEL ────────────────────────────
    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=C["panel"], corner_radius=12, width=250)
        right.grid(row=0, column=2, sticky="nsew", padx=(6,0))
        right.pack_propagate(False)

        # Alerts
        ctk.CTkLabel(right, text="🚨  ALERTS", font=("Courier New", 10, "bold"),
                     text_color=C["red"]).pack(padx=12, pady=(12,4), anchor="w")

        self.alerts_box = ctk.CTkScrollableFrame(right, fg_color=C["bg"],
                                                  corner_radius=8, height=240)
        self.alerts_box.pack(fill="x", padx=10, pady=(0,6))

        self.no_alert_lbl = ctk.CTkLabel(self.alerts_box, text="No alerts",
                                          font=("Courier New", 10), text_color=C["dim"])
        self.no_alert_lbl.pack(pady=16)

        # Medications
        ctk.CTkLabel(right, text="💊  MEDICATIONS", font=("Courier New", 10, "bold"),
                     text_color=C["accent"]).pack(padx=12, pady=(6,4), anchor="w")

        self.meds_box = ctk.CTkScrollableFrame(right, fg_color=C["bg"],
                                                corner_radius=8, height=180)
        self.meds_box.pack(fill="x", padx=10, pady=(0,6))

        self.no_med_lbl = ctk.CTkLabel(self.meds_box, text="No medications",
                                        font=("Courier New", 10), text_color=C["dim"])
        self.no_med_lbl.pack(pady=16)

        # Quick actions
        ctk.CTkLabel(right, text="⚡  QUICK ACTIONS", font=("Courier New", 10, "bold"),
                     text_color=C["accent"]).pack(padx=12, pady=(6,4), anchor="w")

        for txt, q in [("💊 Medicines",         "what are my medicines"),
                        ("📞 Emergency contacts", "show emergency contacts"),
                        ("😴 I feel tired",       "I feel tired"),
                        ("⏰ My routine",          "what is my daily routine"),
                        ("🆘 I need help",        "help me"),]:
            ctk.CTkButton(right, text=txt, height=30, anchor="w",
                          fg_color=C["card"], hover_color=C["input"],
                          text_color=C["text"], font=("Courier New", 10),
                          command=lambda x=q: self._quick(x)
                          ).pack(fill="x", padx=10, pady=2)

    # ────────────────────────────────────────
    # ACTIONS
    # ────────────────────────────────────────
    def _start(self, event=None):
        name = self.name_entry.get().strip()
        if not name:
            return
        self.patient = name.lower().replace(" ", "_")
        self.name_entry.configure(state="disabled")
        self.start_btn.configure(state="disabled", text="Starting...")
        self.patient_name_lbl.configure(text=name.title())
        self.brain.set_patient(name)
        self.brain.start()
        # Start fall monitor
        self.fall_mon = FallMonitor(self.patient, self.out_q)
        self.fall_mon.start()
        self._sys(f"Starting LEO for patient: {name.title()}")

    def _send(self, e=None):
        text = self.entry.get().strip()
        if not text or not self.brain.ready: return
        self.entry.delete(0, "end")
        self._msg(self.patient.replace("_"," ").title() or "You", text, "you", "msg")
        self.brain.send(text)

    def _quick(self, text):
        if not self.brain.ready: return
        self._msg(self.patient.replace("_"," ").title() or "You", text, "you", "msg")
        self.brain.send(text)

    def _toggle_cam(self):
        if self.cam_thread and self.cam_thread.running:
            self.cam_thread.stop()
            self.cam_thread = None
            self.mon_proc and self.mon_proc.terminate()
            self.mon_proc = None
            self.cam_btn.configure(text="▶  Start Camera", fg_color=C["green"],
                                    hover_color="#00b050", text_color="#000")
            self.s_cam.configure(text="Off", text_color=C["orange"])
            self.cam_placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self._sys("Camera stopped.")
        else:
            # Start preview
            self.cam_placeholder.place_forget()
            self.cam_thread = CameraThread(self._update_frame, src=0)
            self.cam_thread.start()
            # Start full monitoring process
            try:
                self.mon_proc = subprocess.Popen(
                    [PYTHON, str(BASE_DIR / "final_monitering_brain.py")],
                    cwd=str(BASE_DIR),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name=="nt" else 0
                )
            except Exception as e:
                self._sys(f"Monitoring error: {e}")
            self.cam_btn.configure(text="■  Stop Camera", fg_color=C["red"],
                                    hover_color="#cc0000", text_color="#fff")
            self.s_cam.configure(text="Active", text_color=C["green"])
            self._sys("Camera monitoring started.")

    def _update_frame(self, img):
        photo = ImageTk.PhotoImage(img)
        self._photo = photo
        self.cam_canvas.after(0, lambda: self.cam_canvas.create_image(
            0, 0, image=photo, anchor="nw"))

    # ────────────────────────────────────────
    # CHAT HELPERS
    # ────────────────────────────────────────
    def _msg(self, sender, text, name_tag, msg_tag, mic=False):
        self.chat.configure(state="normal")
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"\n{sender}  ", name_tag)
        self.chat.insert("end", f"{ts}\n", "time")
        prefix = "🎤 " if mic else ""
        self.chat.insert("end", f"{prefix}{text}\n", msg_tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _sys(self, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"\n  ◆ {text}\n", "sys")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _alert(self, text, color=None):
        try: self.no_alert_lbl.destroy()
        except: pass
        card = ctk.CTkFrame(self.alerts_box, fg_color=C["card"], corner_radius=8)
        card.pack(fill="x", pady=3)
        ts = datetime.now().strftime("%H:%M")
        ctk.CTkLabel(card, text=f"🚨 {ts}", font=("Courier New", 9),
                     text_color=C["red"]).pack(anchor="w", padx=8, pady=(6,0))
        ctk.CTkLabel(card, text=text, font=("Courier New", 10),
                     text_color=C["text"], wraplength=200,
                     justify="left").pack(anchor="w", padx=8, pady=(0,6))

    def _load_meds(self, meds):
        try: self.no_med_lbl.destroy()
        except: pass
        for m in meds[:8]:
            f = ctk.CTkFrame(self.meds_box, fg_color=C["card"], corner_radius=6)
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=m.get("medicine","?"),
                         font=("Courier New", 10, "bold"), text_color=C["text"]
                         ).pack(anchor="w", padx=8, pady=(4,0))
            ctk.CTkLabel(f, text=f"{m.get('time','?')}  •  {m.get('dose','?')}",
                         font=("Courier New", 9), text_color=C["dim"]
                         ).pack(anchor="w", padx=8, pady=(0,4))

    # ────────────────────────────────────────
    # POLL QUEUE
    # ────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                ev, data = self.out_q.get_nowait()

                if ev == "leo":
                    self._msg("LEO", data, "leo", "msg")

                elif ev == "voice":
                    name = self.patient.replace("_"," ").title() or "You"
                    self._msg(name, data, "you", "msg", mic=True)

                elif ev == "sys":
                    self._sys(data)
                    self.status_lbl.configure(text=f"● {data[:40]}", text_color=C["orange"])

                elif ev == "ready":
                    name = data["name"]
                    meds = data["meds"]
                    self.status_lbl.configure(text="● Running", text_color=C["green"])
                    self.s_leo.configure(text="Active",    text_color=C["green"])
                    self.s_mic.configure(text="Listening", text_color=C["green"])
                    self.voice_indicator.configure(text="🎤 Listening...", text_color=C["green"])
                    self.patient_name_lbl.pack(pady=(0,2))
                    self.age_lbl.configure(text=f"Age {data['profile'].get('personal',{}).get('age','?')}")
                    self.age_lbl.pack(pady=(0,8))
                    self.start_btn.configure(text="✓ LEO Active", state="disabled",
                                             fg_color=C["green"])
                    if meds: self._load_meds(meds)
                    self._sys(f"LEO ready for {name}")

                elif ev == "db":
                    col = C["green"] if data == "Connected" else C["orange"]
                    self.s_db.configure(text=data, text_color=col)

                elif ev == "fall":
                    # Fall detected via MongoDB
                    self.fall_count += 1
                    self.fall_lbl.configure(text=str(self.fall_count), text_color=C["red"])
                    score = data.get("score", 0)
                    ts    = data.get("time", "")
                    clip  = data.get("clip_path", "")
                    clip_name = Path(clip).name if clip else "No clip"
                    self._alert(f"FALL at {ts}\nScore: {score}\n{clip_name}")
                    self._sys(f"FALL DETECTED — Score:{score} — WhatsApp sent!")
                    self.title("🚨 FALL DETECTED — LEO")
                    self.after(5000, lambda: self.title("LEO — AI Home Assistant"))
                    # Send WhatsApp
                    try:
                        from twilio_alerts import twilio_alerts
                        from patait_info_collector import _load_existing
                        profile  = _load_existing(self.patient)
                        contacts = profile.get("emergency_contacts", [])
                        threading.Thread(
                            target=twilio_alerts.send_fall_alert,
                            kwargs=dict(patient=self.patient, contacts=contacts,
                                        clip_path=clip, score=score),
                            daemon=True
                        ).start()
                    except Exception as e:
                        self._sys(f"WhatsApp error: {e}")

                elif ev == "error":
                    self._sys(f"Error: {data}")
                    self.status_lbl.configure(text="● Error", text_color=C["red"])

        except queue.Empty:
            pass
        self.after(200, self._poll)

    def on_close(self):
        if self.cam_thread:  self.cam_thread.stop()
        if self.mon_proc:    self.mon_proc.terminate()
        if self.fall_mon:    self.fall_mon.stop()
        self.brain.stop()
        self.destroy()


# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    app = LeoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()