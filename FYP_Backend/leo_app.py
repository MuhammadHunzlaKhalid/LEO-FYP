# """
# LEO — Desktop GUI v3
# Detection video plays INSIDE the app window.
# Bigger video, smaller chat. No separate windows.

# FIXES APPLIED:
#   1. Duplicate _display_loop bug — loop now self-terminates when camera stops,
#      guarded by _display_loop_active flag so only one loop runs at a time.
#   2. Motion state reset on video loop — prev_gray/cy/area/ar reset to None
#      when video seeks back to frame 0 (fix is in monitoring_stream.py).
# """
# import customtkinter as ctk
# import tkinter as tk
# from PIL import Image, ImageTk
# import threading, queue, subprocess, sys, os, time, json, webbrowser, math
# from PIL import Image
# import numpy as np
# from pathlib import Path
# from datetime import datetime

# BASE_DIR = Path(__file__).parent
# PYTHON   = sys.executable

# ctk.set_appearance_mode("dark")
# ctk.set_default_color_theme("blue")

# C = dict(
#     bg="#090b12", panel="#0f1120", card="#151827",
#     input="#1a1e30", accent="#00c8ff", purple="#7c3aed",
#     green="#00e676", red="#ff3d3d", orange="#ff9800",
#     text="#dde1f5", dim="#566080", border="#1e2340",
# )

# VIDEO_W, VIDEO_H = 620, 460   # detection video size in GUI


# class LeoBrain(threading.Thread):
#     def __init__(self, out_q):
#         super().__init__(daemon=True)
#         self.out_q = out_q
#         self.in_q  = queue.Queue()
#         self.leo = self.tts = self.bg = None
#         self.ready = False
#         self.patient_name = None

#     def set_patient(self, name):
#         self.patient_name = name.lower().replace(" ", "_")

#     def run(self):
#         try:
#             while not self.patient_name:
#                 time.sleep(0.1)
#             self.out_q.put(("sys", "Loading patient profile..."))
#             sys.path.insert(0, str(BASE_DIR))
#             from patait_info_collector import _profile_exists, _load_existing
#             from mongo_storage import leo_db
#             from audio import Leo, VoiceOutput, BackgroundListener

#             if _profile_exists(self.patient_name):
#                 profile = _load_existing(self.patient_name)
#             else:
#                 profile = {"personal": {"name": self.patient_name},
#                            "emergency_contacts": [], "contacts": [],
#                            "medications": [], "routine": {}, "active_zones": []}

#             if leo_db.connected:
#                 leo_db.save_patient(profile)
#                 self.out_q.put(("db", "Connected"))
#             else:
#                 self.out_q.put(("db", "Offline"))

#             self.out_q.put(("sys", "Loading Qwen LLM..."))
#             self.leo = Leo(self.patient_name, preloaded_profile=profile)
#             self.out_q.put(("sys", "Loading Kokoro TTS..."))
#             self.tts = VoiceOutput()
#             self.out_q.put(("sys", "Starting mic listener (Whisper)..."))

#             def on_voice(text):
#                 self.out_q.put(("voice", text))
#                 self._respond(text)

#             self.bg = BackgroundListener(on_voice, whisper_model="base")
#             self.bg.start()

#             self.ready = True
#             name = profile.get("personal", {}).get("name", self.patient_name)
#             self.out_q.put(("ready", {"name": name,
#                                        "meds": profile.get("medications", []),
#                                        "profile": profile}))
#             hour = datetime.now().hour
#             g = "Good morning" if hour<12 else ("Good afternoon" if hour<18 else "Good evening")
#             msg = f"{g}, {name}! I am Leo. You can type or speak — I am always listening."
#             self.out_q.put(("leo", msg))
#             self._speak(msg)

#             while True:
#                 try:
#                     self._respond(self.in_q.get(timeout=0.5))
#                 except queue.Empty:
#                     pass
#         except Exception as e:
#             self.out_q.put(("error", str(e)))

#     def _respond(self, text):
#         if not self.leo or not text: return
#         try:
#             resp = self.leo.respond(text)
#             self.out_q.put(("leo", resp))
#             self._speak(resp)
#         except Exception as e:
#             self.out_q.put(("error", str(e)))

#     def _speak(self, t):
#         if self.tts and self.tts.available:
#             threading.Thread(target=self.tts.speak, args=(t,), daemon=True).start()

#     def send(self, t): self.in_q.put(t)
#     def stop(self):
#         if self.bg: self.bg.stop()


# class FallMonitor(threading.Thread):
#     def __init__(self, patient, out_q):
#         super().__init__(daemon=True)
#         self.patient = patient; self.out_q = out_q
#         self.running = True; self.last_seen = None

#     def run(self):
#         try:
#             sys.path.insert(0, str(BASE_DIR))
#             from mongo_storage import leo_db
#             if not leo_db.connected: return
#             last = leo_db._col("fall_events").find_one(
#                 {"patient": self.patient}, sort=[("timestamp", -1)])
#             self.last_seen = last["timestamp"] if last else datetime.min
#             while self.running:
#                 time.sleep(4)
#                 new = leo_db._col("fall_events").find_one(
#                     {"patient": self.patient,
#                      "timestamp": {"$gt": self.last_seen}},
#                     sort=[("timestamp", -1)])
#                 if new:
#                     self.last_seen = new["timestamp"]
#                     self.out_q.put(("fall", new))
#         except: pass

#     def stop(self): self.running = False


# class LeoApp(ctk.CTk):
#     def __init__(self):
#         super().__init__()
#         self.title("LEO — AI Home Assistant")
#         self.geometry("1400x860")
#         self.minsize(1200, 720)
#         self.configure(fg_color=C["bg"])

#         self.out_q   = queue.Queue()
#         self.brain   = LeoBrain(self.out_q)
#         self.mon     = None    # MonitoringStream thread
#         self.fall_m  = None
#         self.fall_c  = 0
#         self.patient = ""
#         self._photo  = None
#         self._last_frame_data = None   # skip PIL if frame hasn't changed

#         # ── FIX 1: guard flag — ensures only ONE _display_loop runs at a time
#         self._display_loop_active = False

#         self._build()
#         self.after(200, self._poll)

#     # ── BUILD ────────────────────────────────
#     def _build(self):
#         # Top bar
#         top = ctk.CTkFrame(self, fg_color=C["panel"], height=54, corner_radius=0)
#         top.pack(fill="x"); top.pack_propagate(False)
#         ctk.CTkLabel(top, text="LEO", font=("Courier New",22,"bold"),
#                      text_color=C["accent"]).pack(side="left",padx=18)
#         ctk.CTkLabel(top, text="AI-Powered Elder Care  |  FYP 2024-25",
#                      font=("Courier New",10), text_color=C["dim"]).pack(side="left")
#         self.status_lbl = ctk.CTkLabel(top, text="● Enter patient name",
#                                         font=("Courier New",10), text_color=C["orange"])
#         self.status_lbl.pack(side="right", padx=20)
#         ctk.CTkButton(top, text="Dashboard", width=110, height=30,
#                       fg_color=C["card"], hover_color=C["input"],
#                       border_width=1, border_color=C["accent"],
#                       text_color=C["accent"], font=("Courier New",10),
#                       command=lambda: webbrowser.open("http://localhost:5000")
#                       ).pack(side="right", padx=8, pady=12)

#         # Main 3-col layout
#         main = ctk.CTkFrame(self, fg_color=C["bg"])
#         main.pack(fill="both", expand=True, padx=10, pady=(0,10))
#         main.columnconfigure(0, weight=0, minsize=200)
#         main.columnconfigure(1, weight=1)
#         main.columnconfigure(2, weight=0, minsize=240)
#         main.rowconfigure(0, weight=1)

#         self._build_left(main)
#         self._build_center(main)
#         self._build_right(main)

#     def _build_left(self, p):
#         left = ctk.CTkFrame(p, fg_color=C["panel"], corner_radius=12, width=200)
#         left.grid(row=0, column=0, sticky="nsew", padx=(0,6))
#         left.pack_propagate(False)

#         # Patient card
#         pc = ctk.CTkFrame(left, fg_color=C["card"], corner_radius=10)
#         pc.pack(fill="x", padx=10, pady=(12,6))
#         ctk.CTkLabel(pc, text="PATIENT", font=("Courier New",8),
#                      text_color=C["dim"]).pack(pady=(8,2))
#         self.name_entry = ctk.CTkEntry(pc, placeholder_text="Patient name...",
#                                         font=("Courier New",12), fg_color=C["input"],
#                                         border_color=C["accent"], text_color=C["text"],
#                                         height=34, width=170)
#         self.name_entry.pack(padx=10, pady=(0,6))
#         self.name_entry.bind("<Return>", self._start)
#         self.start_btn = ctk.CTkButton(pc, text="▶  Start LEO", height=34,
#                                         fg_color=C["accent"], hover_color="#00a0cc",
#                                         text_color="#000", font=("Courier New",11,"bold"),
#                                         command=self._start)
#         self.start_btn.pack(fill="x", padx=10, pady=(0,10))
#         self.pt_lbl  = ctk.CTkLabel(pc, text="", font=("Courier New",14,"bold"),
#                                      text_color=C["accent"])
#         self.age_lbl = ctk.CTkLabel(pc, text="", font=("Courier New",10),
#                                      text_color=C["dim"])

#         # Status
#         ctk.CTkLabel(left, text="SYSTEM STATUS", font=("Courier New",8),
#                      text_color=C["dim"]).pack(padx=10, pady=(10,2), anchor="w")
#         self.s_leo = self._sc(left, "LEO Brain", "—")
#         self.s_cam = self._sc(left, "Camera",    "Off")
#         self.s_mic = self._sc(left, "Mic",       "—")
#         self.s_db  = self._sc(left, "MongoDB",   "—")
#         self.s_sms = self._sc(left, "WhatsApp",  "Ready")

#         # Falls
#         ctk.CTkLabel(left, text="FALLS TODAY", font=("Courier New",8),
#                      text_color=C["dim"]).pack(padx=10, pady=(12,2), anchor="w")
#         fc = ctk.CTkFrame(left, fg_color=C["card"], corner_radius=10)
#         fc.pack(fill="x", padx=10)
#         self.fall_lbl = ctk.CTkLabel(fc, text="0",
#                                       font=("Courier New",40,"bold"),
#                                       text_color=C["green"])
#         self.fall_lbl.pack(pady=8)

#         # Camera toggle
#         ctk.CTkLabel(left, text="MONITORING", font=("Courier New",8),
#                      text_color=C["dim"]).pack(padx=10, pady=(12,3), anchor="w")
#         self.cam_btn = ctk.CTkButton(left, text="▶  Start Camera", height=36,
#                                       fg_color=C["green"], hover_color="#00b050",
#                                       text_color="#000", font=("Courier New",11,"bold"),
#                                       command=self._toggle_cam)
#         self.cam_btn.pack(fill="x", padx=10, pady=(0,10))

#         # State label
#         ctk.CTkLabel(left, text="CURRENT STATE", font=("Courier New",8),
#                      text_color=C["dim"]).pack(padx=10, pady=(6,2), anchor="w")
#         self.state_lbl = ctk.CTkLabel(left, text="—",
#                                        font=("Courier New",13,"bold"),
#                                        text_color=C["accent"], wraplength=180)
#         self.state_lbl.pack(padx=10)

#     def _sc(self, parent, label, val):
#         f = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=7)
#         f.pack(fill="x", padx=10, pady=2)
#         ctk.CTkLabel(f, text=label, font=("Courier New",9),
#                      text_color=C["dim"]).pack(side="left", padx=8, pady=4)
#         lbl = ctk.CTkLabel(f, text=val, font=("Courier New",9,"bold"),
#                             text_color=C["orange"])
#         lbl.pack(side="right", padx=8)
#         return lbl

#     def _build_center(self, p):
#         center = ctk.CTkFrame(p, fg_color=C["panel"], corner_radius=12)
#         center.grid(row=0, column=1, sticky="nsew", padx=6)
#         center.rowconfigure(0, weight=3)   # VIDEO — big
#         center.rowconfigure(1, weight=1)   # CHAT  — small
#         center.rowconfigure(2, weight=0)   # INPUT
#         center.columnconfigure(0, weight=1)

#         # ── VIDEO AREA (big) ──────────────────
#         vid_frame = ctk.CTkFrame(center, fg_color=C["bg"], corner_radius=10)
#         vid_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10,4))

#         self.vid_canvas = tk.Canvas(vid_frame, bg="#050508",
#                                      highlightthickness=0)
#         self.vid_canvas.pack(fill="both", expand=True, padx=2, pady=2)
#         # Create ONE image item — reuse it every frame (no flicker)
#         self._canvas_img_id = None
#         self._last_cw = 0; self._last_ch = 0   # cache canvas size
#         self._photo_keep = []   # keeps last PhotoImage alive — prevents GC flicker

#         # Placeholder
#         self.vid_placeholder = ctk.CTkLabel(
#             vid_frame,
#             text="📷\n\nCamera is OFF\n\nEnter patient name & click Start LEO\nthen click Start Camera",
#             font=("Courier New",13), text_color=C["dim"], justify="center")
#         self.vid_placeholder.place(relx=0.5, rely=0.5, anchor="center")

