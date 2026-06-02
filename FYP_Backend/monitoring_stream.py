# # """
# # LEO — Monitoring Stream (Single-Thread, v19 Logic)
# # ===================================================

# # Uses the EXACT same single-threaded detection loop as the working
# # standalone v19 script.  YOLO runs synchronously every frame so the
# # displayed frame and its detection boxes are always in perfect sync.

# # The only difference from v19:
# #   • No cv2.imshow — annotated frame is written to self.latest_frame
# #     so the GUI's _display_loop can pick it up.
# #   • Zone setup screen is skipped — zones are loaded from the saved JSON.
# #   • fall_cb is called when a fall is detected (instead of direct SMS).
# # """

# # import cv2
# # import numpy as np
# # import json
# # import math
# # import threading
# # from collections import deque
# # from pathlib import Path

# # BASE_DIR = Path(__file__).parent

# # VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
# # FALL_MODEL_PATH = (
# #     "D:\\Python\\FYP\\Trained Datasets\\"
# #     "GPT_fyp_train_dataset_fall_v2.1\\runs_backup\\detect\\"
# #     "runs\\train\\fall_stage1\\weights\\best.pt"
# # )
# # POSTURE_MODEL_PATH = (
# #     "D:\\Python\\FYP\\Trained Datasets\\"
# #     "GPT_fyp_train_dataset_lying1_posture_v2.1\\runs_backup\\detect\\"
# #     "runs\\train\\siting_stage1\\weights\\best.pt"
# # )

# # FRAME_W, FRAME_H = 640, 480

# # # ── Speed tuning ──────────────────────────────────────────────────────────────
# # # MX550 GPU (2GB VRAM) — both models fit at FP16.
# # # On GPU, YOLO_EVERY_N=1 is fine (GPU inference ~10-20ms per frame).
# # # On CPU fallback, increase to 3 or 4.
# # YOLO_EVERY_N = 1   # every frame on GPU — fast enough

# # # 416 is the sweet spot for MX550: accurate + fits in 2GB VRAM at FP16.
# # # Use 320 if you see CUDA out-of-memory errors.
# # YOLO_IMGSZ = 416

# # # Force GPU — set to True to error loudly if CUDA is unavailable
# # # (helps confirm you are actually using the GPU)
# # FORCE_CUDA = False

# # # ── Detection parameters (identical to v19) ───────────────────────────────────
# # LYING_CONFIRM_FRAMES           = 8
# # STANDING_CONFIRM_FRAMES        = 3
# # POSTURE_PERSIST_FRAMES         = 8
# # LYING_ASPECT_RATIO_MAX         = 1.2
# # SITTING_CONFIRM_FOR_PREPOSTURE = 3

# # DROP_FAST_PX       = 7
# # DROP_ANY_PX        = 3
# # AREA_CHANGE_HIGH   = 0.12
# # AREA_CHANGE_ANY    = 0.05
# # SUDDEN_DROP_THRESH = 7.0
# # SUDDEN_AREA_THRESH = 0.20
# # FLOW_SPIKE_THRESH  = 1.4
# # FLOW_ANY_THRESH    = 0.7
# # FLOW_STILL_THRESH  = 0.9
# # ASPECT_DROP_THRESH = 0.18
# # FALL_MODEL_CONSEC  = 2
# # FALL_SCORE_NEEDED  = 4
# # ANALYSIS_START     = 4
# # ANALYSIS_END       = 40
# # PRE_LYING_WINDOW   = 25
# # POST_LYING_WINDOW  = 10
# # UPRIGHT_LOOKBACK   = 55
# # MIN_UPRIGHT_FRAMES = 15
# # FALL_LATCH_FRAMES     = 65
# # RECOVERY_LATCH_FRAMES = 25

# # # ── Colors (identical to v19) ─────────────────────────────────────────────────
# # ZONE_COLORS = {
# #     "bed":  (0, 200, 255),
# #     "sofa": (0, 140, 255),
# # }

# # STATE_META = {
# #     "FALL":              ((0,   0,   220), "!"),
# #     "LYING (POST-FALL)": ((0,   60,  190), "!"),
# #     "LYING (SAFE)":      ((140, 80,  0),   "~"),
# #     "LYING (ON BED)":    ((0,   110, 150), "~"),
# #     "LYING (ON SOFA)":   ((0,   90,  165), "~"),
# #     "STANDING":          ((0,   160, 30),  "^"),
# #     "SITTING":           ((0,   130, 120), "s"),
# #     "RECOVERY":          ((130, 0,   160), "r"),
# #     "UNKNOWN":           ((75,  75,  75),  "?"),
# #     "STARTING":          ((60,  60,  60),  "."),
# # }


# # # ── Helpers (identical to v19) ────────────────────────────────────────────────

# # def get_aspect_ratio(box):
# #     x1, y1, x2, y2 = box
# #     return max(y2 - y1, 1) / max(x2 - x1, 1)

# # def get_bbox_area(box):
# #     x1, y1, x2, y2 = box
# #     return max(x2 - x1, 0) * max(y2 - y1, 0)

# # def compute_flow_energy(gray_curr, gray_prev, box):
# #     if gray_prev is None or box is None: return 0.0
# #     x1 = max(int(box[0]), 0); y1 = max(int(box[1]), 0)
# #     x2 = min(int(box[2]), gray_curr.shape[1])
# #     y2 = min(int(box[3]), gray_curr.shape[0])
# #     if x2 <= x1 + 4 or y2 <= y1 + 4: return 0.0
# #     flow = cv2.calcOpticalFlowFarneback(
# #         gray_prev[y1:y2, x1:x2], gray_curr[y1:y2, x1:x2], None,
# #         pyr_scale=0.5, levels=2, winsize=12, iterations=2,
# #         poly_n=5, poly_sigma=1.1, flags=0)
# #     return float(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))

# # def select_main_subject(detections):
# #     if not detections: return "none", None
# #     best_label, best_box, best_area, best_conf = "none", None, -1, -1
# #     for (label, box, conf) in detections:
# #         area = get_bbox_area(box); ar = get_aspect_ratio(box)
# #         if label == "lying" and ar > LYING_ASPECT_RATIO_MAX: continue
# #         if area > best_area or (area == best_area and conf > best_conf):
# #             best_area, best_conf = area, conf
# #             best_label, best_box = label, box
# #     return best_label, best_box

# # def person_zone(person_box, zones):
# #     if person_box is None or not zones: return None
# #     cx = (person_box[0] + person_box[2]) / 2
# #     cy = (person_box[1] + person_box[3]) / 2
# #     for z in zones:
# #         x1, y1, x2, y2 = z["box"]
# #         if x1 <= cx <= x2 and y1 <= cy <= y2:
# #             return z
# #     return None

# # def person_in_safe_zone(person_box, zones):
# #     return person_zone(person_box, zones) is not None


# # # ── Draw helpers (identical to v19) ──────────────────────────────────────────

# # def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
# #     (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
# #     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
# #     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
# #     cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
# #                 (255,255,255), 1, cv2.LINE_AA)

# # def draw_zone_on_frame(img, z, is_active=False):
# #     x1, y1, x2, y2 = z["box"]
# #     col   = ZONE_COLORS[z["type"]]
# #     alpha = 0.22 if is_active else 0.12
# #     ov    = img.copy()
# #     cv2.rectangle(ov, (x1,y1), (x2,y2), col, -1)
# #     cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)
# #     cv2.rectangle(img, (x1,y1), (x2,y2), col, 2 if is_active else 1, cv2.LINE_AA)
# #     label = z["type"].upper() + (" *" if is_active else "")
# #     (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
# #     pad = 4
# #     bov = img.copy()
# #     cv2.rectangle(bov, (x1, y1), (x1+tw+pad*2, y1+th+pad*2), col, -1)
# #     cv2.addWeighted(bov, 0.80, img, 0.20, 0, img)
# #     cv2.putText(img, label, (x1+pad, y1+th+pad),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,255), 1, cv2.LINE_AA)

# # def draw_all_zones(img, zones, active_zone=None):
# #     for z in zones:
# #         draw_zone_on_frame(img, z, is_active=(z is active_zone))

# # def draw_banner(frame, state):
# #     col = STATE_META.get(state, ((100,100,100),"?"))[0]
# #     W = frame.shape[1]
# #     ov = frame.copy()
# #     cv2.rectangle(ov, (0,0), (W,58), col, -1)
# #     cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
# #     cv2.rectangle(frame, (0,0), (5,58), col, -1)
# #     cv2.line(frame, (0,58), (W,58), col, 1)
# #     cv2.putText(frame, f"STATE:  {state}",
# #                 (16,40), cv2.FONT_HERSHEY_SIMPLEX,
# #                 0.95, (255,255,255), 2, cv2.LINE_AA)

# # def draw_signals(frame, flow_val, area_chg, drop_vel, score, fall_score_needed):
# #     H, W = frame.shape[:2]
# #     px, py = 6, H-90; pw = 192
# #     ov = frame.copy()
# #     cv2.rectangle(ov, (px-2,py-2), (px+pw,py+80), (12,12,18), -1)
# #     cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
# #     cv2.rectangle(frame, (px-2,py-2), (px+pw,py+80), (50,50,70), 1)
# #     sigs = [("FLOW", flow_val, 5.0,  (0,200,255)),
# #             ("AREA", area_chg, 0.3,  (0,180,120)),
# #             ("DROP", drop_vel, 20.0, (60,100,255)),
# #             ("SCOR", score,    fall_score_needed*1.5, (0,60,255))]
# #     bx = px+44; bmax = pw-52
# #     for i, (lbl, val, mx, col) in enumerate(sigs):
# #         y  = py + 6 + i*18
# #         bw = int(min(val / max(mx, 0.001), 1.0) * bmax)
# #         cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (28,28,40), -1)
# #         if bw > 0: cv2.rectangle(frame, (bx,y+2), (bx+bw,y+12), col, -1)
# #         cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (55,55,75), 1)
# #         cv2.putText(frame, lbl, (px,y+12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140,140,165), 1)
# #         cv2.putText(frame, f"{val:.1f}", (bx+bmax+3,y+12),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.27, (170,170,195), 1)

# # def draw_rec_indicator(frame, is_saving_clip, tick):
# #     H, W = frame.shape[:2]
# #     pulse = int(180 + 75 * math.sin(tick * 0.2))
# #     cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
# #     cv2.putText(frame, "REC", (W-45, 25),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
# #     if is_saving_clip:
# #         badge = "  SAVING FALL CLIP  "
# #         (bw,bh), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
# #         bx = W - bw - 60
# #         cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
# #         cv2.putText(frame, badge, (bx, 30+bh+2),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# # # ══════════════════════════════════════════════════════════════════════════════
# # #  MonitoringStream — single-threaded, v19 detection logic
# # # ══════════════════════════════════════════════════════════════════════════════
# # class MonitoringStream(threading.Thread):
# #     """
# #     Runs in its own thread but detection is synchronous inside that thread —
# #     exactly like v19.  YOLO + state machine + drawing all happen in one loop,
# #     so every displayed frame has correct, current detection boxes.

# #     GUI reads self.latest_frame  (thread-safe via self._lock).
# #     fall_cb is called when a fall is confirmed.
# #     """

# #     def __init__(self, patient_name, frame_cb, fall_cb=None,
# #                  zones=None, video_path=VIDEO_PATH):
# #         super().__init__(daemon=True, name="MonitoringStream")
# #         self.patient_name = patient_name
# #         self.frame_cb     = frame_cb    # unused — GUI reads latest_frame directly
# #         self.fall_cb      = fall_cb
# #         self.video_path   = video_path
# #         self.running      = False
# #         self.state        = "STARTING"
# #         self.score        = 0
# #         self.latest_frame = None
# #         self._lock        = threading.Lock()

# #         # Load zones
# #         self.zones = zones if zones is not None else self._load_zones()

# #     def _load_zones(self):
# #         zf = BASE_DIR / "data" / "patients" / self.patient_name / "safe_zones.json"
# #         if not zf.exists():
# #             return []
# #         try:
# #             with open(zf) as f:
# #                 data = json.load(f)
# #             zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
# #             print(f"[MonitoringStream] Loaded {len(zones)} zone(s)")
# #             return zones
# #         except Exception as e:
# #             print(f"[MonitoringStream] Zone load error: {e}")
# #             return []

# #     def stop(self):
# #         self.running = False

# #     # ── Fall analysis (identical to v19) ─────────────────────────────────────
# #     def _analyze_fall(self, fmc, ar_hist,
# #                       flow_history, drop_history, area_change_history,
# #                       posture_history, raw_drop_history, raw_area_history,
# #                       pre_posture="none", current_person_box=None):

# #         if (current_person_box is not None
# #                 and person_in_safe_zone(current_person_box, self.zones)):
# #             return False, 0, "blocked:person_in_safe_zone"