#         # Voice indicator overlay
#         self.mic_lbl = ctk.CTkLabel(center, text="",
#                                      font=("Courier New",10),
#                                      text_color=C["green"])
#         self.mic_lbl.grid(row=0, column=0, sticky="se", padx=18, pady=12)

#         # ── CHAT AREA (small) ─────────────────
#         chat_hdr = ctk.CTkFrame(center, fg_color=C["card"], height=30, corner_radius=0)
#         chat_hdr.grid(row=1, column=0, sticky="new")
#         chat_hdr.pack_propagate(False)
#         ctk.CTkLabel(chat_hdr, text="💬  Conversation with LEO",
#                      font=("Courier New",10,"bold"), text_color=C["accent"]
#                      ).pack(side="left", padx=12, pady=6)

#         self.chat = tk.Text(center, bg=C["card"], fg=C["text"],
#                             font=("Courier New",11), wrap="word",
#                             relief="flat", borderwidth=0,
#                             padx=12, pady=6, state="disabled", height=7)
#         self.chat.grid(row=1, column=0, sticky="nsew", pady=(30,0))
#         self.chat.tag_configure("you",  foreground=C["accent"],  font=("Courier New",9,"bold"))
#         self.chat.tag_configure("leo",  foreground="#a78bfa",    font=("Courier New",9,"bold"))
#         self.chat.tag_configure("msg",  foreground=C["text"],    font=("Courier New",11))
#         self.chat.tag_configure("sys",  foreground=C["orange"],  font=("Courier New",9,"italic"))
#         self.chat.tag_configure("time", foreground=C["dim"],     font=("Courier New",8))

#         # ── INPUT ─────────────────────────────
#         inp = ctk.CTkFrame(center, fg_color=C["card"], height=56, corner_radius=0)
#         inp.grid(row=2, column=0, sticky="ew")
#         inp.pack_propagate(False)

#         self.entry = ctk.CTkEntry(
#             inp, placeholder_text="Type here, or just speak — both work at the same time...",
#             font=("Courier New",12), fg_color=C["input"],
#             border_color=C["purple"], text_color=C["text"],
#             placeholder_text_color=C["dim"], height=38)
#         self.entry.pack(side="left", fill="x", expand=True, padx=(12,8), pady=9)
#         self.entry.bind("<Return>", self._send)

#         ctk.CTkButton(inp, text="Send ▶", width=88, height=38,
#                       fg_color=C["purple"], hover_color="#6020c0",
#                       font=("Courier New",12,"bold"),
#                       command=self._send).pack(side="right", padx=(0,10))

#     def _build_right(self, p):
#         right = ctk.CTkFrame(p, fg_color=C["panel"], corner_radius=12, width=240)
#         right.grid(row=0, column=2, sticky="nsew", padx=(6,0))
#         right.pack_propagate(False)

#         ctk.CTkLabel(right, text="🚨  ALERTS", font=("Courier New",10,"bold"),
#                      text_color=C["red"]).pack(padx=12, pady=(12,4), anchor="w")
#         self.alerts_box = ctk.CTkScrollableFrame(right, fg_color=C["bg"],
#                                                   corner_radius=8, height=260)
#         self.alerts_box.pack(fill="x", padx=10, pady=(0,6))
#         self.no_alert = ctk.CTkLabel(self.alerts_box, text="No alerts",
#                                       font=("Courier New",10), text_color=C["dim"])
#         self.no_alert.pack(pady=16)

#         ctk.CTkLabel(right, text="💊  MEDICATIONS", font=("Courier New",10,"bold"),
#                      text_color=C["accent"]).pack(padx=12, pady=(6,4), anchor="w")
#         self.meds_box = ctk.CTkScrollableFrame(right, fg_color=C["bg"],
#                                                 corner_radius=8, height=170)
#         self.meds_box.pack(fill="x", padx=10, pady=(0,6))
#         self.no_med = ctk.CTkLabel(self.meds_box, text="No medications",
#                                     font=("Courier New",10), text_color=C["dim"])
#         self.no_med.pack(pady=16)

#         ctk.CTkLabel(right, text="⚡  QUICK ACTIONS", font=("Courier New",10,"bold"),
#                      text_color=C["accent"]).pack(padx=12, pady=(6,4), anchor="w")
#         for txt, q in [("💊 My medicines",        "what are my medicines"),
#                         ("📞 Emergency contacts",  "show emergency contacts"),
#                         ("😴 I feel tired",        "I feel tired"),
#                         ("⏰ My routine",           "what is my daily routine"),
#                         ("🆘 Help me",             "help me"),]:
#             ctk.CTkButton(right, text=txt, height=30, anchor="w",
#                           fg_color=C["card"], hover_color=C["input"],
#                           text_color=C["text"], font=("Courier New",10),
#                           command=lambda x=q: self._quick(x)
#                           ).pack(fill="x", padx=10, pady=2)

#     # ── ACTIONS ──────────────────────────────
#     def _start(self, e=None):
#         name = self.name_entry.get().strip()
#         if not name: return
#         self.patient = name.lower().replace(" ", "_")
#         self.name_entry.configure(state="disabled")
#         self.start_btn.configure(state="disabled", text="Starting...")
#         self.brain.set_patient(name)
#         self.brain.start()
#         self.fall_m = FallMonitor(self.patient, self.out_q)
#         self.fall_m.start()
#         self._sys(f"Starting LEO for {name.title()}...")

#     def _send(self, e=None):
#         text = self.entry.get().strip()
#         if not text or not self.brain.ready: return
#         self.entry.delete(0, "end")
#         n = self.patient.replace("_"," ").title() or "You"
#         self._msg(n, text, "you", "msg")
#         self.brain.send(text)

#     def _quick(self, text):
#         if not self.brain.ready: return
#         n = self.patient.replace("_"," ").title() or "You"
#         self._msg(n, text, "you", "msg")
#         self.brain.send(text)

#     def _toggle_cam(self):
#         if self.mon and self.mon.running:
#             # ── Stop camera ───────────────────────────────────────────────
#             self.mon.stop()
#             self.mon = None
#             # _display_loop_active will be set to False by the loop itself
#             # once it sees self.mon is None — no manual reset needed.
#             self._canvas_img_id = None
#             self._last_frame_data = None
#             self.vid_canvas.delete("all")
#             self.cam_btn.configure(text="▶  Start Camera",
#                                     fg_color=C["green"], hover_color="#00b050",
#                                     text_color="#000")
#             self.s_cam.configure(text="Off", text_color=C["orange"])
#             self.vid_placeholder.place(relx=0.5, rely=0.5, anchor="center")
#             self.state_lbl.configure(text="—")
#             self._sys("Camera stopped.")
#         else:
#             # ── Start camera ──────────────────────────────────────────────
#             self.vid_placeholder.place_forget()
#             try:
#                 from monitoring_stream import MonitoringStream
#                 self.mon = MonitoringStream(
#                     patient_name = self.patient,
#                     frame_cb     = self._on_frame,
#                     fall_cb      = self._on_fall_detected,
#                 )
#                 self.mon.start()

#                 # ── FIX 1: only spawn one display loop, even on restart ──
#                 if not self._display_loop_active:
#                     self._display_loop_active = True
#                     self._display_loop()

#                 self.cam_btn.configure(text="■  Stop Camera",
#                                         fg_color=C["red"], hover_color="#cc0000",
#                                         text_color="#fff")
#                 self.s_cam.configure(text="Active", text_color=C["green"])
#                 self._sys("Camera monitoring started (YOLO running)...")
#             except Exception as ex:
#                 self._sys(f"Camera error: {ex}")

#     def _on_frame(self, frame_rgb, state, score):
#         """Not used directly — display loop reads from buffer."""
#         pass

#     def _display_loop(self):
#         """
#         Runs every 33ms (~30fps) in the main thread.

#         FIX 1 — Self-terminating loop:
#           When the camera is stopped (self.mon is None or not running),
#           the loop clears _display_loop_active and returns WITHOUT
#           rescheduling itself.  This means:
#             • No ghost loops accumulate across camera stop/start cycles.
#             • The guard in _toggle_cam ensures only one loop starts at a time.
#         """
#         # ── Check if camera is still alive ────────────────────────────────
#         if not self.mon or not self.mon.running:
#             self._display_loop_active = False   # allow next start to spawn fresh loop
#             return                               # do NOT reschedule — loop ends here

#         # ── Read latest frame from Thread 1 buffer ────────────────────────
#         with self.mon._lock:
#             data = self.mon.latest_frame

#         # Only run PIL conversion when there is a NEW frame.
#         if data is not None and data is not self._last_frame_data:
#             self._last_frame_data = data
#             frame_rgb, state, score = data
#             try:
#                 cw = self.vid_canvas.winfo_width()
#                 ch = self.vid_canvas.winfo_height()
#                 if cw < 10: cw = VIDEO_W
#                 if ch < 10: ch = VIDEO_H

#                 h, w = frame_rgb.shape[:2]
#                 scale = min(cw / w, ch / h)
#                 nw = max(1, int(w * scale))
#                 nh = max(1, int(h * scale))

#                 # Fast resize
#                 img   = Image.fromarray(frame_rgb)
#                 img   = img.resize((nw, nh), Image.NEAREST)
#                 photo = ImageTk.PhotoImage(img)
#                 # Keep last 2 photos alive — prevents GC flicker
#                 self._photo_keep = [photo] + self._photo_keep[:1]

#                 if self._canvas_img_id is None:
#                     # First frame — create the image item once
#                     self._canvas_img_id = self.vid_canvas.create_image(
#                         cw // 2, ch // 2, image=photo, anchor="center")
#                 else:
#                     # All subsequent frames — just update, no delete/create
#                     self.vid_canvas.itemconfig(self._canvas_img_id, image=photo)
#                     # Only reposition if canvas was resized
#                     if cw != self._last_cw or ch != self._last_ch:
#                         self.vid_canvas.coords(
#                             self._canvas_img_id, cw // 2, ch // 2)
#                         self._last_cw = cw
#                         self._last_ch = ch

#                 self.state_lbl.configure(text=state)
#             except Exception:
#                 pass

#         # ── Reschedule only while camera is alive ─────────────────────────
#         self.after(33, self._display_loop)

#     def _on_fall_detected(self, score, reason, posture, clip_path=""):
#         """Called by MonitoringStream when fall detected — send WhatsApp."""
#         self.out_q.put(("fall_direct", {
#             "score":     score,
#             "reason":    reason,
#             "posture":   posture,
#             "time":      datetime.now().strftime("%H:%M:%S"),
#             "clip_path": clip_path,
#         }))

#     # ── CHAT ─────────────────────────────────
#     def _msg(self, sender, text, ntag, mtag, mic=False):
#         self.chat.configure(state="normal")
#         ts = datetime.now().strftime("%H:%M")
#         self.chat.insert("end", f"\n{sender}  ", ntag)
#         self.chat.insert("end", f"{ts}\n", "time")
#         self.chat.insert("end", f"{'🎤 ' if mic else ''}{text}\n", mtag)
#         self.chat.configure(state="disabled")
#         self.chat.see("end")

#     def _sys(self, text):
#         self.chat.configure(state="normal")
#         self.chat.insert("end", f"\n  ◆ {text}\n", "sys")
#         self.chat.configure(state="disabled")
#         self.chat.see("end")

#     def _alert_card(self, text):
#         try: self.no_alert.destroy()
#         except: pass
#         card = ctk.CTkFrame(self.alerts_box, fg_color=C["card"], corner_radius=8)
#         card.pack(fill="x", pady=3)
#         ts = datetime.now().strftime("%H:%M")
#         ctk.CTkLabel(card, text=f"🚨 {ts}", font=("Courier New",9),
#                      text_color=C["red"]).pack(anchor="w", padx=8, pady=(6,0))
#         ctk.CTkLabel(card, text=text, font=("Courier New",10),
#                      text_color=C["text"], wraplength=200,
#                      justify="left").pack(anchor="w", padx=8, pady=(0,6))

#     def _load_meds(self, meds):
#         try: self.no_med.destroy()
#         except: pass
#         for m in meds[:8]:
#             f = ctk.CTkFrame(self.meds_box, fg_color=C["card"], corner_radius=6)
#             f.pack(fill="x", pady=2)
#             ctk.CTkLabel(f, text=m.get("medicine","?"),
#                          font=("Courier New",10,"bold"), text_color=C["text"]
#                          ).pack(anchor="w", padx=8, pady=(4,0))
#             ctk.CTkLabel(f, text=f"{m.get('time','?')}  •  {m.get('dose','?')}",
#                          font=("Courier New",9), text_color=C["dim"]
#                          ).pack(anchor="w", padx=8, pady=(0,4))

#     def _do_fall_whatsapp(self, data):
#         """Send WhatsApp alert for fall — runs in thread.

#         ALL tkinter updates go through out_q — direct widget calls from
#         threads are not thread-safe and silently fail in tkinter.
#         """
#         try:
#             self.out_q.put(("whatsapp_status", "Sending..."))
#             from twilio_alerts import twilio_alerts
#             from patait_info_collector import _load_existing
#             profile  = _load_existing(self.patient)
#             contacts = profile.get("emergency_contacts", [])

#             if not contacts:
#                 self.out_q.put(("whatsapp_status", "No contacts"))
#                 self.out_q.put(("sys", "WhatsApp: No emergency contacts configured!"))
#                 return

#             ok = twilio_alerts.send_fall_alert(
#                 patient   = self.patient,
#                 contacts  = contacts,
#                 clip_path = data.get("clip_path", ""),
#                 score     = data.get("score", 0),
#                 posture   = data.get("posture", "lying"),
#             )
#             if ok:
#                 self.out_q.put(("whatsapp_status", "Sent ✓"))
#                 self.out_q.put(("sys", "WhatsApp sent to emergency contacts!"))
#             else:
#                 self.out_q.put(("whatsapp_status", "Send Failed"))
#                 self.out_q.put(("sys", "WhatsApp: Send failed — check Twilio logs (daily limit?)"))
#         except Exception as e:
#             self.out_q.put(("whatsapp_status", "Error"))
#             self.out_q.put(("sys", f"WhatsApp error: {e}"))

#     # ── POLL QUEUE ────────────────────────────
#     def _poll(self):
#         try:
#             while True:
#                 ev, data = self.out_q.get_nowait()
#                 if ev == "leo":
#                     self._msg("LEO", data, "leo", "msg")
#                 elif ev == "voice":
#                     n = self.patient.replace("_"," ").title() or "You"
#                     self._msg(n, data, "you", "msg", mic=True)
#                     self.mic_lbl.configure(text=f"🎤 Heard: {data[:40]}")
#                     self.after(3000, lambda: self.mic_lbl.configure(text=""))
#                 elif ev == "sys":
#                     self._sys(data)
#                     self.status_lbl.configure(text=f"● {data[:38]}", text_color=C["orange"])
#                 elif ev == "ready":
#                     self.status_lbl.configure(text="● Running", text_color=C["green"])
#                     self.s_leo.configure(text="Active",    text_color=C["green"])
#                     self.s_mic.configure(text="Listening", text_color=C["green"])
#                     name = data["name"]
#                     self.pt_lbl.configure(text=name.title()); self.pt_lbl.pack(pady=(0,2))
#                     age = data["profile"].get("personal",{}).get("age","?")
#                     self.age_lbl.configure(text=f"Age {age}"); self.age_lbl.pack(pady=(0,8))
#                     self.start_btn.configure(text="✓ LEO Active", state="disabled",
#                                              fg_color=C["green"])
#                     if data["meds"]: self._load_meds(data["meds"])
#                     self._sys(f"LEO ready for {name}")
#                 elif ev == "db":
#                     col = C["green"] if data == "Connected" else C["orange"]
#                     self.s_db.configure(text=data, text_color=col)
#                 elif ev in ("fall", "fall_direct"):
#                     self.fall_c += 1
#                     self.fall_lbl.configure(text=str(self.fall_c), text_color=C["red"])
#                     score = data.get("score", 0)
#                     ts    = data.get("time","") or data.get("timestamp","")
#                     clip  = data.get("clip_path","")
#                     self._alert_card(f"FALL DETECTED\nTime: {ts}\nScore: {score}")
#                     self._sys(f"FALL! Score:{score} — Sending WhatsApp...")
#                     self.title("🚨 FALL DETECTED — LEO")
#                     self.after(5000, lambda: self.title("LEO — AI Home Assistant"))
#                     threading.Thread(target=self._do_fall_whatsapp,
#                                      args=(data,), daemon=True).start()
#                 elif ev == "whatsapp_status":
#                     if "Sent" in data:
#                         col = C["green"]
#                     elif data == "Sending...":
#                         col = C["orange"]
#                     else:
#                         col = C["red"]
#                     self.s_sms.configure(text=data, text_color=col)
#                 elif ev == "error":
#                     self._sys(f"Error: {data}")
#                     self.status_lbl.configure(text="● Error", text_color=C["red"])
#         except queue.Empty:
#             pass
#         self.after(200, self._poll)

#     def on_close(self):
#         if self.mon:    self.mon.stop()
#         if self.fall_m: self.fall_m.stop()
#         self.brain.stop()
#         self.destroy()


# if __name__ == "__main__":
#     app = LeoApp()
#     app.protocol("WM_DELETE_WINDOW", app.on_close)
#     app.mainloop()











"""
LEO — Desktop GUI v5 (Final PC Version)
=========================================
FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman

PROJECT: AI-Powered Home Assistant for the Elderly

COMPLETE FEATURE LIST (per proposal):
  ✓ Real-time fall detection via YOLO (GPU-accelerated)
  ✓ Patient profile setup (full GUI wizard — no terminal)
  ✓ Safe zone drawing (bed/sofa zones on camera frame)
  ✓ Voice commands via Whisper microphone listener
  ✓ Natural language chat via Qwen LLM
  ✓ Kokoro TTS voice responses
  ✓ WhatsApp alerts via Twilio on fall detection
  ✓ MongoDB storage (patients, falls, activity logs, sessions)
  ✓ History window — falls, activity log, conversations
  ✓ Medication schedule display and reminders
  ✓ Caregiver dashboard (Flask web app at localhost:5000)
  ✓ Continuous video recording + fall clip saving

STARTUP FLOW:
  1. Patient Setup Wizard (GUI — name → info → contacts → meds → routine)
  2. Safe Zone Setup (draw bed/sofa zones on live video frame)
  3. Main Monitoring Window
       Left:   Patient card, system status, falls counter, camera controls
       Center: Live detection video, LEO conversation, text input
       Right:  Alerts, medications, quick actions
  4. History Window (button) — falls, activity log, conversations
"""

import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import threading, queue, sys, time, json, webbrowser, re, math
import requests, base64, io
from pathlib import Path
from datetime import datetime, timedelta

# ─── FastAPI push — live video + state to Flutter app ─────────────
_API_BASE   = "http://localhost:8000"
_push_q     = queue.Queue(maxsize=3)
_push_patient = ""   # set when patient loads

def _api_pusher():
    while True:
        try:
            payload = _push_q.get(timeout=1)
            try:
                requests.post(f"{_API_BASE}/video/push-frame",
                              json=payload, timeout=0.4)
            except Exception:
                pass
        except queue.Empty:
            pass

threading.Thread(target=_api_pusher, daemon=True, name="APIPusher").start()

def _push_frame_to_api(frame_rgb, state, score, fall_detected=False,
                       on_safe_zone=False, posture="unknown"):
    """Encode RGB frame with PIL (no cv2 needed) and push to FastAPI."""
    try:
        buf = io.BytesIO()
        Image.fromarray(frame_rgb).save(buf, format="JPEG", quality=65)
        b64 = base64.b64encode(buf.getvalue()).decode()
        payload = {
            "frame_b64":     b64,
            "state":         str(state),
            "posture":       str(posture),
            "fall_detected": bool(fall_detected),
            "on_safe_zone":  bool(on_safe_zone),
            "confidence":    round(min(float(score) / 4.0, 1.0), 3),
            "patient":       _push_patient,
        }
        if _push_q.full():
            try: _push_q.get_nowait()
            except queue.Empty: pass
        _push_q.put_nowait(payload)
    except Exception:
        pass
# ──────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C = dict(
    bg="#090b12", panel="#0f1120", card="#151827",
    input="#1a1e30", accent="#00c8ff", purple="#7c3aed",
    green="#00e676", red="#ff3d3d", orange="#ff9800",
    text="#dde1f5", dim="#566080", border="#1e2340",
    yellow="#ffd600",
)

ZONE_COLORS_BGR  = {"bed": (0,200,255),  "sofa": (0,140,255)}
ZONE_COLORS_HEX  = {"bed": "#00c8ff",   "sofa": "#008cff"}
FRAME_W, FRAME_H = 640, 480
VIDEO_W, VIDEO_H = 620, 460

# ── monitoring_stream VIDEO_PATH (used for zone setup preview) ─────────────
try:
    import monitoring_stream as _ms
    _VIDEO_PATH = _ms.VIDEO_PATH
except Exception:
    _VIDEO_PATH = "0"

# =============================================================================
#  PROFILE HELPERS
# =============================================================================
def _profile_path(name: str) -> Path:
    return BASE_DIR / "data" / "patients" / name.lower().replace(" ","_") / "profile.json"

def _profile_exists(name: str) -> bool:
    return _profile_path(name).exists()

def _load_existing(name: str) -> dict:
    with open(_profile_path(name)) as f:
        return json.load(f)

def _save_profile(profile: dict):
    name  = profile["personal"]["name"]
    pdir  = _profile_path(name).parent
    pdir.mkdir(parents=True, exist_ok=True)
    with open(pdir/"profile.json","w") as f:
        json.dump(profile, f, indent=4, ensure_ascii=False)
    print(f"[Setup] Profile saved → {pdir/'profile.json'}")

def _zones_path(username: str) -> Path:
    return BASE_DIR/"data"/"patients"/username/"safe_zones.json"

def _load_zones(username: str) -> list:
    zp = _zones_path(username)
    if not zp.exists(): return []
    try:
        with open(zp) as f: data=json.load(f)
        return [{"type":d["type"],"box":tuple(d["box"])} for d in data]
    except: return []

def _save_zones(username: str, zones: list):
    zp = _zones_path(username)
    zp.parent.mkdir(parents=True, exist_ok=True)
    with open(zp,"w") as f:
        json.dump([{"type":z["type"],"box":list(z["box"])} for z in zones], f, indent=2)
    print(f"[Zones] Saved {len(zones)} zone(s) → {zp}")