# #         flow_list  = list(flow_history)
# #         drop_list  = list(drop_history)
# #         area_list  = list(area_change_history)
# #         post_list  = list(posture_history)
# #         ar_list    = list(ar_hist) if ar_hist else []
# #         raw_drops  = list(raw_drop_history)
# #         raw_areas  = list(raw_area_history)
# #         score = 0; notes = []

# #         if pre_posture == "sitting":
# #             if fmc >= FALL_MODEL_CONSEC:
# #                 notes.append("sitting_override_by_fallmodel")
# #             else:
# #                 return False, 0, "blocked:sitting_to_lying(sofa/bed)"

# #         upright_count = sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
# #                             if p in ("standing", "sitting"))
# #         if upright_count < MIN_UPRIGHT_FRAMES:
# #             return False, 0, f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

# #         has_sudden_drop = any(d >= SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
# #         has_sudden_area = any(a >= SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
# #         if not has_sudden_drop and not has_sudden_area and fmc == 0:
# #             return False, 0, "blocked:gradual_transition(no_spike,no_fallmodel)"

# #         pre_drops   = drop_list[-PRE_LYING_WINDOW:] if drop_list else []
# #         max_drop    = max(pre_drops) if pre_drops else 0.0
# #         if   max_drop >= DROP_FAST_PX: score += 2; notes.append(f"fast_drop={max_drop:.0f}")
# #         elif max_drop >= DROP_ANY_PX:  score += 1; notes.append(f"drop={max_drop:.0f}")

# #         pre_area      = area_list[-PRE_LYING_WINDOW:] if area_list else []
# #         max_area_chg  = max(pre_area) if pre_area else 0.0
# #         if   max_area_chg >= AREA_CHANGE_HIGH: score += 2; notes.append(f"area_chg={max_area_chg:.2f}")
# #         elif max_area_chg >= AREA_CHANGE_ANY:  score += 1; notes.append(f"area_any={max_area_chg:.2f}")

# #         n = len(flow_list)
# #         pre_flow     = flow_list[max(0, n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
# #                                   max(0, n-POST_LYING_WINDOW)]
# #         max_pre_flow = max(pre_flow) if pre_flow else 0.0
# #         if   max_pre_flow >= FLOW_SPIKE_THRESH: score += 2; notes.append(f"flow_spike={max_pre_flow:.2f}")
# #         elif max_pre_flow >= FLOW_ANY_THRESH:   score += 1; notes.append(f"flow={max_pre_flow:.2f}")

# #         if len(ar_list) >= 4:
# #             ar_before = float(np.mean(ar_list[:max(1, len(ar_list)-PRE_LYING_WINDOW)]))
# #             ar_after  = float(np.mean(ar_list[-3:]))
# #             ar_drop   = ar_before - ar_after
# #             if ar_drop >= ASPECT_DROP_THRESH:
# #                 score += 2; notes.append(f"aspect_flip={ar_drop:.2f}")

# #         if fmc >= FALL_MODEL_CONSEC:
# #             score += 3; notes.append(f"fall_model={fmc}f")

# #         if (max_drop < DROP_ANY_PX and max_area_chg < AREA_CHANGE_ANY
# #                 and max_pre_flow < FLOW_ANY_THRESH):
# #             return False, score, (f"blocked:no_motion(d={max_drop:.1f} "
# #                                    f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

# #         post_flow   = (flow_list[-POST_LYING_WINDOW:]
# #                        if len(flow_list) >= POST_LYING_WINDOW else flow_list)
# #         still_ratio = sum(1 for f in post_flow if f < FLOW_STILL_THRESH) / max(len(post_flow), 1)
# #         if still_ratio >= 0.35:
# #             score += 1; notes.append(f"still={still_ratio:.0%}")

# #         reason = f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
# #         if score >= FALL_SCORE_NEEDED:
# #             return True, score, f"FALL:{reason}"
# #         return False, score, f"safe:{reason}"

# #     # ── Main detection loop (v19 single-thread logic) ─────────────────────────
# #     def run(self):
# #         self.running = True

# #         # Load YOLO models
# #         try:
# #             from ultralytics import YOLO
# #             import torch as _torch
# #             if FORCE_CUDA and not _torch.cuda.is_available():
# #                 raise RuntimeError("CUDA not available — install CUDA PyTorch: "
# #                                    "pip install torch --index-url https://download.pytorch.org/whl/cu121")
# #             device = "cuda" if _torch.cuda.is_available() else "cpu"
# #             if device == "cuda":
# #                 gpu_name = _torch.cuda.get_device_name(0)
# #                 vram_gb  = _torch.cuda.get_device_properties(0).total_memory / 1e9
# #                 print(f"[MonitoringStream] GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)")
# #             else:
# #                 print("[MonitoringStream] WARNING: CUDA not found — running on CPU (slow!)")
# #                 print("[MonitoringStream] Fix: pip install torch --index-url https://download.pytorch.org/whl/cu121")

# #             print(f"[MonitoringStream] Device: {device} | YOLO every {YOLO_EVERY_N} frame(s) | imgsz={YOLO_IMGSZ}")
# #             print("[MonitoringStream] Loading YOLO models...")
# #             fall_model    = YOLO(FALL_MODEL_PATH).to(device)
# #             posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

# #             # FP16 note: half=True is passed per-inference call (correct Ultralytics API).
# #             # Do NOT call model.half() — it causes dtype mismatch errors on some layers.
# #             use_half = (device == "cuda")
# #             if use_half:
# #                 print("[MonitoringStream] FP16 (half precision) will be used at inference.")

# #             # Warmup: run one dummy frame so the FIRST real frame is not slow
# #             import numpy as _np
# #             _dummy = _np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=_np.uint8)
# #             fall_model(_dummy,    imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
# #             posture_model(_dummy, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
# #             print("[MonitoringStream] Models warmed up and ready.")
# #         except Exception as e:
# #             print(f"[MonitoringStream] Model load error: {e}")
# #             if self.fall_cb:
# #                 self.fall_cb(0, str(e), "error", "")
# #             return

# #         # Start video session (same as v19)
# #         video_session = None
# #         try:
# #             from video_recorder import VideoSession
# #             video_session = VideoSession(
# #                 patient_name    = self.patient_name,
# #                 fps             = 20.0,
# #                 frame_size      = (FRAME_W, FRAME_H),
# #                 save_continuous = True,
# #             )
# #             video_session.start()
# #             print(f"[MonitoringStream] Recording to data/patients/{self.patient_name}/videos/")
# #         except Exception as e:
# #             print(f"[MonitoringStream] VideoSession failed (no recording): {e}")

# #         # Open video / camera
# #         src = (int(self.video_path)
# #                if str(self.video_path).isdigit()
# #                else self.video_path)
# #         cap = cv2.VideoCapture(src)
# #         if not cap.isOpened():
# #             print("[MonitoringStream] Cannot open video source.")
# #             if video_session: video_session.stop()
# #             return

# #         # ── State variables (identical to v19) ───────────────────────────────
# #         posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
# #         flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
# #         drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
# #         area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
# #         aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
# #         raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
# #         raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

# #         prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
# #         lying_consec = standing_consec = fall_model_consec = 0
# #         frames_since_lying = 0; episode_analyzed = False
# #         last_valid_posture = "none"; posture_persist_counter = 0
# #         fall_latch_ctr = recovery_latch_ctr = 0
# #         final_state = "STARTING"; fall_reason = ""
# #         post_fall_lying = False; pre_lying_posture = "none"
# #         episode_locked = False; last_upright_posture = "none"
# #         sitting_consec_pre = 0; safe_lying_locked = False
# #         last_known_posture = "none"
# #         frame_count = 0
# #         _last_dets     = []     # cached YOLO detections for skipped frames
# #         _last_fall_det = False  # cached fall model result

# #         print("[MonitoringStream] Detection loop started.")

# #         # ── Main loop — identical structure to v19 ────────────────────────────
# #         while self.running:
# #             ret, frame = cap.read()
# #             if not ret:
# #                 # Loop video file back to start
# #                 cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
# #                 # Reset per-frame motion state so first frame of next loop
# #                 # doesn't get false drop/area spikes from stale values
# #                 prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
# #                 continue

# #             frame_count += 1
# #             frame     = cv2.resize(frame, (FRAME_W, FRAME_H))
# #             gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# #             # ── YOLO frame skipping ───────────────────────────────────────────
# #             # Run YOLO only every YOLO_EVERY_N frames.
# #             # Skipped frames reuse _last_dets / _last_fall_det (cached below).
# #             # Motion tracking (flow, drop, area) still runs every frame — fast.
# #             run_yolo = (frame_count % YOLO_EVERY_N == 0)

# #             # ── FALL MODEL ────────────────────────────────────────────────────
# #             fall_detected = False
# #             if run_yolo:
# #                 for r in fall_model(frame, conf=0.5, imgsz=YOLO_IMGSZ, half=use_half, verbose=False):
# #                     for box in r.boxes:
# #                         cls   = int(box.cls[0])
# #                         label = fall_model.names[cls]
# #                         conf  = float(box.conf[0])
# #                         x1, y1, x2, y2 = map(int, box.xyxy[0])
# #                         if label.lower() == "fall":
# #                             fall_detected = True
# #                         cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,180), 2)
# #                         cv2.putText(frame, f"{label} {conf:.2f}", (x1, max(y1-8, 70)),
# #                                     cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,0,180), 1)
# #                 _last_fall_det = fall_detected
# #             else:
# #                 # Reuse last result — redraw cached boxes on this frame
# #                 fall_detected = _last_fall_det
# #                 for (lbl, (x1,y1,x2,y2), cf) in _last_dets:
# #                     col = (0,0,180) if lbl == "fall" else ((120,120,120) if (lbl=="lying" and get_aspect_ratio((x1,y1,x2,y2))>LYING_ASPECT_RATIO_MAX) else (0,180,0))
# #                     cv2.rectangle(frame, (x1,y1), (x2,y2), col, 2)
# #             fall_model_consec = fall_model_consec + 1 if fall_detected else 0

# #             # ── POSTURE MODEL ─────────────────────────────────────────────────
# #             all_detections = []
# #             if run_yolo:
# #                 for r in posture_model(frame, conf=0.45, imgsz=YOLO_IMGSZ, half=use_half, verbose=False):
# #                     for box in r.boxes:
# #                         conf  = float(box.conf[0])
# #                         cls   = int(box.cls[0])
# #                         label = posture_model.names[cls].lower()
# #                         x1, y1, x2, y2 = map(int, box.xyxy[0])
# #                         all_detections.append((label, (x1,y1,x2,y2), conf))
# #                         ar     = get_aspect_ratio((x1,y1,x2,y2))
# #                         reject = (label == "lying" and ar > LYING_ASPECT_RATIO_MAX)
# #                         color  = (120,120,120) if reject else (0,180,0)
# #                         cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
# #                         cv2.putText(frame, f"{label}{'[X]' if reject else ''} {conf:.2f}",
# #                                     (x1, max(y1-26, 70)),
# #                                     cv2.FONT_HERSHEY_SIMPLEX, 0.38,
# #                                     (100,100,100) if reject else (0,180,0), 1)
# #                 _last_dets = all_detections   # cache for skipped frames
# #             else:
# #                 all_detections = _last_dets   # reuse cached detections

# #             raw_posture_label, person_box = select_main_subject(all_detections)
# #             active_zone  = person_zone(person_box, self.zones)
# #             on_safe_zone = active_zone is not None

# #             if raw_posture_label != "none":
# #                 last_valid_posture      = raw_posture_label
# #                 posture_persist_counter = 0
# #                 posture_label           = raw_posture_label
# #             else:
# #                 posture_persist_counter += 1
# #                 posture_label = (last_valid_posture
# #                                  if posture_persist_counter <= POSTURE_PERSIST_FRAMES
# #                                  else "none")
# #             if posture_label != "none":
# #                 last_known_posture = posture_label

# #             flow_energy = compute_flow_energy(gray_curr, prev_gray, person_box)
# #             flow_history.append(flow_energy)
# #             prev_gray = gray_curr.copy()

# #             drop_velocity = 0.0; area_change = 0.0
# #             curr_ar = prev_aspect_ratio if prev_aspect_ratio else 1.5
# #             if person_box is not None:
# #                 x1, y1, x2, y2 = person_box
# #                 cy       = (y1 + y2) / 2.0
# #                 curr_ar  = get_aspect_ratio(person_box)
# #                 curr_area = get_bbox_area(person_box)
# #                 if prev_center_y  is not None: drop_velocity = cy - prev_center_y
# #                 if prev_bbox_area is not None and prev_bbox_area > 0:
# #                     area_change = abs(curr_area - prev_bbox_area) / prev_bbox_area
# #                 prev_center_y  = cy
# #                 prev_bbox_area = curr_area
# #                 prev_aspect_ratio = curr_ar