# =============================================================================
#  1. PATIENT SETUP SCREEN  (8-step GUI wizard)
# =============================================================================
class PatientSetupScreen:
    """GUI wizard to collect patient profile. Calls on_complete(name, profile)."""

    def __init__(self, container: ctk.CTkFrame, on_complete):
        self.container   = container
        self.on_complete = on_complete
        self._name = self._username = ""
        self._profile = {}
        self._em = []; self._gn = []; self._meds = []; self._zones_txt = []
        self._page = None
        self._show_name_page()

    # ── helpers ──────────────────────────────────────────────────────────────
    def _clear(self):
        if self._page and self._page.winfo_exists(): self._page.destroy()
        self._page = ctk.CTkFrame(self.container, fg_color=C["bg"])
        self._page.pack(fill="both", expand=True)

    def _hdr(self, title, sub=""):
        ctk.CTkLabel(self._page, text="LEO", font=("Courier New",30,"bold"),
                     text_color=C["accent"]).pack(pady=(30,2))
        ctk.CTkLabel(self._page, text="AI Home Assistant for the Elderly  |  FYP 2024-25",
                     font=("Courier New",10), text_color=C["dim"]).pack()
        ctk.CTkFrame(self._page, height=2, fg_color=C["border"]).pack(fill="x",padx=80,pady=12)
        ctk.CTkLabel(self._page, text=title, font=("Courier New",19,"bold"),
                     text_color=C["text"]).pack(pady=(0,3))
        if sub:
            ctk.CTkLabel(self._page, text=sub, font=("Courier New",11),
                         text_color=C["dim"]).pack(pady=(0,14))

    def _prog(self, step, total=6):
        f=ctk.CTkFrame(self._page,fg_color="transparent"); f.pack(pady=(0,8))
        for i in range(1,total+1):
            ctk.CTkFrame(f,width=38,height=5,corner_radius=3,
                         fg_color=C["accent"] if i<=step else C["border"]
                         ).pack(side="left",padx=2)
        ctk.CTkLabel(f,text=f"  Step {step}/{total}",
                     font=("Courier New",9),text_color=C["dim"]).pack(side="left")

    def _ent(self, p, ph, w=360, h=44):
        e=ctk.CTkEntry(p,placeholder_text=ph,font=("Courier New",13),
                       fg_color=C["input"],border_color=C["accent"],
                       text_color=C["text"],placeholder_text_color=C["dim"],
                       height=h,width=w); e.pack(pady=5); return e

    def _mini(self, p, ph, w, h=36):
        e=ctk.CTkEntry(p,placeholder_text=ph,font=("Courier New",11),
                       fg_color=C["input"],border_color=C["border"],
                       text_color=C["text"],placeholder_text_color=C["dim"],
                       height=h,width=w); e.pack(side="left",padx=3); return e

    @staticmethod
    def _ok_phone(p): return bool(re.match(r"^03\d{9}$",p.strip()))
    @staticmethod
    def _ok_time(t):
        try: datetime.strptime(t.strip(),"%H:%M"); return True
        except: return False

    def _nav(self, parent, nxt_cmd, back_cmd=None, nxt_label="Next  ▶"):
        f=ctk.CTkFrame(parent,fg_color="transparent"); f.pack(pady=12)
        ctk.CTkButton(f,text=nxt_label,command=nxt_cmd,fg_color=C["accent"],
                      hover_color="#00a0cc",text_color="#000",
                      font=("Courier New",12,"bold"),height=40,width=170,
                      corner_radius=8).pack(side="left",padx=6)
        if back_cmd:
            ctk.CTkButton(f,text="← Back",command=back_cmd,
                          fg_color="transparent",hover_color=C["input"],
                          text_color=C["dim"],font=("Courier New",11),
                          height=40,width=110).pack(side="left",padx=6)

    # ── Page 1 — Name ─────────────────────────────────────────────────────────
    def _show_name_page(self):
        self._clear(); self._hdr("Welcome","Enter patient name to begin")
        f=ctk.CTkFrame(self._page,fg_color="transparent"); f.pack(expand=True)
        ctk.CTkLabel(f,text="Patient Name",font=("Courier New",12),
                     text_color=C["dim"]).pack()
        ne=ctk.CTkEntry(f,placeholder_text="e.g. Ali Ahmed",
                        font=("Courier New",15),fg_color=C["input"],
                        border_color=C["accent"],text_color=C["text"],
                        height=50,width=400); ne.pack(pady=10); ne.focus()
        err=ctk.CTkLabel(f,text="",font=("Courier New",11),
                         text_color=C["red"]); err.pack()
        def go(e=None):
            n=ne.get().strip()
            if not n: err.configure(text="Name cannot be empty."); return
            self._name=n; self._username=n.lower().replace(" ","_")
            if _profile_exists(n): self._show_existing_page()
            else: self._init_new(); self._show_personal_page()
        ne.bind("<Return>",go)
        ctk.CTkButton(f,text="Continue  ▶",command=go,fg_color=C["accent"],
                      hover_color="#00a0cc",text_color="#000",
                      font=("Courier New",14,"bold"),height=50,width=400,
                      corner_radius=8).pack(pady=8)

    # ── Page 2a — Existing ────────────────────────────────────────────────────
    def _show_existing_page(self):
        self._clear()
        ex=_load_existing(self._name); p=ex.get("personal",{})
        self._hdr(f"Welcome back, {p.get('name',self._name)}!",
                  "A saved profile was found for this patient.")
        f=ctk.CTkFrame(self._page,fg_color=C["card"],corner_radius=12)
        f.pack(padx=100,pady=8,fill="x")
        for lbl,val in [
            ("Name",p.get("name","?")),("Age",str(p.get("age","?"))),
            ("Emergency contacts",str(len(ex.get("emergency_contacts",[])))),
            ("Medications",str(len(ex.get("medications",[])))),
            ("Routine",f"Wake {ex.get('routine',{}).get('wake_up','?')} / Sleep {ex.get('routine',{}).get('sleep','?')}"),
        ]:
            r=ctk.CTkFrame(f,fg_color="transparent"); r.pack(fill="x",padx=20,pady=3)
            ctk.CTkLabel(r,text=f"{lbl}:",font=("Courier New",11),
                         text_color=C["dim"],width=160,anchor="w").pack(side="left")
            ctk.CTkLabel(r,text=val,font=("Courier New",12,"bold"),
                         text_color=C["text"],anchor="w").pack(side="left")
        bf=ctk.CTkFrame(self._page,fg_color="transparent"); bf.pack(pady=18)
        ctk.CTkButton(bf,text="▶  Load Existing Profile",
                      command=lambda:(self.__setattr__('_profile',ex),
                                      self.on_complete(self._name,self._profile)),
                      fg_color=C["green"],hover_color="#00b050",text_color="#000",
                      font=("Courier New",13,"bold"),height=44,width=300,
                      corner_radius=8).pack(pady=5)
        ctk.CTkButton(bf,text="✎  Create New Profile",
                      command=lambda:(self._init_new(),self._show_personal_page()),
                      fg_color=C["card"],hover_color=C["input"],text_color=C["text"],
                      border_width=1,border_color=C["accent"],
                      font=("Courier New",13),height=44,width=300,
                      corner_radius=8).pack(pady=5)
        ctk.CTkButton(bf,text="← Back",command=self._show_name_page,
                      fg_color="transparent",hover_color=C["input"],
                      text_color=C["dim"],font=("Courier New",11),
                      height=32,width=120).pack(pady=4)

    def _init_new(self):
        self._em=[]; self._gn=[]; self._meds=[]; self._zones_txt=[]
        self._profile={"personal":{"name":self._name},
                       "emergency_contacts":self._em,"contacts":self._gn,
                       "medications":self._meds,"routine":{},"active_zones":self._zones_txt}

    # ── Page 3 — Personal ─────────────────────────────────────────────────────
    def _show_personal_page(self):
        self._clear(); self._hdr(f"New Profile: {self._name}","Personal Information")
        self._prog(1)
        f=ctk.CTkFrame(self._page,fg_color="transparent"); f.pack(expand=True)
        ctk.CTkLabel(f,text="Age (years)",font=("Courier New",12),
                     text_color=C["dim"]).pack()
        ae=self._ent(f,"e.g. 65"); ae.focus()
        err=ctk.CTkLabel(f,text="",font=("Courier New",11),
                         text_color=C["red"]); err.pack()
        def nxt(e=None):
            a=ae.get().strip()
            if not a.isdigit() or not 1<=int(a)<=120:
                err.configure(text="Enter valid age (1-120)."); return
            self._profile["personal"]["age"]=int(a)
            self._show_contacts_page(self._em,"Emergency Contacts",
                "Who to notify when a fall is detected",True,2,
                self._show_personal_page,self._show_gn_contacts)
        ae.bind("<Return>",nxt)
        self._nav(f,nxt,self._show_name_page)

    # ── Pages 4/5 — Contacts ──────────────────────────────────────────────────
    def _show_gn_contacts(self):
        self._show_contacts_page(self._gn,"General Contacts",
            "Friends and family for regular calls",False,3,
            lambda:self._show_contacts_page(self._em,"Emergency Contacts",
                "Who to notify when a fall is detected",True,2,
                self._show_personal_page,self._show_gn_contacts),
            self._show_meds_page)

    def _show_contacts_page(self,store,title,sub,required,step,on_back,on_next):
        self._clear(); self._hdr(title,sub); self._prog(step)
        sc=ctk.CTkScrollableFrame(self._page,fg_color=C["panel"],
                                   corner_radius=10,height=130)
        sc.pack(fill="x",padx=80,pady=4)
        def refresh():
            for w in sc.winfo_children(): w.destroy()
            if store:
                for i,c in enumerate(store):
                    r=ctk.CTkFrame(sc,fg_color=C["card"],corner_radius=5)
                    r.pack(fill="x",pady=2,padx=4)
                    ctk.CTkLabel(r,
                        text=f"  {c['name']}  •  {c['relation']}  •  {c['phone']}",
                        font=("Courier New",10),text_color=C["text"]
                        ).pack(side="left",pady=5,padx=6)
                    j=i
                    ctk.CTkButton(r,text="✕",width=26,height=22,
                        fg_color=C["red"],hover_color="#cc0000",text_color="#fff",
                        font=("Courier New",9),
                        command=lambda k=j:(store.pop(k),refresh())
                        ).pack(side="right",padx=5)
            else:
                ctk.CTkLabel(sc,text="No contacts added yet.",
                             font=("Courier New",10),text_color=C["dim"]
                             ).pack(pady=12)
        refresh()
        af=ctk.CTkFrame(self._page,fg_color="transparent"); af.pack(pady=4)
        r1=ctk.CTkFrame(af,fg_color="transparent"); r1.pack()
        ne=self._mini(r1,"Contact name",185)
        re_=self._mini(r1,"Relation (son/wife)",175)
        r2=ctk.CTkFrame(af,fg_color="transparent"); r2.pack(pady=3)
        pe=self._mini(r2,"Phone  03XXXXXXXXX",255)
        err=ctk.CTkLabel(af,text="",font=("Courier New",10),
                         text_color=C["red"]); err.pack()
        def add():
            n_,r__,p_=ne.get().strip(),re_.get().strip(),pe.get().strip()
            if not n_: err.configure(text="Name required."); return
            if not r__: err.configure(text="Relation required."); return
            if not self._ok_phone(p_):
                err.configure(text="Phone: 03XXXXXXXXX (11 digits)"); return
            store.append({"name":n_,"relation":r__,"phone":p_})
            ne.delete(0,"end"); re_.delete(0,"end"); pe.delete(0,"end")
            err.configure(text=""); refresh()
        ctk.CTkButton(r2,text="+ Add",command=add,
                      fg_color=C["purple"],hover_color="#6020c0",text_color="#fff",
                      font=("Courier New",11,"bold"),height=36,width=95,
                      corner_radius=7).pack(side="left",padx=4)
        def nxt():
            if required and not store:
                err.configure(text="Add at least one contact."); return
            on_next()
        self._nav(self._page,nxt,on_back)

    # ── Page 6 — Medications ──────────────────────────────────────────────────
    def _show_meds_page(self):
        self._clear(); self._hdr("Medication Schedule","Add all daily medicines")
        self._prog(4)
        sc=ctk.CTkScrollableFrame(self._page,fg_color=C["panel"],
                                   corner_radius=10,height=120)
        sc.pack(fill="x",padx=80,pady=4)
        def refresh():
            for w in sc.winfo_children(): w.destroy()
            if self._meds:
                for i,m in enumerate(self._meds):
                    r=ctk.CTkFrame(sc,fg_color=C["card"],corner_radius=5)
                    r.pack(fill="x",pady=2,padx=4)
                    ctk.CTkLabel(r,
                        text=f"  {m['medicine']}  •  {m['dose']}  •  {m['time']}  •  {m['before_after_food']} food",
                        font=("Courier New",10),text_color=C["text"]
                        ).pack(side="left",pady=5,padx=6)
                    j=i
                    ctk.CTkButton(r,text="✕",width=24,height=20,
                        fg_color=C["red"],hover_color="#cc0000",text_color="#fff",
                        font=("Courier New",9),
                        command=lambda k=j:(self._meds.pop(k),refresh())
                        ).pack(side="right",padx=5)
            else:
                ctk.CTkLabel(sc,text="No medications yet.",
                             font=("Courier New",10),text_color=C["dim"]
                             ).pack(pady=10)
        refresh()
        mf=ctk.CTkFrame(self._page,fg_color="transparent"); mf.pack(pady=4)
        r1=ctk.CTkFrame(mf,fg_color="transparent"); r1.pack()
        me=self._mini(r1,"Medicine name",185)
        de=self._mini(r1,"Dose (1 tablet)",165)
        te=self._mini(r1,"Time HH:MM",105)
        r2=ctk.CTkFrame(mf,fg_color="transparent"); r2.pack(pady=3)
        doc_e=self._mini(r2,"Doctor name",175)
        fv=ctk.StringVar(value="after")
        ctk.CTkOptionMenu(r2,variable=fv,values=["before","after"],
                          font=("Courier New",11),fg_color=C["input"],
                          button_color=C["border"],width=120,height=34
                          ).pack(side="left",padx=3)
        ctk.CTkLabel(r2,text="food",font=("Courier New",11),
                     text_color=C["dim"]).pack(side="left",padx=2)
        qe=self._mini(r2,"Qty",80)
        err=ctk.CTkLabel(mf,text="",font=("Courier New",10),
                         text_color=C["red"]); err.pack()
        def add():
            mn,d,t=me.get().strip(),de.get().strip(),te.get().strip()
            if not mn: err.configure(text="Medicine name required."); return
            if not d:  err.configure(text="Dose required."); return
            if not self._ok_time(t):
                err.configure(text="Time: HH:MM e.g. 08:30"); return
            self._meds.append({"medicine":mn,"dose":d,"time":t,
                               "before_after_food":fv.get(),
                               "doctor":doc_e.get().strip() or "Unknown",
                               "quantity_left":int(qe.get()) if qe.get().isdigit() else 0,
                               "purpose":"","frequency_per_day":1,
                               "total_quantity":0,"start_date":""})
            for e_ in [me,de,te,doc_e,qe]: e_.delete(0,"end")
            err.configure(text=""); refresh()
        ctk.CTkButton(mf,text="+ Add Medicine",command=add,
                      fg_color=C["purple"],hover_color="#6020c0",text_color="#fff",
                      font=("Courier New",11,"bold"),height=36,width=190,
                      corner_radius=7).pack(pady=4)
        self._nav(self._page,self._show_routine_page,self._show_gn_contacts)

    # ── Page 7 — Routine ──────────────────────────────────────────────────────
    def _show_routine_page(self):
        self._clear(); self._hdr("Daily Routine","Patient sleep schedule")
        self._prog(5)
        f=ctk.CTkFrame(self._page,fg_color="transparent"); f.pack(expand=True)
        ctk.CTkLabel(f,text="Wake up time (HH:MM)",font=("Courier New",12),
                     text_color=C["dim"]).pack()
        wu=self._ent(f,"e.g. 06:00"); wu.focus()
        ctk.CTkLabel(f,text="Sleep time (HH:MM)",font=("Courier New",12),
                     text_color=C["dim"]).pack(pady=(10,0))
        sl=self._ent(f,"e.g. 22:00")
        err=ctk.CTkLabel(f,text="",font=("Courier New",11),
                         text_color=C["red"]); err.pack()
        def nxt():
            w_,s_=wu.get().strip(),sl.get().strip()
            if not self._ok_time(w_): err.configure(text="Wake: HH:MM"); return
            if not self._ok_time(s_): err.configure(text="Sleep: HH:MM"); return
            self._profile["routine"]={"wake_up":w_,"sleep":s_}
            self._show_zones_text_page()
        self._nav(f,nxt,self._show_meds_page)

    # ── Page 8 — Zones + finish ───────────────────────────────────────────────
    def _show_zones_text_page(self):
        self._clear(); self._hdr("Active Rooms","Which rooms does the patient use?")
        self._prog(6)
        sc=ctk.CTkScrollableFrame(self._page,fg_color=C["panel"],
                                   corner_radius=10,height=110)
        sc.pack(fill="x",padx=120,pady=4)
        def refresh():
            for w in sc.winfo_children(): w.destroy()
            if self._zones_txt:
                for i,z in enumerate(self._zones_txt):
                    r=ctk.CTkFrame(sc,fg_color=C["card"],corner_radius=5)
                    r.pack(fill="x",pady=2,padx=4)
                    ctk.CTkLabel(r,text=f"  {z}",font=("Courier New",11),
                                 text_color=C["text"]).pack(side="left",pady=5,padx=8)
                    j=i
                    ctk.CTkButton(r,text="✕",width=24,height=20,
                        fg_color=C["red"],hover_color="#cc0000",text_color="#fff",
                        font=("Courier New",9),
                        command=lambda k=j:(self._zones_txt.pop(k),refresh())
                        ).pack(side="right",padx=5)
            else:
                ctk.CTkLabel(sc,text="No rooms added.",font=("Courier New",10),
                             text_color=C["dim"]).pack(pady=10)
        refresh()
        zf=ctk.CTkFrame(self._page,fg_color="transparent"); zf.pack(pady=6)
        ze=ctk.CTkEntry(zf,placeholder_text="e.g. bedroom, kitchen",
                        font=("Courier New",12),fg_color=C["input"],
                        border_color=C["border"],text_color=C["text"],
                        height=38,width=290); ze.pack(side="left",padx=5)
        def add(e=None):
            z=ze.get().strip()
            if z: self._zones_txt.append(z); ze.delete(0,"end"); refresh()
        ze.bind("<Return>",add)
        ctk.CTkButton(zf,text="+ Add",command=add,
                      fg_color=C["purple"],hover_color="#6020c0",text_color="#fff",
                      font=("Courier New",11,"bold"),height=38,width=95,
                      corner_radius=7).pack(side="left",padx=5)
        bf=ctk.CTkFrame(self._page,fg_color="transparent"); bf.pack(pady=14)
        def finish():
            self._profile["emergency_contacts"]=self._em
            self._profile["contacts"]=self._gn
            self._profile["medications"]=self._meds
            self._profile["active_zones"]=self._zones_txt
            _save_profile(self._profile)
            self.on_complete(self._name,self._profile)
        ctk.CTkButton(bf,text="Next: Zone Setup  ▶",command=finish,
                      fg_color=C["green"],hover_color="#00b050",text_color="#000",
                      font=("Courier New",13,"bold"),height=46,width=240,
                      corner_radius=8).pack(side="left",padx=6)
        ctk.CTkButton(bf,text="← Back",command=self._show_routine_page,
                      fg_color="transparent",hover_color=C["input"],
                      text_color=C["dim"],font=("Courier New",11),
                      height=46,width=110).pack(side="left",padx=6)


# =============================================================================
#  2. SAFE ZONE SETUP WINDOW
#  Draw bed/sofa zones on the camera frame before monitoring starts.
#  Saves to data/patients/{name}/safe_zones.json
# =============================================================================
class ZoneSetupWindow(ctk.CTkToplevel):
    """
    Standalone zone drawing window.
    Loads a frame from the video file, lets the user draw zones, saves JSON.
    Can be opened from the main window too (for re-setup).
    """

    CANVAS_W = FRAME_W   # 640
    CANVAS_H = FRAME_H   # 480

    def __init__(self, parent, username: str, on_done, video_path=None):
        super().__init__(parent)
        self.title("LEO — Safe Zone Setup")
        self.geometry(f"{self.CANVAS_W + 220}x{self.CANVAS_H + 80}")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self.grab_set()   # modal

        self.username  = username
        self.on_done   = on_done
        self.video_path = video_path or _VIDEO_PATH
        self.zones     = list(_load_zones(username))  # start with existing zones
        self._zone_type = "bed"
        self._drawing   = False
        self._p0 = self._p1 = None
        self._bg_photo  = None   # keep alive
        self._bg_img    = None   # PIL image for re-drawing

        # FIX: init _type_var before _build so mouse callbacks never crash
        self._type_var  = ctk.StringVar(value="bed")

        self._build()
        self._load_bg_frame()
        self._redraw()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

    # ── build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        # Canvas on left
        self.canvas = tk.Canvas(self, width=self.CANVAS_W, height=self.CANVAS_H,
                                bg="#050508", cursor="crosshair",
                                highlightthickness=1, highlightbackground=C["border"])
        self.canvas.place(x=0, y=0)
        self.canvas.bind("<ButtonPress-1>",   self._mouse_down)
        self.canvas.bind("<B1-Motion>",       self._mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)

        # Control panel on right — width/height must be in constructor for CTk
        rp = ctk.CTkFrame(self, fg_color=C["panel"],
                           width=210, height=self.CANVAS_H+80,
                           corner_radius=0)
        rp.place(x=self.CANVAS_W, y=0)
        rp.pack_propagate(False)

        ctk.CTkLabel(rp, text="ZONE SETUP", font=("Courier New",13,"bold"),
                     text_color=C["accent"]).pack(pady=(16,2))
        ctk.CTkLabel(rp, text="Draw zones on the camera frame.\nBed / Sofa = safe areas\n(falls ignored inside zones)",
                     font=("Courier New",9), text_color=C["dim"],
                     justify="center", wraplength=190).pack(pady=(2,12))

        ctk.CTkFrame(rp, height=1, fg_color=C["border"]).pack(fill="x",padx=12,pady=4)
        ctk.CTkLabel(rp, text="ZONE TYPE", font=("Courier New",9),
                     text_color=C["dim"]).pack(pady=(6,2))

        for zt in ["bed","sofa"]:
            ctk.CTkRadioButton(rp, text=f"  {zt.upper()} zone",
                               variable=self._type_var, value=zt,
                               font=("Courier New",11),
                               text_color=ZONE_COLORS_HEX[zt],
                               command=lambda: self.__setattr__('_zone_type', self._type_var.get())
                               ).pack(anchor="w", padx=20, pady=3)

        ctk.CTkFrame(rp, height=1, fg_color=C["border"]).pack(fill="x",padx=12,pady=8)
        ctk.CTkLabel(rp, text="ZONES DRAWN", font=("Courier New",9),
                     text_color=C["dim"]).pack()
        self.zone_count_lbl = ctk.CTkLabel(rp, text="0",
                                            font=("Courier New",28,"bold"),
                                            text_color=C["accent"])
        self.zone_count_lbl.pack(pady=4)

        ctk.CTkButton(rp, text="↩ Delete Last", height=32,
                      fg_color="#3a1a1a", hover_color="#5a2020",
                      text_color=C["red"], font=("Courier New",10),
                      command=self._delete_last).pack(fill="x",padx=14,pady=3)
        ctk.CTkButton(rp, text="✕ Clear All", height=32,
                      fg_color="#3a1a1a", hover_color="#5a2020",
                      text_color=C["red"], font=("Courier New",10),
                      command=self._clear_all).pack(fill="x",padx=14,pady=3)

        ctk.CTkFrame(rp, height=1, fg_color=C["border"]).pack(fill="x",padx=12,pady=8)
        ctk.CTkButton(rp, text="✓  Save & Continue", height=44,
                      fg_color=C["green"], hover_color="#00b050",
                      text_color="#000", font=("Courier New",11,"bold"),
                      command=self._save_and_done).pack(fill="x",padx=14,pady=3)
        ctk.CTkButton(rp, text="Skip (no zones)", height=34,
                      fg_color=C["card"], hover_color=C["input"],
                      text_color=C["dim"], font=("Courier New",10),
                      command=self._on_skip).pack(fill="x",padx=14,pady=3)

        ctk.CTkLabel(rp, text="KEYBOARD", font=("Courier New",8),
                     text_color=C["dim"]).pack(pady=(10,2))
        ctk.CTkLabel(rp, text="D = delete last\nC = clear all\nTAB = switch type\nEnter = save",
                     font=("Courier New",8), text_color=C["dim"],
                     justify="center").pack()

        # Status bar at bottom — width/height in constructor (CTk restriction)
        self.status_lbl = ctk.CTkLabel(self, text="Draw zones by clicking and dragging on the video frame",
                                        font=("Courier New",9), text_color=C["dim"],
                                        width=self.CANVAS_W, height=30, anchor="w")
        self.status_lbl.place(x=0, y=self.CANVAS_H)

        # Keyboard bindings
        self.bind("<d>", lambda e: self._delete_last())
        self.bind("<D>", lambda e: self._delete_last())
        self.bind("<c>", lambda e: self._clear_all())
        self.bind("<C>", lambda e: self._clear_all())
        self.bind("<Tab>", self._toggle_type)
        self.bind("<Return>", lambda e: self._save_and_done())

    # ── load background frame from video ─────────────────────────────────────
    def _load_bg_frame(self):
        try:
            import cv2
            src = (int(self.video_path)
                   if str(self.video_path).isdigit()
                   else self.video_path)
            cap = cv2.VideoCapture(src)
            if cap.isOpened():
                # Skip first 30 frames — video often starts black
                ret, frame = False, None
                for _ in range(30):
                    ret, frame = cap.read()
                    if not ret: break
                cap.release()
                if ret:
                    frame = cv2.resize(frame, (self.CANVAS_W, self.CANVAS_H))
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self._bg_img = Image.fromarray(frame_rgb)
                    self.status_lbl.configure(
                        text=f"Loaded frame from video. Draw zones — {len(self.zones)} existing zone(s) loaded.")
                    return
        except Exception as e:
            print(f"[ZoneSetup] Could not load video frame: {e}")
        # Fallback: dark placeholder
        self._bg_img = Image.new("RGB", (self.CANVAS_W, self.CANVAS_H), (8,8,20))
        self.status_lbl.configure(text="Video not found — drawing zones on placeholder. Zones will still work.")

    # ── drawing ───────────────────────────────────────────────────────────────
    def _mouse_down(self, e):
        self._zone_type = self._type_var.get()
        self._drawing = True; self._p0=(e.x,e.y); self._p1=(e.x,e.y)

    def _mouse_drag(self, e):
        if self._drawing:
            self._p1=(max(0,min(e.x,self.CANVAS_W-1)),
                      max(0,min(e.y,self.CANVAS_H-1)))
            self._redraw()

    def _mouse_up(self, e):
        if self._drawing and self._p0 and self._p1:
            self._drawing = False
            x1=min(self._p0[0],self._p1[0]); y1=min(self._p0[1],self._p1[1])
            x2=max(self._p0[0],self._p1[0]); y2=max(self._p0[1],self._p1[1])
            if (x2-x1)>15 and (y2-y1)>15:
                self.zones.append({"type":self._zone_type,"box":(x1,y1,x2,y2)})
                self.zone_count_lbl.configure(text=str(len(self.zones)))
            self._p0=self._p1=None; self._redraw()

    def _redraw(self):
        """Redraw canvas: bg image + committed zones + live drag rect."""
        if not self._bg_img: return
        img = self._bg_img.copy()
        import numpy as np
        arr = np.array(img)

        # Draw committed zones
        for z in self.zones:
            x1,y1,x2,y2 = [int(v) for v in z["box"]]
            # clamp to image bounds
            x1=max(0,x1); y1=max(0,y1)
            x2=min(arr.shape[1],x2); y2=min(arr.shape[0],y2)
            if x2<=x1 or y2<=y1: continue
            col_bgr = ZONE_COLORS_BGR[z["type"]]
            col_rgb = (col_bgr[2], col_bgr[1], col_bgr[0])  # BGR→RGB
            col_arr = np.array(col_rgb, dtype=np.float32)

            # Semi-transparent fill — proper numpy broadcasting (was broken before)
            roi = arr[y1:y2, x1:x2].astype(np.float32)
            arr[y1:y2, x1:x2] = (roi * 0.65 + col_arr * 0.35).astype(np.uint8)

            # 2-pixel border
            arr[y1:y2, x1:x1+2]  = col_rgb
            arr[y1:y2, x2-2:x2]  = col_rgb
            arr[y1:y1+2, x1:x2]  = col_rgb
            arr[y2-2:y2, x1:x2]  = col_rgb

            # Zone type label using PIL
            from PIL import ImageDraw
            pil_tmp = Image.fromarray(arr.astype("uint8"))
            draw = ImageDraw.Draw(pil_tmp)
            lbl = z["type"].upper()
            tw = len(lbl) * 7 + 10
            draw.rectangle([x1, y1, x1+tw, y1+18], fill=col_rgb)
            draw.text((x1+4, y1+2), lbl, fill=(255,255,255))
            arr = np.array(pil_tmp)

        # Live drag rectangle while mouse is held
        if self._drawing and self._p0 and self._p1:
            x1=min(self._p0[0],self._p1[0]); y1=min(self._p0[1],self._p1[1])
            x2=max(self._p0[0],self._p1[0]); y2=max(self._p0[1],self._p1[1])
            x1=max(0,x1); y1=max(0,y1)
            x2=min(arr.shape[1],x2); y2=min(arr.shape[0],y2)
            if x2>x1 and y2>y1:
                col_bgr = ZONE_COLORS_BGR[self._zone_type]
                col_rgb = (col_bgr[2], col_bgr[1], col_bgr[0])
                arr[y1:y2, x1:x1+2]  = col_rgb
                arr[y1:y2, x2-2:x2]  = col_rgb
                arr[y1:y1+2, x1:x2]  = col_rgb
                arr[y2-2:y2, x1:x2]  = col_rgb

        final = Image.fromarray(arr.astype("uint8"))
        self._bg_photo = ImageTk.PhotoImage(final)
        self.canvas.delete("all")
        self.canvas.create_image(0,0,image=self._bg_photo,anchor="nw")

    def _delete_last(self):
        if self.zones: self.zones.pop()
        self.zone_count_lbl.configure(text=str(len(self.zones)))
        self._redraw()

    def _clear_all(self):
        self.zones.clear()
        self.zone_count_lbl.configure(text="0")
        self._redraw()

    def _toggle_type(self, e=None):
        t = "sofa" if self._type_var.get()=="bed" else "bed"
        self._type_var.set(t); self._zone_type=t

    def _save_and_done(self):
        _save_zones(self.username, self.zones)
        self.grab_release(); self.destroy()
        self.on_done(self.zones)

    def _on_skip(self):
        self.grab_release(); self.destroy()
        self.on_done(self.zones)  # pass existing (or empty) zones unchanged