# #             drop_history.append(max(drop_velocity, 0.0))
# #             area_change_history.append(area_change)
# #             aspect_ratio_history.append(curr_ar)
# #             raw_drop_history.append(max(drop_velocity, 0.0))
# #             raw_area_history.append(area_change)

# #             if fall_latch_ctr == 0:
# #                 posture_history.append(posture_label)

# #             # Track pre-lying posture (same as v19)
# #             if lying_consec < LYING_CONFIRM_FRAMES:
# #                 if posture_label == "standing":
# #                     last_upright_posture = "standing"; sitting_consec_pre = 0
# #                 elif posture_label == "sitting":
# #                     sitting_consec_pre += 1
# #                     if sitting_consec_pre >= SITTING_CONFIRM_FOR_PREPOSTURE:
# #                         last_upright_posture = "sitting"
# #                 else:
# #                     sitting_consec_pre = 0

# #             if posture_label == "lying":
# #                 lying_consec   += 1; standing_consec = 0
# #                 if lying_consec == LYING_CONFIRM_FRAMES and not episode_locked:
# #                     pre_lying_posture = last_upright_posture; episode_locked = True
# #                 if on_safe_zone and lying_consec >= LYING_CONFIRM_FRAMES and not safe_lying_locked:
# #                     safe_lying_locked = True
# #                     fall_reason = f"blocked:person_on_{active_zone['type']}(safe_zone)"
# #             elif posture_label in ("standing", "sitting"):
# #                 standing_consec += 1
# #                 if standing_consec >= STANDING_CONFIRM_FRAMES:
# #                     lying_consec      = 0; frames_since_lying = 0
# #                     episode_analyzed  = False; fall_reason = ""
# #                     post_fall_lying   = False; episode_locked = False
# #                     pre_lying_posture = "none"; sitting_consec_pre = 0
# #                     safe_lying_locked = False
# #             else:
# #                 standing_consec = 0

# #             if lying_consec >= LYING_CONFIRM_FRAMES:
# #                 frames_since_lying += 1
# #             else:
# #                 if frames_since_lying > 0:
# #                     post_fall_lying   = False; episode_analyzed  = False
# #                     episode_locked    = False; pre_lying_posture  = "none"
# #                     sitting_consec_pre = 0;    safe_lying_locked  = False
# #                 frames_since_lying = 0

# #             current_score = 0
# #             in_analysis_window = ANALYSIS_START <= frames_since_lying <= ANALYSIS_END

# #             # ── Fall analysis trigger 1: analysis window (same as v19) ────────
# #             if (in_analysis_window and not episode_analyzed
# #                     and not safe_lying_locked and fall_latch_ctr == 0):
# #                 is_fall, current_score, fall_reason = self._analyze_fall(
# #                     fall_model_consec, aspect_ratio_history,
# #                     flow_history, drop_history, area_change_history,
# #                     posture_history, raw_drop_history, raw_area_history,
# #                     pre_posture=pre_lying_posture, current_person_box=person_box)
# #                 if is_fall:
# #                     fall_latch_ctr   = FALL_LATCH_FRAMES
# #                     episode_analyzed = True; post_fall_lying = True
# #                     clip_path = ""
# #                     if video_session:
# #                         try: clip_path = str(video_session.on_fall())
# #                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
# #                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
# #                     if self.fall_cb:
# #                         threading.Thread(
# #                             target=self.fall_cb,
# #                             args=(current_score, fall_reason, posture_label, clip_path),
# #                             daemon=True).start()
# #                 else:
# #                     safe_lying_locked = True

# #             # ── Fall analysis trigger 2: fall model + lying (same as v19) ─────
# #             if (fall_detected and fall_model_consec >= FALL_MODEL_CONSEC
# #                     and lying_consec >= LYING_CONFIRM_FRAMES
# #                     and not safe_lying_locked and fall_latch_ctr == 0
# #                     and not episode_analyzed):
# #                 is_fall, current_score, fall_reason = self._analyze_fall(
# #                     fall_model_consec, aspect_ratio_history,
# #                     flow_history, drop_history, area_change_history,
# #                     posture_history, raw_drop_history, raw_area_history,
# #                     pre_posture=pre_lying_posture, current_person_box=person_box)
# #                 if is_fall:
# #                     fall_latch_ctr   = FALL_LATCH_FRAMES
# #                     episode_analyzed = True; post_fall_lying = True
# #                     clip_path = ""
# #                     if video_session:
# #                         try: clip_path = str(video_session.on_fall())
# #                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
# #                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
# #                     if self.fall_cb:
# #                         threading.Thread(
# #                             target=self.fall_cb,
# #                             args=(current_score, fall_reason, posture_label, clip_path),
# #                             daemon=True).start()
# #                 else:
# #                     safe_lying_locked = True

# #             # ── Fall analysis trigger 3: fall model + unknown posture (v19) ───
# #             if (posture_label == "none" and fall_model_consec >= FALL_MODEL_CONSEC
# #                     and not safe_lying_locked and fall_latch_ctr == 0
# #                     and not episode_analyzed
# #                     and last_known_posture in ("standing", "sitting")
# #                     and not person_in_safe_zone(person_box, self.zones)):
# #                 is_fall, current_score, fall_reason = self._analyze_fall(
# #                     fall_model_consec, aspect_ratio_history,
# #                     flow_history, drop_history, area_change_history,
# #                     posture_history, raw_drop_history, raw_area_history,
# #                     pre_posture=last_known_posture, current_person_box=person_box)
# #                 if is_fall:
# #                     fall_latch_ctr   = FALL_LATCH_FRAMES
# #                     episode_analyzed = True; post_fall_lying = True
# #                     fall_reason      = f"[FM-UNKNOWN] {fall_reason}"
# #                     clip_path = ""
# #                     if video_session:
# #                         try: clip_path = str(video_session.on_fall())
# #                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
# #                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
# #                     if self.fall_cb:
# #                         threading.Thread(
# #                             target=self.fall_cb,
# #                             args=(current_score, fall_reason, posture_label, clip_path),
# #                             daemon=True).start()

# #             # ── Safe-zone latch cancel (same as v19) ──────────────────────────
# #             if fall_latch_ctr > 0 and on_safe_zone:
# #                 fall_latch_ctr    = 0; recovery_latch_ctr = 0
# #                 post_fall_lying   = False; safe_lying_locked = True
# #                 fall_reason       = "blocked:entered_safe_zone_during_latch"
# #                 print("[BLOCK-B] Latch cancelled — person in safe zone")

# #             # ── State machine (same as v19) ───────────────────────────────────
# #             if fall_latch_ctr > 0:
# #                 fall_latch_ctr -= 1; final_state = "FALL"
# #                 if fall_latch_ctr == 0: recovery_latch_ctr = RECOVERY_LATCH_FRAMES
# #             elif recovery_latch_ctr > 0:
# #                 recovery_latch_ctr -= 1; final_state = "RECOVERY"
# #             else:
# #                 if posture_label == "lying":
# #                     if post_fall_lying: final_state = "LYING (POST-FALL)"
# #                     elif on_safe_zone:  final_state = f"LYING (ON {active_zone['type'].upper()})"
# #                     else:               final_state = "LYING (SAFE)"
# #                 elif posture_label == "standing": final_state = "STANDING"
# #                 elif posture_label == "sitting":  final_state = "SITTING"
# #                 else:                              final_state = "UNKNOWN"

# #             self.state = final_state
# #             self.score = current_score

# #             # ── Draw overlays (same as v19) ───────────────────────────────────
# #             draw_all_zones(frame, self.zones, active_zone)
# #             draw_banner(frame, final_state)
# #             draw_signals(frame, flow_energy, area_change,
# #                          max(drop_velocity, 0), current_score, FALL_SCORE_NEEDED)
# #             is_saving = (video_session.clipper.is_saving
# #                          if video_session and hasattr(video_session, 'clipper') else False)
# #             draw_rec_indicator(frame, is_saving, frame_count)

# #             H, W = frame.shape[:2]
# #             if on_safe_zone:
# #                 col = ZONE_COLORS[active_zone["type"]]
# #                 draw_pill_label(frame, f"ON {active_zone['type'].upper()}",
# #                                 W-108, 88, col, scale=0.40)
# #             if safe_lying_locked:
# #                 draw_pill_label(frame, "SAFE-LOCK", W-100, 112, (30,130,60), scale=0.35)

# #             selected_ar = get_aspect_ratio(person_box) if person_box else 0.0
# #             dbg = (f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
# #                    f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
# #                    f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
# #                    f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
# #                    f"zone:{active_zone['type'] if active_zone else 'none'}  "
# #                    f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
# #             cv2.putText(frame, dbg, (6, H-6),
# #                         cv2.FONT_HERSHEY_SIMPLEX, 0.27, (130,130,155), 1)
# #             if fall_reason:
# #                 cv2.putText(frame, fall_reason, (6, H-18),
# #                             cv2.FONT_HERSHEY_SIMPLEX, 0.28, (55,195,255), 1)

# #             # Feed the FULLY DRAWN frame to recorder (same as v19 final version)
# #             if video_session:
# #                 video_session.feed(frame)

# #             # Write annotated frame to GUI buffer (RGB for tkinter)
# #             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
# #             with self._lock:
# #                 self.latest_frame = (frame_rgb, final_state, current_score)

# #         # ── Cleanup ───────────────────────────────────────────────────────────
# #         cap.release()
# #         if video_session:
# #             video_session.stop()
# #         print("[MonitoringStream] Stopped.")






















# """
# LEO — Monitoring Stream (GPU-Accelerated, v19 Logic)
# =====================================================

# Full GPU acceleration:
#   • Both YOLO models run IN PARALLEL on GPU via ThreadPoolExecutor
#     (cuts YOLO time roughly in half vs sequential)
#   • FP16 (half precision) inference — 2x faster, half the VRAM usage
#   • GPU optical flow via cv2.cuda (falls back to CPU if unavailable)
#   • imgsz=640 — full resolution since GPU can handle it
#   • Warmup inference so the first real frame is not slow

# Detection logic is identical to the working standalone v19 script.
# """

# import cv2
# import numpy as np
# import json
# import math
# import threading
# from concurrent.futures import ThreadPoolExecutor
# from collections import deque
# from pathlib import Path

# BASE_DIR = Path(__file__).parent

# VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
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

# FRAME_W, FRAME_H = 640, 480

# # ── GPU speed config ──────────────────────────────────────────────────────────
# # Both YOLO models run IN PARALLEL on the GPU — cuts YOLO time ~50%.
# # MX550 (2GB VRAM) handles both at FP16 with imgsz=640 fine.
# YOLO_EVERY_N = 1     # run YOLO on every frame (GPU is fast enough)
# YOLO_IMGSZ   = 640   # full resolution — GPU handles it; better accuracy
# FORCE_CUDA   = False # set True to crash loudly if GPU is missing

# # ── Detection parameters (identical to v19) ───────────────────────────────────
# LYING_CONFIRM_FRAMES           = 8
# STANDING_CONFIRM_FRAMES        = 3
# POSTURE_PERSIST_FRAMES         = 8
# LYING_ASPECT_RATIO_MAX         = 1.2
# SITTING_CONFIRM_FOR_PREPOSTURE = 3

# DROP_FAST_PX       = 7
# DROP_ANY_PX        = 3
# AREA_CHANGE_HIGH   = 0.12
# AREA_CHANGE_ANY    = 0.05
# SUDDEN_DROP_THRESH = 7.0
# SUDDEN_AREA_THRESH = 0.20
# FLOW_SPIKE_THRESH  = 1.4
# FLOW_ANY_THRESH    = 0.7
# FLOW_STILL_THRESH  = 0.9
# ASPECT_DROP_THRESH = 0.18
# FALL_MODEL_CONSEC  = 2
# FALL_SCORE_NEEDED  = 4
# ANALYSIS_START     = 4
# ANALYSIS_END       = 40
# PRE_LYING_WINDOW   = 25
# POST_LYING_WINDOW  = 10
# UPRIGHT_LOOKBACK   = 55
# MIN_UPRIGHT_FRAMES = 15
# FALL_LATCH_FRAMES     = 65
# RECOVERY_LATCH_FRAMES = 25

# # ── Colors (identical to v19) ─────────────────────────────────────────────────
# ZONE_COLORS = {
#     "bed":  (0, 200, 255),
#     "sofa": (0, 140, 255),
# }

# STATE_META = {
#     "FALL":              ((0,   0,   220), "!"),
#     "LYING (POST-FALL)": ((0,   60,  190), "!"),
#     "LYING (SAFE)":      ((140, 80,  0),   "~"),
#     "LYING (ON BED)":    ((0,   110, 150), "~"),
#     "LYING (ON SOFA)":   ((0,   90,  165), "~"),
#     "STANDING":          ((0,   160, 30),  "^"),
#     "SITTING":           ((0,   130, 120), "s"),
#     "RECOVERY":          ((130, 0,   160), "r"),
#     "UNKNOWN":           ((75,  75,  75),  "?"),
#     "STARTING":          ((60,  60,  60),  "."),
# }


# # ── Helpers (identical to v19) ────────────────────────────────────────────────

# def get_aspect_ratio(box):
#     x1, y1, x2, y2 = box
#     return max(y2 - y1, 1) / max(x2 - x1, 1)

# def get_bbox_area(box):
#     x1, y1, x2, y2 = box
#     return max(x2 - x1, 0) * max(y2 - y1, 0)

# # Check once at import time whether cv2.cuda optical flow is available
# _CUDA_FLOW = None
# def _init_cuda_flow():
#     global _CUDA_FLOW
#     try:
#         _CUDA_FLOW = cv2.cuda.FarnebackOpticalFlow.create(
#             numLevels=2, pyrScale=0.5, fastPyramids=False,
#             winSize=12, numIters=2, polyN=5, polySigma=1.1, flags=0)
#         print("[MonitoringStream] GPU optical flow enabled (cv2.cuda).")
#     except Exception:
#         _CUDA_FLOW = None
#         print("[MonitoringStream] GPU optical flow unavailable — using CPU Farneback.")

# def compute_flow_energy(gray_curr, gray_prev, box):
#     if gray_prev is None or box is None: return 0.0
#     x1 = max(int(box[0]), 0); y1 = max(int(box[1]), 0)
#     x2 = min(int(box[2]), gray_curr.shape[1])
#     y2 = min(int(box[3]), gray_curr.shape[0])
#     if x2 <= x1 + 4 or y2 <= y1 + 4: return 0.0
#     roi_curr = gray_curr[y1:y2, x1:x2]
#     roi_prev = gray_prev[y1:y2, x1:x2]
#     if _CUDA_FLOW is not None:
#         try:
#             g_curr = cv2.cuda_GpuMat(); g_curr.upload(roi_curr)
#             g_prev = cv2.cuda_GpuMat(); g_prev.upload(roi_prev)
#             g_flow = _CUDA_FLOW.calc(g_prev, g_curr, None)
#             flow   = g_flow.download()
#             return float(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))
#         except Exception:
#             pass  # fall through to CPU
#     flow = cv2.calcOpticalFlowFarneback(
#         roi_prev, roi_curr, None,
#         pyr_scale=0.5, levels=2, winsize=12, iterations=2,
#         poly_n=5, poly_sigma=1.1, flags=0)
#     return float(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))

# def select_main_subject(detections):
#     if not detections: return "none", None
#     best_label, best_box, best_area, best_conf = "none", None, -1, -1
#     for (label, box, conf) in detections:
#         area = get_bbox_area(box); ar = get_aspect_ratio(box)
#         if label == "lying" and ar > LYING_ASPECT_RATIO_MAX: continue
#         if area > best_area or (area == best_area and conf > best_conf):
#             best_area, best_conf = area, conf
#             best_label, best_box = label, box
#     return best_label, best_box

# def person_zone(person_box, zones):
#     if person_box is None or not zones: return None
#     cx = (person_box[0] + person_box[2]) / 2
#     cy = (person_box[1] + person_box[3]) / 2
#     for z in zones:
#         x1, y1, x2, y2 = z["box"]
#         if x1 <= cx <= x2 and y1 <= cy <= y2:
#             return z
#     return None

# def person_in_safe_zone(person_box, zones):
#     return person_zone(person_box, zones) is not None


# # ── Draw helpers (identical to v19) ──────────────────────────────────────────

# def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
#     (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
#     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
#     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
#     cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
#                 (255,255,255), 1, cv2.LINE_AA)

# def draw_zone_on_frame(img, z, is_active=False):
#     x1, y1, x2, y2 = z["box"]
#     col   = ZONE_COLORS[z["type"]]
#     alpha = 0.22 if is_active else 0.12
#     ov    = img.copy()
#     cv2.rectangle(ov, (x1,y1), (x2,y2), col, -1)
#     cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)
#     cv2.rectangle(img, (x1,y1), (x2,y2), col, 2 if is_active else 1, cv2.LINE_AA)
#     label = z["type"].upper() + (" *" if is_active else "")
#     (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
#     pad = 4
#     bov = img.copy()
#     cv2.rectangle(bov, (x1, y1), (x1+tw+pad*2, y1+th+pad*2), col, -1)
#     cv2.addWeighted(bov, 0.80, img, 0.20, 0, img)
#     cv2.putText(img, label, (x1+pad, y1+th+pad),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,255), 1, cv2.LINE_AA)

# def draw_all_zones(img, zones, active_zone=None):
#     for z in zones:
#         draw_zone_on_frame(img, z, is_active=(z is active_zone))

# def draw_banner(frame, state):
#     col = STATE_META.get(state, ((100,100,100),"?"))[0]
#     W = frame.shape[1]
#     ov = frame.copy()
#     cv2.rectangle(ov, (0,0), (W,58), col, -1)
#     cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
#     cv2.rectangle(frame, (0,0), (5,58), col, -1)
#     cv2.line(frame, (0,58), (W,58), col, 1)
#     cv2.putText(frame, f"STATE:  {state}",
#                 (16,40), cv2.FONT_HERSHEY_SIMPLEX,
#                 0.95, (255,255,255), 2, cv2.LINE_AA)

# def draw_signals(frame, flow_val, area_chg, drop_vel, score, fall_score_needed):
#     H, W = frame.shape[:2]
#     px, py = 6, H-90; pw = 192
#     ov = frame.copy()
#     cv2.rectangle(ov, (px-2,py-2), (px+pw,py+80), (12,12,18), -1)
#     cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
#     cv2.rectangle(frame, (px-2,py-2), (px+pw,py+80), (50,50,70), 1)
#     sigs = [("FLOW", flow_val, 5.0,  (0,200,255)),
#             ("AREA", area_chg, 0.3,  (0,180,120)),
#             ("DROP", drop_vel, 20.0, (60,100,255)),
#             ("SCOR", score,    fall_score_needed*1.5, (0,60,255))]
#     bx = px+44; bmax = pw-52
#     for i, (lbl, val, mx, col) in enumerate(sigs):
#         y  = py + 6 + i*18
#         bw = int(min(val / max(mx, 0.001), 1.0) * bmax)
#         cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (28,28,40), -1)
#         if bw > 0: cv2.rectangle(frame, (bx,y+2), (bx+bw,y+12), col, -1)
#         cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (55,55,75), 1)
#         cv2.putText(frame, lbl, (px,y+12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140,140,165), 1)
#         cv2.putText(frame, f"{val:.1f}", (bx+bmax+3,y+12),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.27, (170,170,195), 1)

# def draw_rec_indicator(frame, is_saving_clip, tick):
#     H, W = frame.shape[:2]
#     pulse = int(180 + 75 * math.sin(tick * 0.2))
#     cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
#     cv2.putText(frame, "REC", (W-45, 25),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
#     if is_saving_clip:
#         badge = "  SAVING FALL CLIP  "
#         (bw,bh), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
#         bx = W - bw - 60
#         cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
#         cv2.putText(frame, badge, (bx, 30+bh+2),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# # ══════════════════════════════════════════════════════════════════════════════
# #  MonitoringStream — single-threaded, v19 detection logic
# # ══════════════════════════════════════════════════════════════════════════════
# class MonitoringStream(threading.Thread):
#     """
#     Runs in its own thread but detection is synchronous inside that thread —
#     exactly like v19.  YOLO + state machine + drawing all happen in one loop,
#     so every displayed frame has correct, current detection boxes.

#     GUI reads self.latest_frame  (thread-safe via self._lock).
#     fall_cb is called when a fall is confirmed.
#     """

#     def __init__(self, patient_name, frame_cb, fall_cb=None,
#                  zones=None, video_path=VIDEO_PATH):
#         super().__init__(daemon=True, name="MonitoringStream")
#         self.patient_name = patient_name
#         self.frame_cb     = frame_cb    # unused — GUI reads latest_frame directly
#         self.fall_cb      = fall_cb
#         self.video_path   = video_path
#         self.running      = False
#         self.state        = "STARTING"
#         self.score        = 0
#         self.latest_frame = None
#         self._lock        = threading.Lock()

#         # Load zones
#         self.zones = zones if zones is not None else self._load_zones()

#     def _load_zones(self):
#         zf = BASE_DIR / "data" / "patients" / self.patient_name / "safe_zones.json"
#         if not zf.exists():
#             return []
#         try:
#             with open(zf) as f:
#                 data = json.load(f)
#             zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
#             print(f"[MonitoringStream] Loaded {len(zones)} zone(s)")
#             return zones
#         except Exception as e:
#             print(f"[MonitoringStream] Zone load error: {e}")
#             return []

#     def stop(self):
#         self.running = False

#     # ── Fall analysis (identical to v19) ─────────────────────────────────────
#     def _analyze_fall(self, fmc, ar_hist,
#                       flow_history, drop_history, area_change_history,
#                       posture_history, raw_drop_history, raw_area_history,
#                       pre_posture="none", current_person_box=None):

#         if (current_person_box is not None
#                 and person_in_safe_zone(current_person_box, self.zones)):
#             return False, 0, "blocked:person_in_safe_zone"

#         flow_list  = list(flow_history)
#         drop_list  = list(drop_history)
#         area_list  = list(area_change_history)
#         post_list  = list(posture_history)
#         ar_list    = list(ar_hist) if ar_hist else []
#         raw_drops  = list(raw_drop_history)
#         raw_areas  = list(raw_area_history)
#         score = 0; notes = []

#         if pre_posture == "sitting":
#             if fmc >= FALL_MODEL_CONSEC:
#                 notes.append("sitting_override_by_fallmodel")
#             else:
#                 return False, 0, "blocked:sitting_to_lying(sofa/bed)"

#         upright_count = sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
#                             if p in ("standing", "sitting"))
#         if upright_count < MIN_UPRIGHT_FRAMES:
#             return False, 0, f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

#         has_sudden_drop = any(d >= SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
#         has_sudden_area = any(a >= SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
#         if not has_sudden_drop and not has_sudden_area and fmc == 0:
#             return False, 0, "blocked:gradual_transition(no_spike,no_fallmodel)"

#         pre_drops   = drop_list[-PRE_LYING_WINDOW:] if drop_list else []
#         max_drop    = max(pre_drops) if pre_drops else 0.0
#         if   max_drop >= DROP_FAST_PX: score += 2; notes.append(f"fast_drop={max_drop:.0f}")
#         elif max_drop >= DROP_ANY_PX:  score += 1; notes.append(f"drop={max_drop:.0f}")

#         pre_area      = area_list[-PRE_LYING_WINDOW:] if area_list else []
#         max_area_chg  = max(pre_area) if pre_area else 0.0
#         if   max_area_chg >= AREA_CHANGE_HIGH: score += 2; notes.append(f"area_chg={max_area_chg:.2f}")
#         elif max_area_chg >= AREA_CHANGE_ANY:  score += 1; notes.append(f"area_any={max_area_chg:.2f}")

#         n = len(flow_list)
#         pre_flow     = flow_list[max(0, n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
#                                   max(0, n-POST_LYING_WINDOW)]
#         max_pre_flow = max(pre_flow) if pre_flow else 0.0
#         if   max_pre_flow >= FLOW_SPIKE_THRESH: score += 2; notes.append(f"flow_spike={max_pre_flow:.2f}")
#         elif max_pre_flow >= FLOW_ANY_THRESH:   score += 1; notes.append(f"flow={max_pre_flow:.2f}")

#         if len(ar_list) >= 4:
#             ar_before = float(np.mean(ar_list[:max(1, len(ar_list)-PRE_LYING_WINDOW)]))
#             ar_after  = float(np.mean(ar_list[-3:]))
#             ar_drop   = ar_before - ar_after
#             if ar_drop >= ASPECT_DROP_THRESH:
#                 score += 2; notes.append(f"aspect_flip={ar_drop:.2f}")

#         if fmc >= FALL_MODEL_CONSEC:
#             score += 3; notes.append(f"fall_model={fmc}f")

#         if (max_drop < DROP_ANY_PX and max_area_chg < AREA_CHANGE_ANY
#                 and max_pre_flow < FLOW_ANY_THRESH):
#             return False, score, (f"blocked:no_motion(d={max_drop:.1f} "
#                                    f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

#         post_flow   = (flow_list[-POST_LYING_WINDOW:]
#                        if len(flow_list) >= POST_LYING_WINDOW else flow_list)
#         still_ratio = sum(1 for f in post_flow if f < FLOW_STILL_THRESH) / max(len(post_flow), 1)
#         if still_ratio >= 0.35:
#             score += 1; notes.append(f"still={still_ratio:.0%}")