# =============================================================================
#  3. HISTORY WINDOW
#  Shows: Falls history, Activity log, Conversations
# =============================================================================
class HistoryWindow(ctk.CTkToplevel):
    """Caregiver history view — falls, activity log, conversations."""

    def __init__(self, parent, username: str):
        super().__init__(parent)
        self.title(f"LEO — History: {username.replace('_',' ').title()}")
        self.geometry("900x640"); self.configure(fg_color=C["bg"])
        self.username = username
        self._build()
        self._load_data()

    def _build(self):
        ctk.CTkLabel(self, text=f"📋  LEO History  —  {self.username.replace('_',' ').title()}",
                     font=("Courier New",14,"bold"), text_color=C["accent"]
                     ).pack(pady=(14,6), padx=20, anchor="w")

        tabs = ctk.CTkTabview(self, fg_color=C["panel"],
                              segmented_button_fg_color=C["card"],
                              segmented_button_selected_color=C["accent"],
                              segmented_button_selected_hover_color="#00a0cc",
                              text_color=C["text"])
        tabs.pack(fill="both", expand=True, padx=16, pady=(0,16))

        tabs.add("🚨  Falls")
        tabs.add("📋  Activity Log")
        tabs.add("💬  Conversations")
        tabs.add("📊  Summary")

        self._fall_frame   = tabs.tab("🚨  Falls")
        self._log_frame    = tabs.tab("📋  Activity Log")
        self._chat_frame   = tabs.tab("💬  Conversations")
        self._summ_frame   = tabs.tab("📊  Summary")

        for f in [self._fall_frame, self._log_frame, self._chat_frame, self._summ_frame]:
            f.configure(fg_color=C["panel"])

    def _card(self, parent, title, value, sub="", col=None):
        col = col or C["accent"]
        f=ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10)
        f.pack(side="left", expand=True, fill="both", padx=6, pady=6)
        ctk.CTkLabel(f,text=title,font=("Courier New",9),
                     text_color=C["dim"]).pack(pady=(10,2))
        ctk.CTkLabel(f,text=value,font=("Courier New",22,"bold"),
                     text_color=col).pack()
        if sub:
            ctk.CTkLabel(f,text=sub,font=("Courier New",9),
                         text_color=C["dim"]).pack(pady=(0,8))
        return f

    def _load_data(self):
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        # Try MongoDB first, fall back to local JSON files
        falls=[]; logs=[]; chats=[]; summary={}
        try:
            from mongo_storage import leo_db
            if leo_db.connected:
                falls   = leo_db.get_falls(self.username, limit=50)
                logs    = leo_db.get_logs(self.username, limit=100)
                summary = leo_db.get_patient_summary(self.username)
                chats   = leo_db.get_memory(self.username)
        except: pass

        # Local JSON fallback
        if not falls:
            local_log = (BASE_DIR/"data"/"patients"/self.username/"logs"/
                         f"{datetime.now().strftime('%Y-%m-%d')}.json")
            if local_log.exists():
                try:
                    with open(local_log) as f: raw=json.load(f)
                    logs  = [l for l in raw if l.get("category")!="fall"]
                    falls_local = [l for l in raw if "fall" in l.get("content","").lower()]
                    if not falls: falls=falls_local
                except: pass

        if not chats:
            mem_dir = BASE_DIR/"data"/"patients"/self.username/"memory"
            if mem_dir.exists():
                files = sorted(mem_dir.glob("chat_*.json"), reverse=True)
                for fp in files[:3]:
                    try:
                        with open(fp) as f: chats+=json.load(f)
                    except: pass

        # Schedule GUI updates on main thread
        self.after(0, lambda: self._populate(falls, logs, chats, summary))

    def _populate(self, falls, logs, chats, summary):
        # ── Falls tab ─────────────────────────────────────────────────────────
        sf = ctk.CTkScrollableFrame(self._fall_frame, fg_color=C["bg"], corner_radius=8)
        sf.pack(fill="both", expand=True, padx=8, pady=8)
        if falls:
            for ev in falls:
                card = ctk.CTkFrame(sf, fg_color=C["card"], corner_radius=8)
                card.pack(fill="x", pady=4, padx=6)
                ts = ev.get("time") or ev.get("timestamp")
                ts_str = ts.strftime("%Y-%m-%d  %H:%M:%S") if hasattr(ts,"strftime") else str(ts)
                ctk.CTkLabel(card, text=f"🚨 FALL — {ts_str}",
                             font=("Courier New",10,"bold"),
                             text_color=C["red"]).pack(anchor="w",padx=12,pady=(8,2))
                row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x",padx=12,pady=(0,8))
                for lbl,val in [("Score", str(ev.get("score",0))+"/4"),
                                 ("Posture", ev.get("posture","?")),
                                 ("Reason", str(ev.get("reason",""))[:60])]:
                    ctk.CTkLabel(row,text=f"{lbl}: {val}",font=("Courier New",9),
                                 text_color=C["dim"]).pack(side="left",padx=8)
                if ev.get("clip_path"):
                    ctk.CTkLabel(card,text=f"📹 Clip: {Path(ev['clip_path']).name}",
                                 font=("Courier New",9),text_color=C["purple"]
                                 ).pack(anchor="w",padx=12,pady=(0,6))
        else:
            ctk.CTkLabel(sf, text="No fall events recorded.",
                         font=("Courier New",12), text_color=C["dim"]).pack(pady=40)

        # ── Activity Log tab ──────────────────────────────────────────────────
        sl = ctk.CTkScrollableFrame(self._log_frame, fg_color=C["bg"], corner_radius=8)
        sl.pack(fill="both", expand=True, padx=8, pady=8)
        CAT_COL={"chat":C["accent"],"fall":C["red"],"medication":C["yellow"],
                 "emotion":C["purple"],"emergency":C["red"]}
        if logs:
            for ev in logs[:80]:
                r=ctk.CTkFrame(sl, fg_color=C["card"], corner_radius=6)
                r.pack(fill="x", pady=2, padx=6)
                cat=ev.get("category","info"); col=CAT_COL.get(cat,C["dim"])
                t=ev.get("time") or ev.get("timestamp","?")
                ts_str = t.strftime("%H:%M:%S") if hasattr(t,"strftime") else str(t)[:8]
                ctk.CTkLabel(r,text=f"[{ts_str}]",font=("Courier New",9),
                             text_color=C["dim"],width=70).pack(side="left",padx=8,pady=5)
                ctk.CTkLabel(r,text=cat.upper(),font=("Courier New",8,"bold"),
                             text_color=col,width=70).pack(side="left",padx=4)
                ctk.CTkLabel(r,text=ev.get("content","")[:90],font=("Courier New",9),
                             text_color=C["text"],anchor="w").pack(side="left",padx=4)
        else:
            ctk.CTkLabel(sl, text="No activity logs found for today.",
                         font=("Courier New",12), text_color=C["dim"]).pack(pady=40)

        # ── Conversations tab ─────────────────────────────────────────────────
        sc = ctk.CTkScrollableFrame(self._chat_frame, fg_color=C["bg"], corner_radius=8)
        sc.pack(fill="both", expand=True, padx=8, pady=8)
        if chats:
            for msg in chats[-60:]:
                role = msg.get("role","user"); content=msg.get("content","")
                is_leo=(role=="assistant")
                r=ctk.CTkFrame(sc, fg_color=C["card"], corner_radius=6)
                r.pack(fill="x", pady=2, padx=6)
                ctk.CTkLabel(r, text="LEO" if is_leo else "PATIENT",
                             font=("Courier New",8,"bold"),
                             text_color=C["purple"] if is_leo else C["accent"],
                             width=55).pack(side="left",padx=8,pady=5)
                ctk.CTkLabel(r, text=content[:110],
                             font=("Courier New",9), text_color=C["text"],
                             anchor="w").pack(side="left",padx=4,pady=5)
        else:
            ctk.CTkLabel(sc, text="No conversation history found.",
                         font=("Courier New",12), text_color=C["dim"]).pack(pady=40)

        # ── Summary tab ───────────────────────────────────────────────────────
        sm=self._summ_frame
        row1=ctk.CTkFrame(sm,fg_color="transparent"); row1.pack(fill="x",pady=8,padx=8)
        ft=summary.get("falls_today",len([f for f in falls
               if hasattr(f.get("timestamp"),"date") and
               f["timestamp"].date()==datetime.now().date()]))
        self._card(row1,"Falls Today",str(ft),"detected today",C["red"] if ft else C["green"])
        self._card(row1,"Total Falls",str(summary.get("total_falls",len(falls))),"all time",C["orange"])
        self._card(row1,"Chat Messages",str(len(chats)),"in history",C["accent"])
        row2=ctk.CTkFrame(sm,fg_color="transparent"); row2.pack(fill="x",padx=8)
        self._card(row2,"Last Fall",summary.get("last_fall","None"),"","")
        self._card(row2,"Last Activity",summary.get("last_activity","—"),"","")
        lf=summary.get("last_fall_clip","")
        self._card(row2,"Last Clip",Path(lf).name if lf else "None","","")
        if summary:
            ctk.CTkLabel(sm,text="Data sourced from MongoDB",font=("Courier New",9),
                         text_color=C["dim"]).pack(pady=8)


# =============================================================================
#  4. LEO BRAIN — AI thread
# =============================================================================
class LeoBrain(threading.Thread):
    def __init__(self, out_q, profile=None):
        super().__init__(daemon=True)
        self.out_q=out_q; self.in_q=queue.Queue()
        self.leo=self.tts=self.bg=None
        self.ready=False; self.patient_name=None; self._profile=profile

    def set_patient(self, name):
        self.patient_name=name.lower().replace(" ","_")

    def run(self):
        try:
            while not self.patient_name: time.sleep(0.05)
            self.out_q.put(("sys","Loading patient profile..."))
            from patait_info_collector import _profile_exists, _load_existing
            from mongo_storage import leo_db
            from audio import Leo, VoiceOutput, BackgroundListener

            profile=(self._profile or
                     (_load_existing(self.patient_name) if _profile_exists(self.patient_name)
                      else {"personal":{"name":self.patient_name},
                            "emergency_contacts":[],"contacts":[],
                            "medications":[],"routine":{},"active_zones":[]}))

            if leo_db.connected:
                leo_db.save_patient(profile); self.out_q.put(("db","Connected"))
            else:
                self.out_q.put(("db","Offline"))

            self.out_q.put(("sys","Loading Qwen LLM (chat)..."))
            self.leo=Leo(self.patient_name, preloaded_profile=profile)
            self.out_q.put(("sys","Loading Kokoro TTS..."))
            self.tts=VoiceOutput()
            self.out_q.put(("sys","Starting mic (Whisper)..."))

            def on_voice(text):
                self.out_q.put(("voice",text)); self._respond(text)

            self.bg=BackgroundListener(on_voice, whisper_model="base")
            self.bg.start(); self.ready=True

            name=profile.get("personal",{}).get("name",self.patient_name)
            self.out_q.put(("ready",{"name":name,"meds":profile.get("medications",[]),
                                     "profile":profile}))
            hour=datetime.now().hour
            g=("Good morning" if hour<12 else "Good afternoon" if hour<18 else "Good evening")
            msg=f"{g}, {name}! I am Leo. You can type or speak — I am always listening."
            self.out_q.put(("leo",msg)); self._speak(msg)

            while True:
                try:    self._respond(self.in_q.get(timeout=0.5))
                except queue.Empty: pass
        except Exception as e:
            self.out_q.put(("error",str(e)))

    def _respond(self, text):
        if not self.leo or not text: return
        try:
            resp=self.leo.respond(text)
            self.out_q.put(("leo",resp)); self._speak(resp)
        except Exception as e:
            self.out_q.put(("error",str(e)))

    def _speak(self, t):
        if self.tts and self.tts.available:
            threading.Thread(target=self.tts.speak,args=(t,),daemon=True).start()

    def send(self, t): self.in_q.put(t)
    def stop(self):
        if self.bg: self.bg.stop()


# =============================================================================
#  5. FALL MONITOR — polls MongoDB for new events
# =============================================================================
class FallMonitor(threading.Thread):
    def __init__(self, patient, out_q):
        super().__init__(daemon=True)
        self.patient=patient; self.out_q=out_q
        self.running=True; self.last_seen=None

    def run(self):
        try:
            from mongo_storage import leo_db
            if not leo_db.connected: return
            last=leo_db._col("fall_events").find_one(
                {"patient":self.patient},sort=[("timestamp",-1)])
            self.last_seen=last["timestamp"] if last else datetime.min
            while self.running:
                time.sleep(4)
                new=leo_db._col("fall_events").find_one(
                    {"patient":self.patient,"timestamp":{"$gt":self.last_seen}},
                    sort=[("timestamp",-1)])
                if new:
                    self.last_seen=new["timestamp"]; self.out_q.put(("fall",new))
        except: pass

    def stop(self): self.running=False


# =============================================================================
#  6. MAIN APP
# =============================================================================
class LeoApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("LEO — AI Home Assistant"); self.geometry("1400x860")
        self.minsize(1100,700); self.configure(fg_color=C["bg"])
        self.out_q=queue.Queue()
        self.brain=self.mon=self.fall_m=None
        self.fall_c=0; self.patient=""; self._profile={}
        self._last_frame_data=None; self._display_loop_active=False
        self._canvas_img_id=None; self._last_cw=self._last_ch=0
        self._photo_keep=[]

        # Show patient setup wizard first
        self._setup_frame=ctk.CTkFrame(self,fg_color=C["bg"])
        self._setup_frame.pack(fill="both",expand=True)
        PatientSetupScreen(self._setup_frame, on_complete=self._on_patient_done)

    # ── Step 1 complete: patient profile collected ────────────────────────────
    def _on_patient_done(self, patient_name: str, profile: dict):
        self.patient=patient_name.lower().replace(" ","_")
        self._profile=profile
        self._setup_frame.destroy()

        # Step 2: Zone Setup Window (always offer it)
        self.withdraw()   # hide main window during zone setup
        ZoneSetupWindow(self, self.patient, on_done=self._on_zones_done)

    # ── Step 2 complete: zones set (or skipped) ───────────────────────────────
    def _on_zones_done(self, zones: list):
        self.deiconify()   # show main window
        self._build()      # build monitoring UI

        # Start LEO brain
        self.brain=LeoBrain(self.out_q, profile=self._profile)
        self.brain.set_patient(self._profile["personal"]["name"])
        self.brain.start()

        # Start fall watcher
        self.fall_m=FallMonitor(self.patient, self.out_q)
        self.fall_m.start()

        self.after(200, self._poll)
        self._sys(f"Starting LEO for {self._profile['personal'].get('name','').title()}...")

    # ── Build main monitoring UI ──────────────────────────────────────────────
    def _build(self):
        # Top bar
        top=ctk.CTkFrame(self,fg_color=C["panel"],height=54,corner_radius=0)
        top.pack(fill="x"); top.pack_propagate(False)
        ctk.CTkLabel(top,text="LEO",font=("Courier New",22,"bold"),
                     text_color=C["accent"]).pack(side="left",padx=18)
        pname=self._profile.get("personal",{}).get("name","")
        ctk.CTkLabel(top,text=f"AI Elder Care  |  {pname}  |  FYP 2024-25",
                     font=("Courier New",10),text_color=C["dim"]).pack(side="left")
        self.status_lbl=ctk.CTkLabel(top,text="● Loading...",
                                      font=("Courier New",10),text_color=C["orange"])
        self.status_lbl.pack(side="right",padx=20)
        ctk.CTkButton(top,text="Dashboard",width=100,height=30,
                      fg_color=C["card"],hover_color=C["input"],
                      border_width=1,border_color=C["accent"],
                      text_color=C["accent"],font=("Courier New",10),
                      command=lambda:webbrowser.open("http://localhost:5000")
                      ).pack(side="right",padx=6,pady=12)
        ctk.CTkButton(top,text="📋 History",width=90,height=30,
                      fg_color=C["card"],hover_color=C["input"],
                      border_width=1,border_color=C["purple"],
                      text_color=C["purple"],font=("Courier New",10),
                      command=self._open_history
                      ).pack(side="right",padx=6,pady=12)

        # 3-col layout
        main=ctk.CTkFrame(self,fg_color=C["bg"])
        main.pack(fill="both",expand=True,padx=10,pady=(0,10))
        main.columnconfigure(0,weight=0,minsize=215)
        main.columnconfigure(1,weight=1)
        main.columnconfigure(2,weight=0,minsize=255)
        main.rowconfigure(0,weight=1)
        self._build_left(main); self._build_center(main); self._build_right(main)

    # ── LEFT PANEL ────────────────────────────────────────────────────────────
    def _build_left(self, p):
        left=ctk.CTkFrame(p,fg_color=C["panel"],corner_radius=12,width=215)
        left.grid(row=0,column=0,sticky="nsew",padx=(0,6))
        left.pack_propagate(False)

        # Patient card
        pc=ctk.CTkFrame(left,fg_color=C["card"],corner_radius=10)
        pc.pack(fill="x",padx=10,pady=(12,6))
        ctk.CTkLabel(pc,text="PATIENT",font=("Courier New",8),
                     text_color=C["dim"]).pack(pady=(8,2))
        pi=self._profile.get("personal",{})
        ctk.CTkLabel(pc,text=pi.get("name",self.patient).title(),
                     font=("Courier New",15,"bold"),text_color=C["accent"]).pack()
        ctk.CTkLabel(pc,text=f"Age {pi.get('age','?')}  •  {len(self._profile.get('medications',[]))} med(s)",
                     font=("Courier New",9),text_color=C["dim"]).pack(pady=(0,8))

        # System status
        ctk.CTkLabel(left,text="SYSTEM STATUS",font=("Courier New",8),
                     text_color=C["dim"]).pack(padx=10,pady=(10,2),anchor="w")
        self.s_leo=self._sc(left,"LEO Brain","Loading")
        self.s_cam=self._sc(left,"Camera","Off")
        self.s_mic=self._sc(left,"Mic","—")
        self.s_db =self._sc(left,"MongoDB","—")
        self.s_sms=self._sc(left,"WhatsApp","Ready")

        # Falls counter
        ctk.CTkLabel(left,text="FALLS TODAY",font=("Courier New",8),
                     text_color=C["dim"]).pack(padx=10,pady=(12,2),anchor="w")
        fc=ctk.CTkFrame(left,fg_color=C["card"],corner_radius=10)
        fc.pack(fill="x",padx=10)
        self.fall_lbl=ctk.CTkLabel(fc,text="0",
                                    font=("Courier New",38,"bold"),text_color=C["green"])
        self.fall_lbl.pack(pady=8)

        # Camera + Zone buttons
        ctk.CTkLabel(left,text="MONITORING",font=("Courier New",8),
                     text_color=C["dim"]).pack(padx=10,pady=(12,3),anchor="w")
        self.cam_btn=ctk.CTkButton(left,text="▶  Start Camera",height=36,
                                    fg_color=C["green"],hover_color="#00b050",
                                    text_color="#000",font=("Courier New",11,"bold"),
                                    command=self._toggle_cam)
        self.cam_btn.pack(fill="x",padx=10,pady=(0,4))
        ctk.CTkButton(left,text="🗺  Edit Safe Zones",height=30,
                      fg_color=C["card"],hover_color=C["input"],
                      border_width=1,border_color=C["accent"],
                      text_color=C["accent"],font=("Courier New",10),
                      command=self._open_zone_setup
                      ).pack(fill="x",padx=10,pady=(0,10))

        # Current state
        ctk.CTkLabel(left,text="CURRENT STATE",font=("Courier New",8),
                     text_color=C["dim"]).pack(padx=10,pady=(4,2),anchor="w")
        self.state_lbl=ctk.CTkLabel(left,text="—",
                                     font=("Courier New",13,"bold"),
                                     text_color=C["accent"],wraplength=195)
        self.state_lbl.pack(padx=10)

        # Zones loaded indicator
        zones=_load_zones(self.patient)
        ctk.CTkLabel(left,text="SAFE ZONES",font=("Courier New",8),
                     text_color=C["dim"]).pack(padx=10,pady=(10,2),anchor="w")
        self.zone_lbl=ctk.CTkLabel(left,
                                    text=f"{len(zones)} zone(s) configured" if zones else "None — click Edit",
                                    font=("Courier New",9),
                                    text_color=C["green"] if zones else C["orange"])
        self.zone_lbl.pack(padx=10,anchor="w")

    def _sc(self, parent, label, val):
        f=ctk.CTkFrame(parent,fg_color=C["card"],corner_radius=7)
        f.pack(fill="x",padx=10,pady=2)
        ctk.CTkLabel(f,text=label,font=("Courier New",9),
                     text_color=C["dim"]).pack(side="left",padx=8,pady=4)
        lbl=ctk.CTkLabel(f,text=val,font=("Courier New",9,"bold"),text_color=C["orange"])
        lbl.pack(side="right",padx=8)
        return lbl

    # ── CENTER — Video + Chat + Input ─────────────────────────────────────────
    def _build_center(self, p):
        center=ctk.CTkFrame(p,fg_color=C["panel"],corner_radius=12)
        center.grid(row=0,column=1,sticky="nsew",padx=6)
        center.rowconfigure(0,weight=3); center.rowconfigure(1,weight=1)
        center.rowconfigure(2,weight=0); center.columnconfigure(0,weight=1)

        vf=ctk.CTkFrame(center,fg_color=C["bg"],corner_radius=10)
        vf.grid(row=0,column=0,sticky="nsew",padx=10,pady=(10,4))
        self.vid_canvas=tk.Canvas(vf,bg="#050508",highlightthickness=0)
        self.vid_canvas.pack(fill="both",expand=True,padx=2,pady=2)
        self.vid_placeholder=ctk.CTkLabel(
            vf,text="📷\n\nCamera is OFF\n\nClick  ▶ Start Camera  to begin monitoring",
            font=("Courier New",13),text_color=C["dim"],justify="center")
        self.vid_placeholder.place(relx=0.5,rely=0.5,anchor="center")
        self.mic_lbl=ctk.CTkLabel(center,text="",font=("Courier New",10),
                                   text_color=C["green"])
        self.mic_lbl.grid(row=0,column=0,sticky="se",padx=18,pady=12)

        ch=ctk.CTkFrame(center,fg_color=C["card"],height=30,corner_radius=0)
        ch.grid(row=1,column=0,sticky="new"); ch.pack_propagate(False)
        ctk.CTkLabel(ch,text="💬  Conversation with LEO",
                     font=("Courier New",10,"bold"),text_color=C["accent"]
                     ).pack(side="left",padx=12,pady=6)

        self.chat=tk.Text(center,bg=C["card"],fg=C["text"],
                          font=("Courier New",11),wrap="word",
                          relief="flat",borderwidth=0,
                          padx=12,pady=6,state="disabled",height=7)
        self.chat.grid(row=1,column=0,sticky="nsew",pady=(30,0))
        self.chat.tag_configure("you",  foreground=C["accent"], font=("Courier New",9,"bold"))
        self.chat.tag_configure("leo",  foreground="#a78bfa",   font=("Courier New",9,"bold"))
        self.chat.tag_configure("msg",  foreground=C["text"],   font=("Courier New",11))
        self.chat.tag_configure("sys",  foreground=C["orange"], font=("Courier New",9,"italic"))
        self.chat.tag_configure("time", foreground=C["dim"],    font=("Courier New",8))

        inp=ctk.CTkFrame(center,fg_color=C["card"],height=56,corner_radius=0)
        inp.grid(row=2,column=0,sticky="ew"); inp.pack_propagate(False)
        self.entry=ctk.CTkEntry(
            inp,placeholder_text="Type here, or just speak — both work simultaneously...",
            font=("Courier New",12),fg_color=C["input"],border_color=C["purple"],
            text_color=C["text"],placeholder_text_color=C["dim"],height=38)
        self.entry.pack(side="left",fill="x",expand=True,padx=(12,8),pady=9)
        self.entry.bind("<Return>",self._send)
        ctk.CTkButton(inp,text="Send ▶",width=88,height=38,
                      fg_color=C["purple"],hover_color="#6020c0",
                      font=("Courier New",12,"bold"),
                      command=self._send).pack(side="right",padx=(0,10))

    # ── RIGHT PANEL ───────────────────────────────────────────────────────────
    def _build_right(self, p):
        right=ctk.CTkFrame(p,fg_color=C["panel"],corner_radius=12,width=255)
        right.grid(row=0,column=2,sticky="nsew",padx=(6,0))
        right.pack_propagate(False)

        ctk.CTkLabel(right,text="🚨  ALERTS",font=("Courier New",10,"bold"),
                     text_color=C["red"]).pack(padx=12,pady=(12,4),anchor="w")
        self.alerts_box=ctk.CTkScrollableFrame(right,fg_color=C["bg"],
                                                corner_radius=8,height=210)
        self.alerts_box.pack(fill="x",padx=10,pady=(0,6))
        self.no_alert=ctk.CTkLabel(self.alerts_box,text="No alerts",
                                    font=("Courier New",10),text_color=C["dim"])
        self.no_alert.pack(pady=16)

        ctk.CTkLabel(right,text="💊  MEDICATIONS",font=("Courier New",10,"bold"),
                     text_color=C["accent"]).pack(padx=12,pady=(6,4),anchor="w")
        self.meds_box=ctk.CTkScrollableFrame(right,fg_color=C["bg"],
                                              corner_radius=8,height=140)
        self.meds_box.pack(fill="x",padx=10,pady=(0,6))
        self.no_med=ctk.CTkLabel(self.meds_box,text="No medications",
                                  font=("Courier New",10),text_color=C["dim"])
        self.no_med.pack(pady=16)
        if self._profile.get("medications"):
            self._load_meds(self._profile["medications"])

        ctk.CTkLabel(right,text="⚡  QUICK ACTIONS",font=("Courier New",10,"bold"),
                     text_color=C["accent"]).pack(padx=12,pady=(6,4),anchor="w")
        for txt,q in [
            ("💊 My medicines",       "what are my medicines"),
            ("📞 Emergency contacts", "show emergency contacts"),
            ("😴 I feel tired",       "I feel tired"),
            ("⏰ My routine",          "what is my daily routine"),
            ("💊 Medicine reminder",  "remind me about my medicine"),
            ("🆘 Help me",            "help me"),
        ]:
            ctk.CTkButton(right,text=txt,height=28,anchor="w",
                          fg_color=C["card"],hover_color=C["input"],
                          text_color=C["text"],font=("Courier New",10),
                          command=lambda x=q:self._quick(x)
                          ).pack(fill="x",padx=10,pady=2)

    # ── ACTIONS ───────────────────────────────────────────────────────────────
    def _send(self, e=None):
        if not self.brain: return
        text=self.entry.get().strip()
        if not text or not self.brain.ready: return
        self.entry.delete(0,"end")
        n=self.patient.replace("_"," ").title() or "You"
        self._msg(n,text,"you","msg"); self.brain.send(text)

    def _quick(self, text):
        if not self.brain or not self.brain.ready: return
        n=self.patient.replace("_"," ").title() or "You"
        self._msg(n,text,"you","msg"); self.brain.send(text)

    def _open_history(self):
        HistoryWindow(self, self.patient)

    def _open_zone_setup(self):
        was_running=(self.mon and self.mon.running)
        if was_running: self.mon.stop(); self.mon=None
        def on_done(zones):
            self.zone_lbl.configure(
                text=f"{len(zones)} zone(s) configured" if zones else "None — click Edit",
                text_color=C["green"] if zones else C["orange"])
            if was_running:
                self._sys("Zones updated. Restart camera to apply.")
        ZoneSetupWindow(self, self.patient, on_done=on_done)

    def _toggle_cam(self):
        if self.mon and self.mon.running:
            self.mon.stop(); self.mon=None
            self._canvas_img_id=None; self._last_frame_data=None
            self.vid_canvas.delete("all")
            self.cam_btn.configure(text="▶  Start Camera",
                                    fg_color=C["green"],hover_color="#00b050",text_color="#000")
            self.s_cam.configure(text="Off",text_color=C["orange"])
            self.vid_placeholder.place(relx=0.5,rely=0.5,anchor="center")
            self.state_lbl.configure(text="—"); self._sys("Camera stopped.")
        else:
            self.vid_placeholder.place_forget()
            try:
                from monitoring_stream import MonitoringStream
                self.mon=MonitoringStream(
                    patient_name=self.patient,
                    frame_cb=lambda *a:None,
                    fall_cb=self._on_fall_detected,
                )
                self.mon.start()
                if not self._display_loop_active:
                    self._display_loop_active=True; self._display_loop()
                self.cam_btn.configure(text="■  Stop Camera",
                                        fg_color=C["red"],hover_color="#cc0000",text_color="#fff")
                self.s_cam.configure(text="Active",text_color=C["green"])
                self._sys("Camera started — GPU YOLO + parallel inference running...")
            except Exception as ex:
                self._sys(f"Camera error: {ex}")
                import traceback; traceback.print_exc()

    def _display_loop(self):
        if not self.mon or not self.mon.running:
            self._display_loop_active=False; return
        with self.mon._lock:
            data=self.mon.latest_frame
        if data is not None and data is not self._last_frame_data:
            self._last_frame_data=data
            frame_rgb,state,score=data
            try:
                cw=self.vid_canvas.winfo_width(); ch=self.vid_canvas.winfo_height()
                if cw<10: cw=VIDEO_W
                if ch<10: ch=VIDEO_H
                h,w=frame_rgb.shape[:2]; scale=min(cw/w,ch/h)
                nw=max(1,int(w*scale)); nh=max(1,int(h*scale))
                img=Image.fromarray(frame_rgb).resize((nw,nh),Image.NEAREST)
                photo=ImageTk.PhotoImage(img)
                self._photo_keep=[photo]+self._photo_keep[:1]
                if self._canvas_img_id is None:
                    self._canvas_img_id=self.vid_canvas.create_image(
                        cw//2,ch//2,image=photo,anchor="center")
                else:
                    self.vid_canvas.itemconfig(self._canvas_img_id,image=photo)
                    if cw!=self._last_cw or ch!=self._last_ch:
                        self.vid_canvas.coords(self._canvas_img_id,cw//2,ch//2)
                        self._last_cw=cw; self._last_ch=ch
                self.state_lbl.configure(text=state)
                # ── Push to FastAPI → Flutter sees live video ──────
                fall_now = ("FALL" in str(state).upper())
                safe_now = ("SAFE" in str(state).upper() and "FALL" not in str(state).upper())
                _push_frame_to_api(
                    frame_rgb     = frame_rgb,
                    state         = state,
                    score         = score,
                    fall_detected = fall_now,
                    on_safe_zone  = safe_now,
                    posture       = str(state).lower().split()[0] if state else "unknown",
                )
                # ────────────────────────────────────────────────────
            except Exception: pass
        self.after(33,self._display_loop)

    def _on_fall_detected(self, score, reason, posture, clip_path=""):
        self.out_q.put(("fall_direct",{
            "score":score,"reason":reason,"posture":posture,
            "time":datetime.now().strftime("%H:%M:%S"),"clip_path":clip_path}))

    # ── CHAT HELPERS ──────────────────────────────────────────────────────────
    def _msg(self, sender, text, ntag, mtag, mic=False):
        self.chat.configure(state="normal")
        ts=datetime.now().strftime("%H:%M")
        self.chat.insert("end",f"\n{sender}  ",ntag)
        self.chat.insert("end",f"{ts}\n","time")
        self.chat.insert("end",f"{'🎤 ' if mic else ''}{text}\n",mtag)
        self.chat.configure(state="disabled"); self.chat.see("end")

    def _sys(self, text):
        self.chat.configure(state="normal")
        self.chat.insert("end",f"\n  ◆ {text}\n","sys")
        self.chat.configure(state="disabled"); self.chat.see("end")

    def _alert_card(self, text):
        try: self.no_alert.destroy()
        except: pass
        card=ctk.CTkFrame(self.alerts_box,fg_color=C["card"],corner_radius=8)
        card.pack(fill="x",pady=3)
        ctk.CTkLabel(card,text=f"🚨 {datetime.now().strftime('%H:%M')}",
                     font=("Courier New",9),text_color=C["red"]
                     ).pack(anchor="w",padx=8,pady=(6,0))
        ctk.CTkLabel(card,text=text,font=("Courier New",10),
                     text_color=C["text"],wraplength=215,justify="left"
                     ).pack(anchor="w",padx=8,pady=(0,6))

    def _load_meds(self, meds):
        try: self.no_med.destroy()
        except: pass
        for m in meds[:8]:
            f=ctk.CTkFrame(self.meds_box,fg_color=C["card"],corner_radius=6)
            f.pack(fill="x",pady=2)
            ctk.CTkLabel(f,text=m.get("medicine","?"),
                         font=("Courier New",10,"bold"),text_color=C["text"]
                         ).pack(anchor="w",padx=8,pady=(4,0))
            ctk.CTkLabel(f,text=f"{m.get('time','?')}  •  {m.get('dose','?')}  •  {m.get('before_after_food','')} food",
                         font=("Courier New",9),text_color=C["dim"]
                         ).pack(anchor="w",padx=8,pady=(0,4))

    def _do_fall_whatsapp(self, data):
        try:
            self.out_q.put(("whatsapp_status","Sending..."))
            from twilio_alerts import twilio_alerts
            from patait_info_collector import _load_existing
            profile=_load_existing(self.patient)
            contacts=profile.get("emergency_contacts",[])
            if not contacts:
                self.out_q.put(("whatsapp_status","No contacts"))
                self.out_q.put(("sys","WhatsApp: No emergency contacts configured!")); return
            ok=twilio_alerts.send_fall_alert(
                patient=self.patient, contacts=contacts,
                clip_path=data.get("clip_path",""),
                score=data.get("score",0), posture=data.get("posture","lying"))
            if ok:
                self.out_q.put(("whatsapp_status","Sent ✓"))
                self.out_q.put(("sys","WhatsApp alert sent to emergency contacts!"))
            else:
                self.out_q.put(("whatsapp_status","Failed"))
                self.out_q.put(("sys","WhatsApp: Send failed — check Twilio logs"))
        except Exception as e:
            self.out_q.put(("whatsapp_status","Error"))
            self.out_q.put(("sys",f"WhatsApp error: {e}"))

    # ── QUEUE POLL ────────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                ev,data=self.out_q.get_nowait()
                if ev=="leo":
                    self._msg("LEO",data,"leo","msg")
                elif ev=="voice":
                    n=self.patient.replace("_"," ").title() or "You"
                    self._msg(n,data,"you","msg",mic=True)
                    self.mic_lbl.configure(text=f"🎤 Heard: {data[:40]}")
                    self.after(3000,lambda:self.mic_lbl.configure(text=""))
                elif ev=="sys":
                    self._sys(data)
                    self.status_lbl.configure(text=f"● {data[:42]}",text_color=C["orange"])
                elif ev=="ready":
                    self.status_lbl.configure(text="● Running",text_color=C["green"])
                    self.s_leo.configure(text="Active",text_color=C["green"])
                    self.s_mic.configure(text="Listening",text_color=C["green"])
                    if data["meds"]: self._load_meds(data["meds"])
                    self._sys(f"LEO ready for {data['name']}")
                    global _push_patient
                    _push_patient = self.patient
                elif ev=="db":
                    self.s_db.configure(text=data,
                        text_color=C["green"] if data=="Connected" else C["orange"])
                elif ev in ("fall","fall_direct"):
                    self.fall_c+=1
                    self.fall_lbl.configure(text=str(self.fall_c),text_color=C["red"])
                    score=data.get("score",0)
                    ts_=data.get("time","") or str(data.get("timestamp",""))
                    self._alert_card(f"FALL DETECTED\nTime: {ts_}\nScore: {score}/4")
                    self._sys(f"🚨 FALL detected! Score:{score} — sending WhatsApp alert...")
                    self.title("🚨 FALL DETECTED — LEO")
                    self.after(8000,lambda:self.title("LEO — AI Home Assistant"))
                    threading.Thread(target=self._do_fall_whatsapp,
                                     args=(data,),daemon=True).start()
                elif ev=="whatsapp_status":
                    col=(C["green"] if "Sent" in str(data) else
                         C["orange"] if data=="Sending..." else C["red"])
                    self.s_sms.configure(text=data,text_color=col)
                elif ev=="error":
                    self._sys(f"Error: {data}")
                    self.status_lbl.configure(text="● Error",text_color=C["red"])
        except queue.Empty: pass
        self.after(200,self._poll)

    def on_close(self):
        if self.mon:    self.mon.stop()
        if self.fall_m: self.fall_m.stop()
        if self.brain:  self.brain.stop()
        self.destroy()


if __name__ == "__main__":
    app=LeoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()