#         reason = f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
#         if score >= FALL_SCORE_NEEDED:
#             return True, score, f"FALL:{reason}"
#         return False, score, f"safe:{reason}"

#     # ── Main detection loop (v19 single-thread logic) ─────────────────────────
#     def run(self):
#         self.running = True

#         # Load YOLO models
#         try:
#             from ultralytics import YOLO
#             import torch as _torch
#             if FORCE_CUDA and not _torch.cuda.is_available():
#                 raise RuntimeError("CUDA not available — install CUDA PyTorch: "
#                                    "pip install torch --index-url https://download.pytorch.org/whl/cu121")
#             device = "cuda" if _torch.cuda.is_available() else "cpu"
#             if device == "cuda":
#                 gpu_name = _torch.cuda.get_device_name(0)
#                 vram_gb  = _torch.cuda.get_device_properties(0).total_memory / 1e9
#                 print(f"[MonitoringStream] GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)")
#             else:
#                 print("[MonitoringStream] WARNING: CUDA not found — running on CPU (slow!)")
#                 print("[MonitoringStream] Fix: pip install torch --index-url https://download.pytorch.org/whl/cu121")

#             print(f"[MonitoringStream] Device: {device} | YOLO every {YOLO_EVERY_N} frame(s) | imgsz={YOLO_IMGSZ}")
#             print("[MonitoringStream] Loading YOLO models...")
#             fall_model    = YOLO(FALL_MODEL_PATH).to(device)
#             posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

#             # FP16: pass half=True per-call (correct Ultralytics API).
#             # Never call model.half() directly — causes dtype mismatch on some layers.
#             use_half = (device == "cuda")
#             if use_half:
#                 print("[MonitoringStream] FP16 inference enabled.")

#             # Persistent thread pool — both YOLO models run IN PARALLEL each frame
#             # Worker count = 2 (one per model). Created once, reused every frame.
#             yolo_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="YOLO")
#             print("[MonitoringStream] Parallel YOLO executor ready (2 workers).")

#             # Warmup BOTH models in parallel (same as runtime)
#             import numpy as _np
#             _dummy = _np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=_np.uint8)
#             _wf = yolo_pool.submit(fall_model,    _dummy, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
#             _wp = yolo_pool.submit(posture_model, _dummy, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
#             _wf.result(); _wp.result()
#             print("[MonitoringStream] Models warmed up (parallel). Ready.")

#             # Init GPU optical flow (silently falls back to CPU if cv2.cuda absent)
#             _init_cuda_flow()
#         except Exception as e:
#             print(f"[MonitoringStream] Model load error: {e}")
#             if self.fall_cb:
#                 self.fall_cb(0, str(e), "error", "")
#             return

#         # Start video session (same as v19)
#         video_session = None
#         try:
#             from video_recorder import VideoSession
#             video_session = VideoSession(
#                 patient_name    = self.patient_name,
#                 fps             = 20.0,
#                 frame_size      = (FRAME_W, FRAME_H),
#                 save_continuous = True,
#             )
#             video_session.start()
#             print(f"[MonitoringStream] Recording to data/patients/{self.patient_name}/videos/")
#         except Exception as e:
#             print(f"[MonitoringStream] VideoSession failed (no recording): {e}")

#         # Open video / camera
#         src = (int(self.video_path)
#                if str(self.video_path).isdigit()
#                else self.video_path)
#         cap = cv2.VideoCapture(src)
#         if not cap.isOpened():
#             print("[MonitoringStream] Cannot open video source.")
#             if video_session: video_session.stop()
#             return

#         # ── State variables (identical to v19) ───────────────────────────────
#         posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
#         flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
#         drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
#         area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
#         aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
#         raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
#         raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

#         prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
#         lying_consec = standing_consec = fall_model_consec = 0
#         frames_since_lying = 0; episode_analyzed = False
#         last_valid_posture = "none"; posture_persist_counter = 0
#         fall_latch_ctr = recovery_latch_ctr = 0
#         final_state = "STARTING"; fall_reason = ""
#         post_fall_lying = False; pre_lying_posture = "none"
#         episode_locked = False; last_upright_posture = "none"
#         sitting_consec_pre = 0; safe_lying_locked = False
#         last_known_posture = "none"
#         frame_count = 0
#         _last_dets     = []     # cached YOLO detections for skipped frames
#         _last_fall_det = False  # cached fall model result

#         print("[MonitoringStream] Detection loop started.")

#         # ── Main loop — identical structure to v19 ────────────────────────────
#         while self.running:
#             ret, frame = cap.read()
#             if not ret:
#                 # Loop video file back to start
#                 cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
#                 # Reset per-frame motion state so first frame of next loop
#                 # doesn't get false drop/area spikes from stale values
#                 prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
#                 continue

#             frame_count += 1
#             frame     = cv2.resize(frame, (FRAME_W, FRAME_H))
#             gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

#             # ── PARALLEL YOLO INFERENCE ───────────────────────────────────────
#             # Both models submit to the GPU simultaneously via yolo_pool.
#             # GPU scheduler runs them concurrently — ~50% faster than sequential.
#             # Frame skipping still available: increase YOLO_EVERY_N if needed.
#             run_yolo = (frame_count % YOLO_EVERY_N == 0)

#             fall_detected  = False
#             all_detections = []

#             if run_yolo:
#                 # Submit both models to thread pool — they run on GPU in parallel
#                 fut_fall    = yolo_pool.submit(
#                     fall_model, frame,
#                     conf=0.5, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
#                 fut_posture = yolo_pool.submit(
#                     posture_model, frame,
#                     conf=0.45, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)

#                 # ── Process fall model results ────────────────────────────────
#                 for r in fut_fall.result():
#                     for box in r.boxes:
#                         cls   = int(box.cls[0])
#                         label = fall_model.names[cls]
#                         conf  = float(box.conf[0])
#                         x1, y1, x2, y2 = map(int, box.xyxy[0])
#                         if label.lower() == "fall":
#                             fall_detected = True
#                         cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,180), 2)
#                         cv2.putText(frame, f"{label} {conf:.2f}",
#                                     (x1, max(y1-8, 70)),
#                                     cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,0,180), 1)
#                 _last_fall_det = fall_detected

#                 # ── Process posture model results ─────────────────────────────
#                 for r in fut_posture.result():
#                     for box in r.boxes:
#                         conf  = float(box.conf[0])
#                         cls   = int(box.cls[0])
#                         label = posture_model.names[cls].lower()
#                         x1, y1, x2, y2 = map(int, box.xyxy[0])
#                         all_detections.append((label, (x1,y1,x2,y2), conf))
#                         ar     = get_aspect_ratio((x1,y1,x2,y2))
#                         reject = (label == "lying" and ar > LYING_ASPECT_RATIO_MAX)
#                         color  = (120,120,120) if reject else (0,180,0)
#                         cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
#                         cv2.putText(frame, f"{label}{'[X]' if reject else ''} {conf:.2f}",
#                                     (x1, max(y1-26, 70)),
#                                     cv2.FONT_HERSHEY_SIMPLEX, 0.38,
#                                     (100,100,100) if reject else (0,180,0), 1)
#                 _last_dets = all_detections

#             else:
#                 # Reuse cached results — redraw last known boxes
#                 fall_detected  = _last_fall_det
#                 all_detections = _last_dets
#                 for (lbl, (x1,y1,x2,y2), cf) in _last_dets:
#                     ar  = get_aspect_ratio((x1,y1,x2,y2))
#                     col = (0,0,180) if lbl == "fall" else (
#                           (120,120,120) if lbl == "lying" and ar > LYING_ASPECT_RATIO_MAX
#                           else (0,180,0))
#                     cv2.rectangle(frame, (x1,y1), (x2,y2), col, 2)

#             fall_model_consec = fall_model_consec + 1 if fall_detected else 0

#             raw_posture_label, person_box = select_main_subject(all_detections)
#             active_zone  = person_zone(person_box, self.zones)
#             on_safe_zone = active_zone is not None

#             if raw_posture_label != "none":
#                 last_valid_posture      = raw_posture_label
#                 posture_persist_counter = 0
#                 posture_label           = raw_posture_label
#             else:
#                 posture_persist_counter += 1
#                 posture_label = (last_valid_posture
#                                  if posture_persist_counter <= POSTURE_PERSIST_FRAMES
#                                  else "none")
#             if posture_label != "none":
#                 last_known_posture = posture_label

#             flow_energy = compute_flow_energy(gray_curr, prev_gray, person_box)
#             flow_history.append(flow_energy)
#             prev_gray = gray_curr.copy()

#             drop_velocity = 0.0; area_change = 0.0
#             curr_ar = prev_aspect_ratio if prev_aspect_ratio else 1.5
#             if person_box is not None:
#                 x1, y1, x2, y2 = person_box
#                 cy       = (y1 + y2) / 2.0
#                 curr_ar  = get_aspect_ratio(person_box)
#                 curr_area = get_bbox_area(person_box)
#                 if prev_center_y  is not None: drop_velocity = cy - prev_center_y
#                 if prev_bbox_area is not None and prev_bbox_area > 0:
#                     area_change = abs(curr_area - prev_bbox_area) / prev_bbox_area
#                 prev_center_y  = cy
#                 prev_bbox_area = curr_area
#                 prev_aspect_ratio = curr_ar

#             drop_history.append(max(drop_velocity, 0.0))
#             area_change_history.append(area_change)
#             aspect_ratio_history.append(curr_ar)
#             raw_drop_history.append(max(drop_velocity, 0.0))
#             raw_area_history.append(area_change)

#             if fall_latch_ctr == 0:
#                 posture_history.append(posture_label)

#             # Track pre-lying posture (same as v19)
#             if lying_consec < LYING_CONFIRM_FRAMES:
#                 if posture_label == "standing":
#                     last_upright_posture = "standing"; sitting_consec_pre = 0
#                 elif posture_label == "sitting":
#                     sitting_consec_pre += 1
#                     if sitting_consec_pre >= SITTING_CONFIRM_FOR_PREPOSTURE:
#                         last_upright_posture = "sitting"
#                 else:
#                     sitting_consec_pre = 0

#             if posture_label == "lying":
#                 lying_consec   += 1; standing_consec = 0
#                 if lying_consec == LYING_CONFIRM_FRAMES and not episode_locked:
#                     pre_lying_posture = last_upright_posture; episode_locked = True
#                 if on_safe_zone and lying_consec >= LYING_CONFIRM_FRAMES and not safe_lying_locked:
#                     safe_lying_locked = True
#                     fall_reason = f"blocked:person_on_{active_zone['type']}(safe_zone)"
#             elif posture_label in ("standing", "sitting"):
#                 standing_consec += 1
#                 if standing_consec >= STANDING_CONFIRM_FRAMES:
#                     lying_consec      = 0; frames_since_lying = 0
#                     episode_analyzed  = False; fall_reason = ""
#                     post_fall_lying   = False; episode_locked = False
#                     pre_lying_posture = "none"; sitting_consec_pre = 0
#                     safe_lying_locked = False
#             else:
#                 standing_consec = 0

#             if lying_consec >= LYING_CONFIRM_FRAMES:
#                 frames_since_lying += 1
#             else:
#                 if frames_since_lying > 0:
#                     post_fall_lying   = False; episode_analyzed  = False
#                     episode_locked    = False; pre_lying_posture  = "none"
#                     sitting_consec_pre = 0;    safe_lying_locked  = False
#                 frames_since_lying = 0

#             current_score = 0
#             in_analysis_window = ANALYSIS_START <= frames_since_lying <= ANALYSIS_END

#             # ── Fall analysis trigger 1: analysis window (same as v19) ────────
#             if (in_analysis_window and not episode_analyzed
#                     and not safe_lying_locked and fall_latch_ctr == 0):
#                 is_fall, current_score, fall_reason = self._analyze_fall(
#                     fall_model_consec, aspect_ratio_history,
#                     flow_history, drop_history, area_change_history,
#                     posture_history, raw_drop_history, raw_area_history,
#                     pre_posture=pre_lying_posture, current_person_box=person_box)
#                 if is_fall:
#                     fall_latch_ctr   = FALL_LATCH_FRAMES
#                     episode_analyzed = True; post_fall_lying = True
#                     clip_path = ""
#                     if video_session:
#                         try: clip_path = str(video_session.on_fall())
#                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
#                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
#                     if self.fall_cb:
#                         threading.Thread(
#                             target=self.fall_cb,
#                             args=(current_score, fall_reason, posture_label, clip_path),
#                             daemon=True).start()
#                 else:
#                     safe_lying_locked = True

#             # ── Fall analysis trigger 2: fall model + lying (same as v19) ─────
#             if (fall_detected and fall_model_consec >= FALL_MODEL_CONSEC
#                     and lying_consec >= LYING_CONFIRM_FRAMES
#                     and not safe_lying_locked and fall_latch_ctr == 0
#                     and not episode_analyzed):
#                 is_fall, current_score, fall_reason = self._analyze_fall(
#                     fall_model_consec, aspect_ratio_history,
#                     flow_history, drop_history, area_change_history,
#                     posture_history, raw_drop_history, raw_area_history,
#                     pre_posture=pre_lying_posture, current_person_box=person_box)
#                 if is_fall:
#                     fall_latch_ctr   = FALL_LATCH_FRAMES
#                     episode_analyzed = True; post_fall_lying = True
#                     clip_path = ""
#                     if video_session:
#                         try: clip_path = str(video_session.on_fall())
#                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
#                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
#                     if self.fall_cb:
#                         threading.Thread(
#                             target=self.fall_cb,
#                             args=(current_score, fall_reason, posture_label, clip_path),
#                             daemon=True).start()
#                 else:
#                     safe_lying_locked = True

#             # ── Fall analysis trigger 3: fall model + unknown posture (v19) ───
#             if (posture_label == "none" and fall_model_consec >= FALL_MODEL_CONSEC
#                     and not safe_lying_locked and fall_latch_ctr == 0
#                     and not episode_analyzed
#                     and last_known_posture in ("standing", "sitting")
#                     and not person_in_safe_zone(person_box, self.zones)):
#                 is_fall, current_score, fall_reason = self._analyze_fall(
#                     fall_model_consec, aspect_ratio_history,
#                     flow_history, drop_history, area_change_history,
#                     posture_history, raw_drop_history, raw_area_history,
#                     pre_posture=last_known_posture, current_person_box=person_box)
#                 if is_fall:
#                     fall_latch_ctr   = FALL_LATCH_FRAMES
#                     episode_analyzed = True; post_fall_lying = True
#                     fall_reason      = f"[FM-UNKNOWN] {fall_reason}"
#                     clip_path = ""
#                     if video_session:
#                         try: clip_path = str(video_session.on_fall())
#                         except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
#                     print(f"[FALL] {fall_reason} | clip: {clip_path}")
#                     if self.fall_cb:
#                         threading.Thread(
#                             target=self.fall_cb,
#                             args=(current_score, fall_reason, posture_label, clip_path),
#                             daemon=True).start()

#             # ── Safe-zone latch cancel (same as v19) ──────────────────────────
#             if fall_latch_ctr > 0 and on_safe_zone:
#                 fall_latch_ctr    = 0; recovery_latch_ctr = 0
#                 post_fall_lying   = False; safe_lying_locked = True
#                 fall_reason       = "blocked:entered_safe_zone_during_latch"
#                 print("[BLOCK-B] Latch cancelled — person in safe zone")

#             # ── State machine (same as v19) ───────────────────────────────────
#             if fall_latch_ctr > 0:
#                 fall_latch_ctr -= 1; final_state = "FALL"
#                 if fall_latch_ctr == 0: recovery_latch_ctr = RECOVERY_LATCH_FRAMES
#             elif recovery_latch_ctr > 0:
#                 recovery_latch_ctr -= 1; final_state = "RECOVERY"
#             else:
#                 if posture_label == "lying":
#                     if post_fall_lying: final_state = "LYING (POST-FALL)"
#                     elif on_safe_zone:  final_state = f"LYING (ON {active_zone['type'].upper()})"
#                     else:               final_state = "LYING (SAFE)"
#                 elif posture_label == "standing": final_state = "STANDING"
#                 elif posture_label == "sitting":  final_state = "SITTING"
#                 else:                              final_state = "UNKNOWN"

#             self.state = final_state
#             self.score = current_score

#             # ── Draw overlays (same as v19) ───────────────────────────────────
#             draw_all_zones(frame, self.zones, active_zone)
#             draw_banner(frame, final_state)
#             draw_signals(frame, flow_energy, area_change,
#                          max(drop_velocity, 0), current_score, FALL_SCORE_NEEDED)
#             is_saving = (video_session.clipper.is_saving
#                          if video_session and hasattr(video_session, 'clipper') else False)
#             draw_rec_indicator(frame, is_saving, frame_count)

#             H, W = frame.shape[:2]
#             if on_safe_zone:
#                 col = ZONE_COLORS[active_zone["type"]]
#                 draw_pill_label(frame, f"ON {active_zone['type'].upper()}",
#                                 W-108, 88, col, scale=0.40)
#             if safe_lying_locked:
#                 draw_pill_label(frame, "SAFE-LOCK", W-100, 112, (30,130,60), scale=0.35)

#             selected_ar = get_aspect_ratio(person_box) if person_box else 0.0
#             dbg = (f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
#                    f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
#                    f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
#                    f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
#                    f"zone:{active_zone['type'] if active_zone else 'none'}  "
#                    f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
#             cv2.putText(frame, dbg, (6, H-6),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.27, (130,130,155), 1)
#             if fall_reason:
#                 cv2.putText(frame, fall_reason, (6, H-18),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.28, (55,195,255), 1)

#             # Feed the FULLY DRAWN frame to recorder (same as v19 final version)
#             if video_session:
#                 video_session.feed(frame)

#             # Write annotated frame to GUI buffer (RGB for tkinter)
#             frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             with self._lock:
#                 self.latest_frame = (frame_rgb, final_state, current_score)

#         # ── Cleanup ───────────────────────────────────────────────────────────
#         try:
#             yolo_pool.shutdown(wait=False)
#         except Exception:
#             pass
#         cap.release()
#         if video_session:
#             video_session.stop()
#         print("[MonitoringStream] Stopped.")

















"""
LEO — Monitoring Stream (GPU-Accelerated, v19 Logic)
=====================================================

Full GPU acceleration:
  • Both YOLO models run IN PARALLEL on GPU via ThreadPoolExecutor
    (cuts YOLO time roughly in half vs sequential)
  • FP16 (half precision) inference — 2x faster, half the VRAM usage
  • GPU optical flow via cv2.cuda (falls back to CPU if unavailable)
  • imgsz=640 — full resolution since GPU can handle it
  • Warmup inference so the first real frame is not slow

Detection logic is identical to the working standalone v19 script.
"""

import cv2
import numpy as np
import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from pathlib import Path

BASE_DIR = Path(__file__).parent

VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
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

FRAME_W, FRAME_H = 640, 480

# ── GPU speed config ──────────────────────────────────────────────────────────
# Both YOLO models run IN PARALLEL on the GPU — cuts YOLO time ~50%.
# MX550 (2GB VRAM) handles both at FP16 with imgsz=640 fine.
YOLO_EVERY_N = 1     # run YOLO on every frame (GPU is fast enough)
YOLO_IMGSZ   = 640   # full resolution — GPU handles it; better accuracy
FORCE_CUDA   = False # set True to crash loudly if GPU is missing

# ── Detection parameters (identical to v19) ───────────────────────────────────
LYING_CONFIRM_FRAMES           = 8
STANDING_CONFIRM_FRAMES        = 3
POSTURE_PERSIST_FRAMES         = 8
LYING_ASPECT_RATIO_MAX         = 1.2
SITTING_CONFIRM_FOR_PREPOSTURE = 3

DROP_FAST_PX       = 7
DROP_ANY_PX        = 3
AREA_CHANGE_HIGH   = 0.12
AREA_CHANGE_ANY    = 0.05
SUDDEN_DROP_THRESH = 7.0
SUDDEN_AREA_THRESH = 0.20
FLOW_SPIKE_THRESH  = 1.4
FLOW_ANY_THRESH    = 0.7
FLOW_STILL_THRESH  = 0.9
ASPECT_DROP_THRESH = 0.18
FALL_MODEL_CONSEC  = 2
FALL_SCORE_NEEDED  = 4
ANALYSIS_START     = 4
ANALYSIS_END       = 40
PRE_LYING_WINDOW   = 25
POST_LYING_WINDOW  = 10
UPRIGHT_LOOKBACK   = 55
MIN_UPRIGHT_FRAMES = 15
FALL_LATCH_FRAMES     = 65
RECOVERY_LATCH_FRAMES = 25

# ── Colors (identical to v19) ─────────────────────────────────────────────────
ZONE_COLORS = {
    "bed":  (0, 200, 255),
    "sofa": (0, 140, 255),
}

STATE_META = {
    "FALL":              ((0,   0,   220), "!"),
    "LYING (POST-FALL)": ((0,   60,  190), "!"),
    "LYING (SAFE)":      ((140, 80,  0),   "~"),
    "LYING (ON BED)":    ((0,   110, 150), "~"),
    "LYING (ON SOFA)":   ((0,   90,  165), "~"),
    "STANDING":          ((0,   160, 30),  "^"),
    "SITTING":           ((0,   130, 120), "s"),
    "RECOVERY":          ((130, 0,   160), "r"),
    "UNKNOWN":           ((75,  75,  75),  "?"),
    "STARTING":          ((60,  60,  60),  "."),
}


# ── Helpers (identical to v19) ────────────────────────────────────────────────

def get_aspect_ratio(box):
    x1, y1, x2, y2 = box
    return max(y2 - y1, 1) / max(x2 - x1, 1)

def get_bbox_area(box):
    x1, y1, x2, y2 = box
    return max(x2 - x1, 0) * max(y2 - y1, 0)

# Check once at import time whether cv2.cuda optical flow is available
_CUDA_FLOW = None
def _init_cuda_flow():
    global _CUDA_FLOW
    try:
        _CUDA_FLOW = cv2.cuda.FarnebackOpticalFlow.create(
            numLevels=2, pyrScale=0.5, fastPyramids=False,
            winSize=12, numIters=2, polyN=5, polySigma=1.1, flags=0)
        print("[MonitoringStream] GPU optical flow enabled (cv2.cuda).")
    except Exception:
        _CUDA_FLOW = None
        print("[MonitoringStream] GPU optical flow unavailable — using CPU Farneback.")

def compute_flow_energy(gray_curr, gray_prev, box):
    if gray_prev is None or box is None: return 0.0
    x1 = max(int(box[0]), 0); y1 = max(int(box[1]), 0)
    x2 = min(int(box[2]), gray_curr.shape[1])
    y2 = min(int(box[3]), gray_curr.shape[0])
    if x2 <= x1 + 4 or y2 <= y1 + 4: return 0.0
    roi_curr = gray_curr[y1:y2, x1:x2]
    roi_prev = gray_prev[y1:y2, x1:x2]
    if _CUDA_FLOW is not None:
        try:
            g_curr = cv2.cuda_GpuMat(); g_curr.upload(roi_curr)
            g_prev = cv2.cuda_GpuMat(); g_prev.upload(roi_prev)
            g_flow = _CUDA_FLOW.calc(g_prev, g_curr, None)
            flow   = g_flow.download()
            return float(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))
        except Exception:
            pass  # fall through to CPU
    flow = cv2.calcOpticalFlowFarneback(
        roi_prev, roi_curr, None,
        pyr_scale=0.5, levels=2, winsize=12, iterations=2,
        poly_n=5, poly_sigma=1.1, flags=0)
    return float(np.mean(np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)))

def select_main_subject(detections):
    if not detections: return "none", None
    best_label, best_box, best_area, best_conf = "none", None, -1, -1
    for (label, box, conf) in detections:
        area = get_bbox_area(box); ar = get_aspect_ratio(box)
        if label == "lying" and ar > LYING_ASPECT_RATIO_MAX: continue
        if area > best_area or (area == best_area and conf > best_conf):
            best_area, best_conf = area, conf
            best_label, best_box = label, box
    return best_label, best_box

def person_zone(person_box, zones):
    if person_box is None or not zones: return None
    cx = (person_box[0] + person_box[2]) / 2
    cy = (person_box[1] + person_box[3]) / 2
    for z in zones:
        x1, y1, x2, y2 = z["box"]
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return z
    return None

def person_in_safe_zone(person_box, zones):
    return person_zone(person_box, zones) is not None


# ── Draw helpers (identical to v19) ──────────────────────────────────────────

def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
    cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255,255,255), 1, cv2.LINE_AA)

def draw_zone_on_frame(img, z, is_active=False):
    x1, y1, x2, y2 = z["box"]
    col   = ZONE_COLORS[z["type"]]
    alpha = 0.22 if is_active else 0.12
    ov    = img.copy()
    cv2.rectangle(ov, (x1,y1), (x2,y2), col, -1)
    cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)
    cv2.rectangle(img, (x1,y1), (x2,y2), col, 2 if is_active else 1, cv2.LINE_AA)
    label = z["type"].upper() + (" *" if is_active else "")
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    pad = 4
    bov = img.copy()
    cv2.rectangle(bov, (x1, y1), (x1+tw+pad*2, y1+th+pad*2), col, -1)
    cv2.addWeighted(bov, 0.80, img, 0.20, 0, img)
    cv2.putText(img, label, (x1+pad, y1+th+pad),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,255), 1, cv2.LINE_AA)

def draw_all_zones(img, zones, active_zone=None):
    for z in zones:
        draw_zone_on_frame(img, z, is_active=(z is active_zone))

def draw_banner(frame, state):
    col = STATE_META.get(state, ((100,100,100),"?"))[0]
    W = frame.shape[1]
    ov = frame.copy()
    cv2.rectangle(ov, (0,0), (W,58), col, -1)
    cv2.addWeighted(ov, 0.55, frame, 0.45, 0, frame)
    cv2.rectangle(frame, (0,0), (5,58), col, -1)
    cv2.line(frame, (0,58), (W,58), col, 1)
    cv2.putText(frame, f"STATE:  {state}",
                (16,40), cv2.FONT_HERSHEY_SIMPLEX,
                0.95, (255,255,255), 2, cv2.LINE_AA)

def draw_signals(frame, flow_val, area_chg, drop_vel, score, fall_score_needed):
    H, W = frame.shape[:2]
    px, py = 6, H-90; pw = 192
    ov = frame.copy()
    cv2.rectangle(ov, (px-2,py-2), (px+pw,py+80), (12,12,18), -1)
    cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
    cv2.rectangle(frame, (px-2,py-2), (px+pw,py+80), (50,50,70), 1)
    sigs = [("FLOW", flow_val, 5.0,  (0,200,255)),
            ("AREA", area_chg, 0.3,  (0,180,120)),
            ("DROP", drop_vel, 20.0, (60,100,255)),
            ("SCOR", score,    fall_score_needed*1.5, (0,60,255))]
    bx = px+44; bmax = pw-52
    for i, (lbl, val, mx, col) in enumerate(sigs):
        y  = py + 6 + i*18
        bw = int(min(val / max(mx, 0.001), 1.0) * bmax)
        cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (28,28,40), -1)
        if bw > 0: cv2.rectangle(frame, (bx,y+2), (bx+bw,y+12), col, -1)
        cv2.rectangle(frame, (bx,y+2), (bx+bmax,y+12), (55,55,75), 1)
        cv2.putText(frame, lbl, (px,y+12), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140,140,165), 1)
        cv2.putText(frame, f"{val:.1f}", (bx+bmax+3,y+12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.27, (170,170,195), 1)

def draw_rec_indicator(frame, is_saving_clip, tick):
    H, W = frame.shape[:2]
    pulse = int(180 + 75 * math.sin(tick * 0.2))
    cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
    cv2.putText(frame, "REC", (W-45, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
    if is_saving_clip:
        badge = "  SAVING FALL CLIP  "
        (bw,bh), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
        bx = W - bw - 60
        cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
        cv2.putText(frame, badge, (bx, 30+bh+2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════════════════════════
#  MonitoringStream — single-threaded, v19 detection logic
# ══════════════════════════════════════════════════════════════════════════════
class MonitoringStream(threading.Thread):
    """
    Runs in its own thread but detection is synchronous inside that thread —
    exactly like v19.  YOLO + state machine + drawing all happen in one loop,
    so every displayed frame has correct, current detection boxes.

    GUI reads self.latest_frame  (thread-safe via self._lock).
    fall_cb is called when a fall is confirmed.
    """

    def __init__(self, patient_name, frame_cb, fall_cb=None,
                 zones=None, video_path=VIDEO_PATH):
        super().__init__(daemon=True, name="MonitoringStream")
        self.patient_name = patient_name
        self.frame_cb     = frame_cb    # unused — GUI reads latest_frame directly
        self.fall_cb      = fall_cb
        self.video_path   = video_path
        self.running      = False
        self.state        = "STARTING"
        self.score        = 0
        self.latest_frame = None
        self._lock        = threading.Lock()

        # Load zones
        self.zones = zones if zones is not None else self._load_zones()

    def _load_zones(self):
        zf = BASE_DIR / "data" / "patients" / self.patient_name / "safe_zones.json"
        if not zf.exists():
            return []
        try:
            with open(zf) as f:
                data = json.load(f)
            zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
            print(f"[MonitoringStream] Loaded {len(zones)} zone(s)")
            return zones
        except Exception as e:
            print(f"[MonitoringStream] Zone load error: {e}")
            return []

    def stop(self):
        self.running = False

    # ── Fall analysis (identical to v19) ─────────────────────────────────────
    def _analyze_fall(self, fmc, ar_hist,
                      flow_history, drop_history, area_change_history,
                      posture_history, raw_drop_history, raw_area_history,
                      pre_posture="none", current_person_box=None):

        if (current_person_box is not None
                and person_in_safe_zone(current_person_box, self.zones)):
            return False, 0, "blocked:person_in_safe_zone"

        flow_list  = list(flow_history)
        drop_list  = list(drop_history)
        area_list  = list(area_change_history)
        post_list  = list(posture_history)
        ar_list    = list(ar_hist) if ar_hist else []
        raw_drops  = list(raw_drop_history)
        raw_areas  = list(raw_area_history)
        score = 0; notes = []

        if pre_posture == "sitting":
            if fmc >= FALL_MODEL_CONSEC:
                notes.append("sitting_override_by_fallmodel")
            else:
                return False, 0, "blocked:sitting_to_lying(sofa/bed)"

        upright_count = sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
                            if p in ("standing", "sitting"))
        if upright_count < MIN_UPRIGHT_FRAMES:
            return False, 0, f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

        has_sudden_drop = any(d >= SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
        has_sudden_area = any(a >= SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
        if not has_sudden_drop and not has_sudden_area and fmc == 0:
            return False, 0, "blocked:gradual_transition(no_spike,no_fallmodel)"

        pre_drops   = drop_list[-PRE_LYING_WINDOW:] if drop_list else []
        max_drop    = max(pre_drops) if pre_drops else 0.0
        if   max_drop >= DROP_FAST_PX: score += 2; notes.append(f"fast_drop={max_drop:.0f}")
        elif max_drop >= DROP_ANY_PX:  score += 1; notes.append(f"drop={max_drop:.0f}")

        pre_area      = area_list[-PRE_LYING_WINDOW:] if area_list else []
        max_area_chg  = max(pre_area) if pre_area else 0.0
        if   max_area_chg >= AREA_CHANGE_HIGH: score += 2; notes.append(f"area_chg={max_area_chg:.2f}")
        elif max_area_chg >= AREA_CHANGE_ANY:  score += 1; notes.append(f"area_any={max_area_chg:.2f}")

        n = len(flow_list)
        pre_flow     = flow_list[max(0, n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
                                  max(0, n-POST_LYING_WINDOW)]
        max_pre_flow = max(pre_flow) if pre_flow else 0.0
        if   max_pre_flow >= FLOW_SPIKE_THRESH: score += 2; notes.append(f"flow_spike={max_pre_flow:.2f}")
        elif max_pre_flow >= FLOW_ANY_THRESH:   score += 1; notes.append(f"flow={max_pre_flow:.2f}")

        if len(ar_list) >= 4:
            ar_before = float(np.mean(ar_list[:max(1, len(ar_list)-PRE_LYING_WINDOW)]))
            ar_after  = float(np.mean(ar_list[-3:]))
            ar_drop   = ar_before - ar_after
            if ar_drop >= ASPECT_DROP_THRESH:
                score += 2; notes.append(f"aspect_flip={ar_drop:.2f}")

        if fmc >= FALL_MODEL_CONSEC:
            score += 3; notes.append(f"fall_model={fmc}f")

        if (max_drop < DROP_ANY_PX and max_area_chg < AREA_CHANGE_ANY
                and max_pre_flow < FLOW_ANY_THRESH):
            return False, score, (f"blocked:no_motion(d={max_drop:.1f} "
                                   f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

        post_flow   = (flow_list[-POST_LYING_WINDOW:]
                       if len(flow_list) >= POST_LYING_WINDOW else flow_list)
        still_ratio = sum(1 for f in post_flow if f < FLOW_STILL_THRESH) / max(len(post_flow), 1)
        if still_ratio >= 0.35:
            score += 1; notes.append(f"still={still_ratio:.0%}")

        reason = f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
        if score >= FALL_SCORE_NEEDED:
            return True, score, f"FALL:{reason}"
        return False, score, f"safe:{reason}"

    # ── Main detection loop (v19 single-thread logic) ─────────────────────────
    def run(self):
        self.running = True

        # Load YOLO models
        try:
            from ultralytics import YOLO
            import torch as _torch
            if FORCE_CUDA and not _torch.cuda.is_available():
                raise RuntimeError("CUDA not available — install CUDA PyTorch: "
                                   "pip install torch --index-url https://download.pytorch.org/whl/cu121")
            device = "cuda" if _torch.cuda.is_available() else "cpu"
            if device == "cuda":
                gpu_name = _torch.cuda.get_device_name(0)
                vram_gb  = _torch.cuda.get_device_properties(0).total_memory / 1e9
                print(f"[MonitoringStream] GPU: {gpu_name} ({vram_gb:.1f} GB VRAM)")
            else:
                print("[MonitoringStream] WARNING: CUDA not found — running on CPU (slow!)")
                print("[MonitoringStream] Fix: pip install torch --index-url https://download.pytorch.org/whl/cu121")

            print(f"[MonitoringStream] Device: {device} | YOLO every {YOLO_EVERY_N} frame(s) | imgsz={YOLO_IMGSZ}")
            print("[MonitoringStream] Loading YOLO models...")
            fall_model    = YOLO(FALL_MODEL_PATH).to(device)
            posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

            # FP16: pass half=True per-call (correct Ultralytics API).
            # Never call model.half() directly — causes dtype mismatch on some layers.
            use_half = (device == "cuda")
            if use_half:
                print("[MonitoringStream] FP16 inference enabled.")

            # Persistent thread pool — both YOLO models run IN PARALLEL each frame
            # Worker count = 2 (one per model). Created once, reused every frame.
            yolo_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="YOLO")
            print("[MonitoringStream] Parallel YOLO executor ready (2 workers).")

            # Warmup BOTH models in parallel (same as runtime)
            import numpy as _np
            _dummy = _np.zeros((YOLO_IMGSZ, YOLO_IMGSZ, 3), dtype=_np.uint8)
            _wf = yolo_pool.submit(fall_model,    _dummy, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
            _wp = yolo_pool.submit(posture_model, _dummy, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
            _wf.result(); _wp.result()
            print("[MonitoringStream] Models warmed up (parallel). Ready.")

            # Init GPU optical flow (silently falls back to CPU if cv2.cuda absent)
            _init_cuda_flow()
        except Exception as e:
            print(f"[MonitoringStream] Model load error: {e}")
            if self.fall_cb:
                self.fall_cb(0, str(e), "error", "")
            return

        # Start video session (same as v19)
        video_session = None
        try:
            from video_recorder import VideoSession
            video_session = VideoSession(
                patient_name    = self.patient_name,
                fps             = 20.0,
                frame_size      = (FRAME_W, FRAME_H),
                save_continuous = True,
            )
            video_session.start()
            print(f"[MonitoringStream] Recording to data/patients/{self.patient_name}/videos/")
        except Exception as e:
            print(f"[MonitoringStream] VideoSession failed (no recording): {e}")

        # Open video / camera
        src = (int(self.video_path)
               if str(self.video_path).isdigit()
               else self.video_path)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            print("[MonitoringStream] Cannot open video source.")
            if video_session: video_session.stop()
            return

        # ── State variables (identical to v19) ───────────────────────────────
        posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
        flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
        drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
        area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
        aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
        raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
        raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

        prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
        lying_consec = standing_consec = fall_model_consec = 0
        frames_since_lying = 0; episode_analyzed = False
        last_valid_posture = "none"; posture_persist_counter = 0
        fall_latch_ctr = recovery_latch_ctr = 0
        final_state = "STARTING"; fall_reason = ""
        post_fall_lying = False; pre_lying_posture = "none"
        episode_locked = False; last_upright_posture = "none"
        sitting_consec_pre = 0; safe_lying_locked = False
        last_known_posture = "none"
        frame_count = 0
        _last_dets     = []     # cached YOLO detections for skipped frames
        _last_fall_det = False  # cached fall model result

        print("[MonitoringStream] Detection loop started.")

        # ── Main loop — identical structure to v19 ────────────────────────────
        while self.running:
            ret, frame = cap.read()
            if not ret:
                # Loop video file back to start
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                # Reset per-frame motion state so first frame of next loop
                # doesn't get false drop/area spikes from stale values
                prev_gray = prev_center_y = prev_bbox_area = prev_aspect_ratio = None
                continue

            frame_count += 1
            frame     = cv2.resize(frame, (FRAME_W, FRAME_H))
            gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # ── PARALLEL YOLO INFERENCE ───────────────────────────────────────
            # Both models submit to the GPU simultaneously via yolo_pool.
            # GPU scheduler runs them concurrently — ~50% faster than sequential.
            # Frame skipping still available: increase YOLO_EVERY_N if needed.
            run_yolo = (frame_count % YOLO_EVERY_N == 0)

            fall_detected  = False
            all_detections = []

            if run_yolo:
                # Submit both models to thread pool — they run on GPU in parallel
                fut_fall    = yolo_pool.submit(
                    fall_model, frame,
                    conf=0.5, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)
                fut_posture = yolo_pool.submit(
                    posture_model, frame,
                    conf=0.45, imgsz=YOLO_IMGSZ, half=use_half, verbose=False)

                # ── Process fall model results ────────────────────────────────
                for r in fut_fall.result():
                    for box in r.boxes:
                        cls   = int(box.cls[0])
                        label = fall_model.names[cls]
                        conf  = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        if label.lower() == "fall":
                            fall_detected = True
                        cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,180), 2)
                        cv2.putText(frame, f"{label} {conf:.2f}",
                                    (x1, max(y1-8, 70)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,0,180), 1)
                _last_fall_det = fall_detected

                # ── Process posture model results ─────────────────────────────
                for r in fut_posture.result():
                    for box in r.boxes:
                        conf  = float(box.conf[0])
                        cls   = int(box.cls[0])
                        label = posture_model.names[cls].lower()
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        all_detections.append((label, (x1,y1,x2,y2), conf))
                        ar     = get_aspect_ratio((x1,y1,x2,y2))
                        reject = (label == "lying" and ar > LYING_ASPECT_RATIO_MAX)
                        color  = (120,120,120) if reject else (0,180,0)
                        cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                        cv2.putText(frame, f"{label}{'[X]' if reject else ''} {conf:.2f}",
                                    (x1, max(y1-26, 70)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                                    (100,100,100) if reject else (0,180,0), 1)
                _last_dets = all_detections

            else:
                # Reuse cached results — redraw last known boxes
                fall_detected  = _last_fall_det
                all_detections = _last_dets
                for (lbl, (x1,y1,x2,y2), cf) in _last_dets:
                    ar  = get_aspect_ratio((x1,y1,x2,y2))
                    col = (0,0,180) if lbl == "fall" else (
                          (120,120,120) if lbl == "lying" and ar > LYING_ASPECT_RATIO_MAX
                          else (0,180,0))
                    cv2.rectangle(frame, (x1,y1), (x2,y2), col, 2)

            fall_model_consec = fall_model_consec + 1 if fall_detected else 0

            raw_posture_label, person_box = select_main_subject(all_detections)
            active_zone  = person_zone(person_box, self.zones)
            on_safe_zone = active_zone is not None

            if raw_posture_label != "none":
                last_valid_posture      = raw_posture_label
                posture_persist_counter = 0
                posture_label           = raw_posture_label
            else:
                posture_persist_counter += 1
                posture_label = (last_valid_posture
                                 if posture_persist_counter <= POSTURE_PERSIST_FRAMES
                                 else "none")
            if posture_label != "none":
                last_known_posture = posture_label

            flow_energy = compute_flow_energy(gray_curr, prev_gray, person_box)
            flow_history.append(flow_energy)
            prev_gray = gray_curr.copy()

            drop_velocity = 0.0; area_change = 0.0
            curr_ar = prev_aspect_ratio if prev_aspect_ratio else 1.5
            if person_box is not None:
                x1, y1, x2, y2 = person_box
                cy       = (y1 + y2) / 2.0
                curr_ar  = get_aspect_ratio(person_box)
                curr_area = get_bbox_area(person_box)
                if prev_center_y  is not None: drop_velocity = cy - prev_center_y
                if prev_bbox_area is not None and prev_bbox_area > 0:
                    area_change = abs(curr_area - prev_bbox_area) / prev_bbox_area
                prev_center_y  = cy
                prev_bbox_area = curr_area
                prev_aspect_ratio = curr_ar

            drop_history.append(max(drop_velocity, 0.0))
            area_change_history.append(area_change)
            aspect_ratio_history.append(curr_ar)
            raw_drop_history.append(max(drop_velocity, 0.0))
            raw_area_history.append(area_change)

            if fall_latch_ctr == 0:
                posture_history.append(posture_label)

            # Track pre-lying posture (same as v19)
            if lying_consec < LYING_CONFIRM_FRAMES:
                if posture_label == "standing":
                    last_upright_posture = "standing"; sitting_consec_pre = 0
                elif posture_label == "sitting":
                    sitting_consec_pre += 1
                    if sitting_consec_pre >= SITTING_CONFIRM_FOR_PREPOSTURE:
                        last_upright_posture = "sitting"
                else:
                    sitting_consec_pre = 0

            if posture_label == "lying":
                lying_consec   += 1; standing_consec = 0
                if lying_consec == LYING_CONFIRM_FRAMES and not episode_locked:
                    pre_lying_posture = last_upright_posture; episode_locked = True
                if on_safe_zone and lying_consec >= LYING_CONFIRM_FRAMES and not safe_lying_locked:
                    safe_lying_locked = True
                    fall_reason = f"blocked:person_on_{active_zone['type']}(safe_zone)"
            elif posture_label in ("standing", "sitting"):
                standing_consec += 1
                if standing_consec >= STANDING_CONFIRM_FRAMES:
                    lying_consec      = 0; frames_since_lying = 0
                    episode_analyzed  = False; fall_reason = ""
                    post_fall_lying   = False; episode_locked = False
                    pre_lying_posture = "none"; sitting_consec_pre = 0
                    safe_lying_locked = False
            else:
                standing_consec = 0

            if lying_consec >= LYING_CONFIRM_FRAMES:
                frames_since_lying += 1
            else:
                if frames_since_lying > 0:
                    post_fall_lying   = False; episode_analyzed  = False
                    episode_locked    = False; pre_lying_posture  = "none"
                    sitting_consec_pre = 0;    safe_lying_locked  = False
                frames_since_lying = 0

            current_score = 0
            in_analysis_window = ANALYSIS_START <= frames_since_lying <= ANALYSIS_END

            # ── Fall analysis trigger 1: analysis window (same as v19) ────────
            if (in_analysis_window and not episode_analyzed
                    and not safe_lying_locked and fall_latch_ctr == 0):
                is_fall, current_score, fall_reason = self._analyze_fall(
                    fall_model_consec, aspect_ratio_history,
                    flow_history, drop_history, area_change_history,
                    posture_history, raw_drop_history, raw_area_history,
                    pre_posture=pre_lying_posture, current_person_box=person_box)
                if is_fall:
                    fall_latch_ctr   = FALL_LATCH_FRAMES
                    episode_analyzed = True; post_fall_lying = True
                    clip_path = ""
                    if video_session:
                        try: clip_path = str(video_session.on_fall())
                        except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
                    print(f"[FALL] {fall_reason} | clip: {clip_path}")
                    if self.fall_cb:
                        threading.Thread(
                            target=self.fall_cb,
                            args=(current_score, fall_reason, posture_label, clip_path),
                            daemon=True).start()
                else:
                    safe_lying_locked = True

            # ── Fall analysis trigger 2: fall model + lying (same as v19) ─────
            if (fall_detected and fall_model_consec >= FALL_MODEL_CONSEC
                    and lying_consec >= LYING_CONFIRM_FRAMES
                    and not safe_lying_locked and fall_latch_ctr == 0
                    and not episode_analyzed):
                is_fall, current_score, fall_reason = self._analyze_fall(
                    fall_model_consec, aspect_ratio_history,
                    flow_history, drop_history, area_change_history,
                    posture_history, raw_drop_history, raw_area_history,
                    pre_posture=pre_lying_posture, current_person_box=person_box)
                if is_fall:
                    fall_latch_ctr   = FALL_LATCH_FRAMES
                    episode_analyzed = True; post_fall_lying = True
                    clip_path = ""
                    if video_session:
                        try: clip_path = str(video_session.on_fall())
                        except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
                    print(f"[FALL] {fall_reason} | clip: {clip_path}")
                    if self.fall_cb:
                        threading.Thread(
                            target=self.fall_cb,
                            args=(current_score, fall_reason, posture_label, clip_path),
                            daemon=True).start()
                else:
                    safe_lying_locked = True

            # ── Fall analysis trigger 3: fall model + unknown posture (v19) ───
            if (posture_label == "none" and fall_model_consec >= FALL_MODEL_CONSEC
                    and not safe_lying_locked and fall_latch_ctr == 0
                    and not episode_analyzed
                    and last_known_posture in ("standing", "sitting")
                    and not person_in_safe_zone(person_box, self.zones)):
                is_fall, current_score, fall_reason = self._analyze_fall(
                    fall_model_consec, aspect_ratio_history,
                    flow_history, drop_history, area_change_history,
                    posture_history, raw_drop_history, raw_area_history,
                    pre_posture=last_known_posture, current_person_box=person_box)
                if is_fall:
                    fall_latch_ctr   = FALL_LATCH_FRAMES
                    episode_analyzed = True; post_fall_lying = True
                    fall_reason      = f"[FM-UNKNOWN] {fall_reason}"
                    clip_path = ""
                    if video_session:
                        try: clip_path = str(video_session.on_fall())
                        except Exception as e: print(f"[MonitoringStream] Clip error: {e}")
                    print(f"[FALL] {fall_reason} | clip: {clip_path}")
                    if self.fall_cb:
                        threading.Thread(
                            target=self.fall_cb,
                            args=(current_score, fall_reason, posture_label, clip_path),
                            daemon=True).start()

            # ── Safe-zone latch cancel (same as v19) ──────────────────────────
            if fall_latch_ctr > 0 and on_safe_zone:
                fall_latch_ctr    = 0; recovery_latch_ctr = 0
                post_fall_lying   = False; safe_lying_locked = True
                fall_reason       = "blocked:entered_safe_zone_during_latch"
                print("[BLOCK-B] Latch cancelled — person in safe zone")

            # ── State machine (same as v19) ───────────────────────────────────
            if fall_latch_ctr > 0:
                fall_latch_ctr -= 1; final_state = "FALL"
                if fall_latch_ctr == 0: recovery_latch_ctr = RECOVERY_LATCH_FRAMES
            elif recovery_latch_ctr > 0:
                recovery_latch_ctr -= 1; final_state = "RECOVERY"
            else:
                if posture_label == "lying":
                    if post_fall_lying: final_state = "LYING (POST-FALL)"
                    elif on_safe_zone:  final_state = f"LYING (ON {active_zone['type'].upper()})"
                    else:               final_state = "LYING (SAFE)"
                elif posture_label == "standing": final_state = "STANDING"
                elif posture_label == "sitting":  final_state = "SITTING"
                else:                              final_state = "UNKNOWN"

            self.state = final_state
            self.score = current_score

            # ── Draw overlays (same as v19) ───────────────────────────────────
            draw_all_zones(frame, self.zones, active_zone)
            draw_banner(frame, final_state)
            draw_signals(frame, flow_energy, area_change,
                         max(drop_velocity, 0), current_score, FALL_SCORE_NEEDED)
            is_saving = (video_session.clipper.is_saving
                         if video_session and hasattr(video_session, 'clipper') else False)
            draw_rec_indicator(frame, is_saving, frame_count)

            H, W = frame.shape[:2]
            if on_safe_zone:
                col = ZONE_COLORS[active_zone["type"]]
                draw_pill_label(frame, f"ON {active_zone['type'].upper()}",
                                W-108, 88, col, scale=0.40)
            if safe_lying_locked:
                draw_pill_label(frame, "SAFE-LOCK", W-100, 112, (30,130,60), scale=0.35)

            selected_ar = get_aspect_ratio(person_box) if person_box else 0.0
            dbg = (f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
                   f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
                   f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
                   f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
                   f"zone:{active_zone['type'] if active_zone else 'none'}  "
                   f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
            cv2.putText(frame, dbg, (6, H-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.27, (130,130,155), 1)
            if fall_reason:
                cv2.putText(frame, fall_reason, (6, H-18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.28, (55,195,255), 1)

            # Feed the FULLY DRAWN frame to recorder (same as v19 final version)
            if video_session:
                video_session.feed(frame)

            # Write annotated frame to GUI buffer (RGB for tkinter)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            with self._lock:
                self.latest_frame = (frame_rgb, final_state, current_score)

        # ── Cleanup ───────────────────────────────────────────────────────────
        try:
            yolo_pool.shutdown(wait=False)
        except Exception:
            pass
        cap.release()
        if video_session:
            video_session.stop()
        print("[MonitoringStream] Stopped.")