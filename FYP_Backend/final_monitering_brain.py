# # """
# # FYP Elderly Fall Detection — v19 (MongoDB + Transparent Setup)
# # ===============================================================
# #   - Transparent zone setup screen (same size as detection window)
# #   - MongoDB integration for all patient data and fall events
# #   - Video saving: continuous recording + fall clips
# #   - Patient folder: data/patients/{name}/

# # FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
# # Supervisor: Dr. Zia Ul Rehman
# # """

# # import cv2
# # import numpy as np
# # from ultralytics import YOLO
# # import torch
# # from collections import deque
# # import os
# # import sys
# # import json
# # import math

# # # ── FYP modules ───────────────────────────────────────
# # from patient_storage       import PatientDirs
# # from video_recorder        import VideoSession
# # from patait_info_collector import AIBrainProfile
# # from mongo_storage         import leo_db

# # # ══════════════════════════════════════════════════════
# # # CONFIGURATION
# # # ══════════════════════════════════════════════════════
# # VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
# # # VIDEO_PATH = 0
# # FRAME_W    = 640
# # FRAME_H    = 480

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

# # # ══════════════════════════════════════════════════════
# # # STEP 1 — PATIENT INFO COLLECTOR
# # # ══════════════════════════════════════════════════════
# # print("\n" + "="*50)
# # print("   LEO — AI Home Assistant for the Elderly")
# # print("   FYP 2024-25 | BSCS")
# # print("="*50)

# # _collector       = AIBrainProfile()
# # _collector.startup()
# # _patient_profile = _collector.get_profile()
# # PATIENT_NAME     = _patient_profile["personal"]["name"].lower().replace(" ", "_")

# # print(f"\n[INFO] Patient: {PATIENT_NAME}")
# # print("[INFO] Loading models...\n")

# # patient_dirs = PatientDirs(PATIENT_NAME)
# # ZONES_FILE   = str(patient_dirs.root / "safe_zones.json")

# # # ══════════════════════════════════════════════════════
# # # DETECTION PARAMETERS
# # # ══════════════════════════════════════════════════════
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

# # # ══════════════════════════════════════════════════════
# # # COLORS & METADATA
# # # ══════════════════════════════════════════════════════
# # ZONE_COLORS = {
# #     "bed":  (0,   200, 255),
# #     "sofa": (0,   140, 255),
# # }
# # TYPE_ORDER = ["bed", "sofa"]

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

# # # ══════════════════════════════════════════════════════
# # # DEVICE + MODELS
# # # ══════════════════════════════════════════════════════
# # device = "cuda" if torch.cuda.is_available() else "cpu"
# # print(f"[INFO] Device: {device}")
# # print(f"[INFO] Patient: {PATIENT_NAME}")
# # print(f"[INFO] Data folder: {patient_dirs.root}")

# # fall_model    = YOLO(FALL_MODEL_PATH).to(device)
# # posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

# # if isinstance(VIDEO_PATH, str) and not os.path.exists(VIDEO_PATH):
# #     print(f"[ERROR] Video not found: {VIDEO_PATH}")
# #     sys.exit(1)

# # # ══════════════════════════════════════════════════════
# # # ZONE SAVE / LOAD
# # # ══════════════════════════════════════════════════════

# # def save_zones(zones, path=ZONES_FILE):
# #     data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
# #     with open(path, "w") as f:
# #         json.dump(data, f, indent=2)
# #     print(f"[ZONES] Saved {len(zones)} zone(s) -> {path}")


# # def load_zones(path=ZONES_FILE):
# #     if not os.path.exists(path):
# #         print(f"[ZONES] No saved file at {path}")
# #         return []
# #     try:
# #         with open(path) as f:
# #             data = json.load(f)
# #         zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
# #         print(f"[ZONES] Loaded {len(zones)} zone(s)")
# #         return zones
# #     except Exception as e:
# #         print(f"[ZONES] Load error: {e}")
# #         return []


# # def person_zone(person_box, zones):
# #     if person_box is None or not zones:
# #         return None
# #     cx = (person_box[0] + person_box[2]) / 2
# #     cy = (person_box[1] + person_box[3]) / 2
# #     for z in zones:
# #         x1, y1, x2, y2 = z["box"]
# #         if x1 <= cx <= x2 and y1 <= cy <= y2:
# #             return z
# #     return None


# # def person_in_safe_zone(person_box, zones):
# #     return person_zone(person_box, zones) is not None


# # # ══════════════════════════════════════════════════════
# # # SHARED DRAW HELPERS
# # # ══════════════════════════════════════════════════════

# # def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
# #     (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
# #     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
# #     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
# #     cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
# #                 (255,255,255), 1, cv2.LINE_AA)


# # def draw_crosshair(img, x, y, size=14, col=(0,255,180)):
# #     cv2.line(img, (x-size, y), (x+size, y), col, 1, cv2.LINE_AA)
# #     cv2.line(img, (x, y-size), (x, y+size), col, 1, cv2.LINE_AA)
# #     cv2.circle(img, (x, y), 4, col, 1, cv2.LINE_AA)


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


# # # ══════════════════════════════════════════════════════
# # # ZONE SETUP SCREEN
# # # FROM DOC3: transparent overlay, same size as detection
# # # ══════════════════════════════════════════════════════

# # def run_setup_screen(video_path, existing_zones):
# #     """
# #     Transparent zone drawing startup screen.
# #     - Same size as detection window (FRAME_W x FRAME_H)
# #     - Video frame fully visible underneath (80% brightness)
# #     - Zones drawn as semi-transparent rectangles (25% fill)
# #     - Options panel is a semi-transparent overlay (top-right corner)
# #     - cv2.WINDOW_NORMAL + resizeWindow = single clean window on Windows
# #     """

# #     # Get background frame — NOT darkened, full visibility
# #     bg = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
# #     cap_s = cv2.VideoCapture(video_path)
# #     if cap_s.isOpened():
# #         for _ in range(5):
# #             ret, raw = cap_s.read()
# #         if ret:
# #             bg = cv2.resize(raw, (FRAME_W, FRAME_H))
# #     cap_s.release()
# #     bg = cv2.addWeighted(bg, 0.80, np.zeros_like(bg), 0.20, 0)

# #     # State
# #     S = {
# #         "zones":   list(existing_zones),
# #         "ztype":   "bed",
# #         "drawing": False,
# #         "p0":      None,
# #         "p1":      None,
# #         "mouse":   (0, 0),
# #         "done":    False,
# #         "save":    True,
# #     }

# #     # Panel overlay position (top-right corner)
# #     PNL_W = 180
# #     PNL_H = 320
# #     PNL_X = FRAME_W - PNL_W - 8
# #     PNL_Y = 8
# #     BH    = 30
# #     BW    = PNL_W - 16
# #     BX    = PNL_X + 8

# #     # Button definitions: (label, key, y_in_canvas)
# #     BTNS = [
# #         ("BED  zone",       "bed",   PNL_Y + 55),
# #         ("SOFA zone",       "sofa",  PNL_Y + 91),
# #         ("Delete last",     "del",   PNL_Y + 148),
# #         ("Clear all",       "clear", PNL_Y + 184),
# #         ("START >>>",       "start", PNL_Y + 262),
# #         ("Skip (no zones)", "skip",  PNL_Y + 298),
# #     ]

# #     def hit(mx, my):
# #         for lbl, key, by in BTNS:
# #             if BX <= mx <= BX+BW and by <= my <= by+BH:
# #                 return key
# #         return None

# #     def cb(evt, mx, my, flags, param):
# #         S["mouse"] = (mx, my)

# #         if evt == cv2.EVENT_MOUSEMOVE:
# #             if S["drawing"] and S["p0"]:
# #                 S["p1"] = (max(0, min(mx, FRAME_W-1)),
# #                            max(0, min(my, FRAME_H-1)))

# #         elif evt == cv2.EVENT_LBUTTONDOWN:
# #             S["drawing"] = True
# #             S["p0"] = (mx, my)
# #             S["p1"] = (mx, my)

# #         elif evt == cv2.EVENT_LBUTTONUP:
# #             if S["drawing"]:
# #                 S["drawing"] = False
# #                 if S["p0"] and S["p1"]:
# #                     x1 = min(S["p0"][0], S["p1"][0])
# #                     y1 = min(S["p0"][1], S["p1"][1])
# #                     x2 = max(S["p0"][0], S["p1"][0])
# #                     y2 = max(S["p0"][1], S["p1"][1])
# #                     if (x2-x1) > 15 and (y2-y1) > 15:
# #                         k = hit(S["p0"][0], S["p0"][1])
# #                         if k:
# #                             _handle(k)
# #                         else:
# #                             S["zones"].append({"type": S["ztype"],
# #                                                "box":  (x1,y1,x2,y2)})
# #                             print(f"[SETUP] Zone added: {S['ztype']} "
# #                                   f"({x1},{y1})-({x2},{y2})")
# #                 S["p0"] = S["p1"] = None

# #     def _handle(k):
# #         if k == "bed":    S["ztype"] = "bed"
# #         elif k == "sofa": S["ztype"] = "sofa"
# #         elif k == "del":
# #             if S["zones"]: S["zones"].pop()
# #         elif k == "clear": S["zones"].clear()
# #         elif k == "start": S["save"] = True;  S["done"] = True
# #         elif k == "skip":  S["save"] = False; S["done"] = True

# #     # Window — same size as detection window, single window on Windows
# #     WIN_S = f"LEO Zone Setup -- {PATIENT_NAME}"
# #     cv2.namedWindow(WIN_S, cv2.WINDOW_NORMAL)
# #     cv2.resizeWindow(WIN_S, FRAME_W, FRAME_H)
# #     cv2.setMouseCallback(WIN_S, cb)

# #     # Show initial frame immediately — no black flash
# #     cv2.imshow(WIN_S, bg)
# #     cv2.waitKey(1)

# #     while not S["done"]:
# #         canvas = bg.copy()

# #         # 1. Draw committed zones (semi-transparent 25% fill)
# #         for z in S["zones"]:
# #             x1,y1,x2,y2 = z["box"]
# #             col = ZONE_COLORS[z["type"]]
# #             ov  = canvas.copy()
# #             cv2.rectangle(ov, (x1,y1),(x2,y2), col, -1)
# #             cv2.addWeighted(ov, 0.25, canvas, 0.75, 0, canvas)
# #             cv2.rectangle(canvas,(x1,y1),(x2,y2),col,2,cv2.LINE_AA)
# #             lbl = z["type"].upper()
# #             (tw,th),_ = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.42,1)
# #             bov = canvas.copy()
# #             cv2.rectangle(bov,(x1,y1),(x1+tw+8,y1+th+6),col,-1)
# #             cv2.addWeighted(bov,0.75,canvas,0.25,0,canvas)
# #             cv2.putText(canvas,lbl,(x1+4,y1+th+2),
# #                         cv2.FONT_HERSHEY_SIMPLEX,0.42,(255,255,255),1,cv2.LINE_AA)

# #         # 2. Live drag rectangle (20% fill while dragging)
# #         if S["drawing"] and S["p0"] and S["p1"]:
# #             col = ZONE_COLORS[S["ztype"]]
# #             rx1 = min(S["p0"][0],S["p1"][0])
# #             ry1 = min(S["p0"][1],S["p1"][1])
# #             rx2 = max(S["p0"][0],S["p1"][0])
# #             ry2 = max(S["p0"][1],S["p1"][1])
# #             ov = canvas.copy()
# #             cv2.rectangle(ov,(rx1,ry1),(rx2,ry2),col,-1)
# #             cv2.addWeighted(ov,0.20,canvas,0.80,0,canvas)
# #             cv2.rectangle(canvas,(rx1,ry1),(rx2,ry2),col,2,cv2.LINE_AA)
# #             cv2.putText(canvas,f"{rx2-rx1}x{ry2-ry1}",
# #                         (rx1+4,max(ry1-5,14)),
# #                         cv2.FONT_HERSHEY_SIMPLEX,0.36,col,1)

# #         # 3. Crosshair
# #         mx,my = S["mouse"]
# #         if not S["drawing"]:
# #             col = ZONE_COLORS[S["ztype"]]
# #             cv2.line(canvas,(mx-14,my),(mx+14,my),col,1,cv2.LINE_AA)
# #             cv2.line(canvas,(mx,my-14),(mx,my+14),col,1,cv2.LINE_AA)
# #             cv2.circle(canvas,(mx,my),4,col,1,cv2.LINE_AA)

# #         # 4. Top instruction bar (75% opacity)
# #         bar = canvas.copy()
# #         cv2.rectangle(bar,(0,0),(FRAME_W,26),(8,8,14),-1)
# #         cv2.addWeighted(bar,0.75,canvas,0.25,0,canvas)
# #         zc  = len(S["zones"])
# #         inst = (f"DRAG to draw zone  |  Type: {S['ztype'].upper()}"
# #                 f"  |  Zones: {zc}  |  ENTER=start  Q=skip  D=del  TAB=switch")
# #         cv2.putText(canvas,inst,(6,18),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.30,(0,220,100),1)

# #         # 5. Panel overlay (72% opacity, top-right corner)
# #         pov = canvas.copy()
# #         cv2.rectangle(pov,(PNL_X-2, PNL_Y-2),
# #                           (PNL_X+PNL_W+2, PNL_Y+PNL_H+2),(8,8,18),-1)
# #         cv2.addWeighted(pov,0.72,canvas,0.28,0,canvas)
# #         cv2.rectangle(canvas,(PNL_X-2,PNL_Y-2),
# #                               (PNL_X+PNL_W+2,PNL_Y+PNL_H+2),(60,65,90),1)

# #         cv2.putText(canvas,"LEO SETUP",(PNL_X+6,PNL_Y+20),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,210,255),1,cv2.LINE_AA)
# #         cv2.putText(canvas,f"Pt: {PATIENT_NAME}",(PNL_X+6,PNL_Y+38),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.28,(100,200,100),1)
# #         cv2.line(canvas,(PNL_X+4,PNL_Y+44),(PNL_X+PNL_W-4,PNL_Y+44),(45,45,65),1)
# #         cv2.putText(canvas,"ZONE TYPE:",(PNL_X+6,PNL_Y+52),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

# #         hov = hit(mx, my)
# #         for lbl,key,by in BTNS:
# #             active  = (key == S["ztype"] and key in ("bed","sofa"))
# #             hovered = (hov == key)
# #             if key == "start":
# #                 bgc = (0,160,55) if not hovered else (0,200,70)
# #                 bdc = (0,230,100)
# #             elif key == "skip":
# #                 bgc = (28,28,48) if not hovered else (42,42,68)
# #                 bdc = (65,70,95)
# #             elif key in ("del","clear"):
# #                 bgc = (90,18,18) if not hovered else (120,22,22)
# #                 bdc = (170,35,35)
# #             elif active:
# #                 bgc = ZONE_COLORS[key]
# #                 bdc = (220,230,255)
# #             else:
# #                 bgc = (28,30,46) if not hovered else (42,45,68)
# #                 bdc = (52,57,82)

# #             bov2 = canvas.copy()
# #             cv2.rectangle(bov2,(BX,by),(BX+BW,by+BH),bgc,-1)
# #             cv2.addWeighted(bov2,0.85,canvas,0.15,0,canvas)
# #             cv2.rectangle(canvas,(BX,by),(BX+BW,by+BH),bdc,1)
# #             if active:
# #                 cv2.circle(canvas,(BX+10,by+BH//2),4,(0,255,140),-1)
# #             tw,th = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.35,1)[0]
# #             cv2.putText(canvas,lbl,(BX+(BW-tw)//2,by+(BH+th)//2),
# #                         cv2.FONT_HERSHEY_SIMPLEX,0.35,(225,230,255),1,cv2.LINE_AA)

# #         sep_y1 = PNL_Y + 130
# #         sep_y2 = PNL_Y + 248
# #         cv2.line(canvas,(PNL_X+4,sep_y1),(PNL_X+PNL_W-4,sep_y1),(45,45,65),1)
# #         cv2.putText(canvas,"ACTIONS:",(PNL_X+6,sep_y1+14),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)
# #         cv2.line(canvas,(PNL_X+4,sep_y2),(PNL_X+PNL_W-4,sep_y2),(45,45,65),1)
# #         cv2.putText(canvas,"WHEN READY:",(PNL_X+6,sep_y2+14),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

# #         zcol = (0,200,80) if zc else (80,80,100)
# #         cv2.putText(canvas,f"Zones: {zc}",
# #                     (PNL_X+6, PNL_Y+PNL_H-10),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.32,zcol,1)

# #         cv2.imshow(WIN_S, canvas)

# #         k = cv2.waitKey(16) & 0xFF
# #         if   k in (13, ord('s'), ord('S')): S["save"]=True;  S["done"]=True
# #         elif k in (ord('q'), ord('Q')):     S["save"]=False; S["done"]=True
# #         elif k in (ord('d'), ord('D')):
# #             if S["zones"]: S["zones"].pop()
# #         elif k in (ord('c'), ord('C')):
# #             S["zones"].clear()
# #         elif k == 9:
# #             S["ztype"] = "sofa" if S["ztype"]=="bed" else "bed"

# #     cv2.destroyWindow(WIN_S)
# #     cv2.waitKey(1)

# #     if S["save"] and S["zones"]:
# #         save_zones(S["zones"])
# #     print(f"[SETUP] {len(S['zones'])} zone(s) confirmed.")
# #     return S["zones"]


# # # ══════════════════════════════════════════════════════
# # # DETECTION HELPERS
# # # ══════════════════════════════════════════════════════

# # def get_aspect_ratio(box):
# #     x1,y1,x2,y2 = box
# #     return max(y2-y1,1)/max(x2-x1,1)

# # def get_bbox_area(box):
# #     x1,y1,x2,y2 = box
# #     return max(x2-x1,0)*max(y2-y1,0)

# # def compute_flow_energy(gray_curr, gray_prev, box):
# #     if gray_prev is None or box is None: return 0.0
# #     x1=max(int(box[0]),0); y1=max(int(box[1]),0)
# #     x2=min(int(box[2]),gray_curr.shape[1])
# #     y2=min(int(box[3]),gray_curr.shape[0])
# #     if x2<=x1+4 or y2<=y1+4: return 0.0
# #     flow = cv2.calcOpticalFlowFarneback(
# #         gray_prev[y1:y2,x1:x2], gray_curr[y1:y2,x1:x2], None,
# #         pyr_scale=0.5,levels=2,winsize=12,iterations=2,
# #         poly_n=5,poly_sigma=1.1,flags=0)
# #     return float(np.mean(np.sqrt(flow[...,0]**2+flow[...,1]**2)))

# # def select_main_subject(boxes_labels_confs):
# #     if not boxes_labels_confs: return "none", None
# #     best_label,best_box,best_area,best_conf = "none",None,-1,-1
# #     for (label,box,conf) in boxes_labels_confs:
# #         area=get_bbox_area(box); ar=get_aspect_ratio(box)
# #         if label=="lying" and ar>LYING_ASPECT_RATIO_MAX: continue
# #         if area>best_area or (area==best_area and conf>best_conf):
# #             best_area,best_conf=area,conf
# #             best_label,best_box=label,box
# #     return best_label,best_box

# # safe_zones = []

# # def analyze_fall_timeline(fmc, ar_hist, pre_posture="none", current_person_box=None):
# #     if current_person_box is not None and person_in_safe_zone(current_person_box, safe_zones):
# #         return False, 0, "blocked:person_in_safe_zone"

# #     flow_list=list(flow_history); drop_list=list(drop_history)
# #     area_list=list(area_change_history); post_list=list(posture_history)
# #     ar_list=list(ar_hist) if ar_hist else []
# #     raw_drops=list(raw_drop_history); raw_areas=list(raw_area_history)
# #     score=0; notes=[]

# #     if pre_posture=="sitting":
# #         if fmc>=FALL_MODEL_CONSEC: notes.append("sitting_override_by_fallmodel")
# #         else: return False,0,"blocked:sitting_to_lying(sofa/bed)"

# #     upright_count=sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
# #                       if p in ("standing","sitting"))
# #     if upright_count<MIN_UPRIGHT_FRAMES:
# #         return False,0,f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

# #     has_sudden_drop=any(d>=SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
# #     has_sudden_area=any(a>=SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
# #     if not has_sudden_drop and not has_sudden_area and fmc==0:
# #         return False,0,"blocked:gradual_transition(no_spike,no_fallmodel)"

# #     pre_drops=drop_list[-PRE_LYING_WINDOW:] if drop_list else []
# #     max_drop=max(pre_drops) if pre_drops else 0.0
# #     if   max_drop>=DROP_FAST_PX: score+=2; notes.append(f"fast_drop={max_drop:.0f}")
# #     elif max_drop>=DROP_ANY_PX:  score+=1; notes.append(f"drop={max_drop:.0f}")

# #     pre_area=area_list[-PRE_LYING_WINDOW:] if area_list else []
# #     max_area_chg=max(pre_area) if pre_area else 0.0
# #     if   max_area_chg>=AREA_CHANGE_HIGH: score+=2; notes.append(f"area_chg={max_area_chg:.2f}")
# #     elif max_area_chg>=AREA_CHANGE_ANY:  score+=1; notes.append(f"area_any={max_area_chg:.2f}")

# #     n=len(flow_list)
# #     pre_flow=flow_list[max(0,n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
# #                        max(0,n-POST_LYING_WINDOW)]
# #     max_pre_flow=max(pre_flow) if pre_flow else 0.0
# #     if   max_pre_flow>=FLOW_SPIKE_THRESH: score+=2; notes.append(f"flow_spike={max_pre_flow:.2f}")
# #     elif max_pre_flow>=FLOW_ANY_THRESH:   score+=1; notes.append(f"flow={max_pre_flow:.2f}")

# #     if len(ar_list)>=4:
# #         ar_before=float(np.mean(ar_list[:max(1,len(ar_list)-PRE_LYING_WINDOW)]))
# #         ar_after=float(np.mean(ar_list[-3:]))
# #         ar_drop=ar_before-ar_after
# #         if ar_drop>=ASPECT_DROP_THRESH: score+=2; notes.append(f"aspect_flip={ar_drop:.2f}")

# #     if fmc>=FALL_MODEL_CONSEC: score+=3; notes.append(f"fall_model={fmc}f")

# #     if (max_drop<DROP_ANY_PX and max_area_chg<AREA_CHANGE_ANY
# #             and max_pre_flow<FLOW_ANY_THRESH):
# #         return False,score,(f"blocked:no_motion(d={max_drop:.1f} "
# #                             f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

# #     post_flow=(flow_list[-POST_LYING_WINDOW:]
# #                if len(flow_list)>=POST_LYING_WINDOW else flow_list)
# #     still_ratio=sum(1 for f in post_flow if f<FLOW_STILL_THRESH)/max(len(post_flow),1)
# #     if still_ratio>=0.35: score+=1; notes.append(f"still={still_ratio:.0%}")

# #     reason=f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
# #     if score>=FALL_SCORE_NEEDED: return True,score,f"FALL:{reason}"
# #     return False,score,f"safe:{reason}"


# # # ══════════════════════════════════════════════════════
# # # DETECTION DISPLAY HELPERS
# # # ══════════════════════════════════════════════════════

# # def draw_banner(frame, state):
# #     col=STATE_META.get(state,((100,100,100),"?"))[0]
# #     W=frame.shape[1]
# #     ov=frame.copy()
# #     cv2.rectangle(ov,(0,0),(W,58),col,-1)
# #     cv2.addWeighted(ov,0.55,frame,0.45,0,frame)
# #     cv2.rectangle(frame,(0,0),(5,58),col,-1)
# #     cv2.line(frame,(0,58),(W,58),col,1)
# #     cv2.putText(frame,f"STATE:  {state}",
# #                 (16,40),cv2.FONT_HERSHEY_SIMPLEX,
# #                 0.95,(255,255,255),2,cv2.LINE_AA)

# # def draw_signals(frame, flow_val, area_chg, drop_vel, score):
# #     H,W=frame.shape[:2]
# #     px,py=6,H-90; pw=192
# #     ov=frame.copy()
# #     cv2.rectangle(ov,(px-2,py-2),(px+pw,py+80),(12,12,18),-1)
# #     cv2.addWeighted(ov,0.78,frame,0.22,0,frame)
# #     cv2.rectangle(frame,(px-2,py-2),(px+pw,py+80),(50,50,70),1)
# #     sigs=[("FLOW",flow_val,5.0,(0,200,255)),
# #           ("AREA",area_chg,0.3,(0,180,120)),
# #           ("DROP",drop_vel,20.0,(60,100,255)),
# #           ("SCOR",score,FALL_SCORE_NEEDED*1.5,(0,60,255))]
# #     bx=px+44; bmax=pw-52
# #     for i,(lbl,val,mx,col) in enumerate(sigs):
# #         y=py+6+i*18
# #         bw=int(min(val/max(mx,0.001),1.0)*bmax)
# #         cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(28,28,40),-1)
# #         if bw>0: cv2.rectangle(frame,(bx,y+2),(bx+bw,y+12),col,-1)
# #         cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(55,55,75),1)
# #         cv2.putText(frame,lbl,(px,y+12),cv2.FONT_HERSHEY_SIMPLEX,0.30,(140,140,165),1)
# #         cv2.putText(frame,f"{val:.1f}",(bx+bmax+3,y+12),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(170,170,195),1)

# # def draw_rec_indicator(frame, is_saving_clip, tick):
# #     H,W=frame.shape[:2]
# #     pulse = int(180 + 75 * math.sin(tick * 0.2))
# #     cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
# #     cv2.putText(frame, "REC", (W-45, 25),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
# #     if is_saving_clip:
# #         badge = "  SAVING FALL CLIP  "
# #         (bw,bh),_ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
# #         bx = W - bw - 60
# #         cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
# #         cv2.putText(frame, badge, (bx, 30+bh+2),
# #                     cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# # # ══════════════════════════════════════════════════════
# # # STARTUP
# # # ══════════════════════════════════════════════════════
# # print(f"\n[INFO] Loading saved zones for patient '{PATIENT_NAME}'...")
# # safe_zones = load_zones()

# # print("[INFO] Opening zone setup screen...")
# # safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
# # print(f"[INFO] {len(safe_zones)} zone(s) confirmed. Starting detection...\n")

# # # Start video session
# # video_session = VideoSession(
# #     patient_name    = PATIENT_NAME,
# #     fps             = 20.0,
# #     frame_size      = (FRAME_W, FRAME_H),
# #     save_continuous = True,
# # )
# # video_session.start()

# # # Start MongoDB session
# # if leo_db.connected:
# #     leo_db.save_patient(_patient_profile)
# #     leo_db.start_session(
# #         patient        = PATIENT_NAME,
# #         recording_path = video_session.recorder.saved_path,
# #     )

# # # ══════════════════════════════════════════════════════
# # # STATE VARIABLES
# # # ══════════════════════════════════════════════════════
# # posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
# # flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
# # drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
# # area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
# # aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
# # raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
# # raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

# # prev_gray=prev_center_y=prev_bbox_area=prev_aspect_ratio=None
# # lying_consec=standing_consec=fall_model_consec=0
# # frames_since_lying=0; episode_analyzed=False
# # last_valid_posture="none"; posture_persist_counter=0
# # fall_latch_ctr=recovery_latch_ctr=0
# # final_state="STARTING"; fall_reason=""
# # post_fall_lying=False; pre_lying_posture="none"
# # episode_locked=False; last_upright_posture="none"
# # sitting_consec_pre=0; safe_lying_locked=False
# # last_known_posture="none"
# # frame_count=0

# # # ══════════════════════════════════════════════════════
# # # MAIN DETECTION LOOP
# # # ══════════════════════════════════════════════════════
# # cap = cv2.VideoCapture(VIDEO_PATH)
# # WIN = f"FYP Fall Detection v19 -- {PATIENT_NAME}"
# # cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
# # cv2.resizeWindow(WIN, FRAME_W, FRAME_H)

# # def rt_mouse_cb(event, x, y, flags, param):
# #     pass

# # cv2.setMouseCallback(WIN, rt_mouse_cb)


# # while True:
# #     ret, frame = cap.read()
# #     if not ret:
# #         print("[INFO] Video ended.")
# #         break

# #     frame_count += 1
# #     frame = cv2.resize(frame, (FRAME_W, FRAME_H))
# #     gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# #     video_session.feed(frame)

# #     # FALL MODEL
# #     fall_detected=False
# #     for r in fall_model(frame,conf=0.5,verbose=False):
# #         for box in r.boxes:
# #             cls=int(box.cls[0]); label=fall_model.names[cls]
# #             conf=float(box.conf[0]); x1,y1,x2,y2=map(int,box.xyxy[0])
# #             if label.lower()=="fall": fall_detected=True
# #             cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,180),2)
# #             cv2.putText(frame,f"{label} {conf:.2f}",(x1,max(y1-8,70)),
# #                         cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,0,180),1)
# #     fall_model_consec=fall_model_consec+1 if fall_detected else 0

# #     # POSTURE MODEL
# #     all_detections=[]
# #     for r in posture_model(frame,conf=0.45,verbose=False):
# #         for box in r.boxes:
# #             conf=float(box.conf[0]); cls=int(box.cls[0])
# #             label=posture_model.names[cls].lower()
# #             x1,y1,x2,y2=map(int,box.xyxy[0])
# #             all_detections.append((label,(x1,y1,x2,y2),conf))
# #             ar=get_aspect_ratio((x1,y1,x2,y2))
# #             reject=(label=="lying" and ar>LYING_ASPECT_RATIO_MAX)
# #             color=(120,120,120) if reject else (0,180,0)
# #             cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
# #             cv2.putText(frame,f"{label}{'[X]' if reject else ''} {conf:.2f}",
# #                         (x1,max(y1-26,70)),cv2.FONT_HERSHEY_SIMPLEX,0.38,
# #                         (100,100,100) if reject else (0,180,0),1)

# #     raw_posture_label,person_box=select_main_subject(all_detections)
# #     active_zone=person_zone(person_box,safe_zones)
# #     on_safe_zone=active_zone is not None

# #     if raw_posture_label!="none":
# #         last_valid_posture=raw_posture_label
# #         posture_persist_counter=0; posture_label=raw_posture_label
# #     else:
# #         posture_persist_counter+=1
# #         posture_label=(last_valid_posture
# #                        if posture_persist_counter<=POSTURE_PERSIST_FRAMES
# #                        else "none")
# #     if posture_label!="none": last_known_posture=posture_label

# #     flow_energy=compute_flow_energy(gray_curr,prev_gray,person_box)
# #     flow_history.append(flow_energy)
# #     prev_gray=gray_curr.copy()

# #     drop_velocity=0.0; area_change=0.0
# #     curr_ar=prev_aspect_ratio if prev_aspect_ratio else 1.5
# #     if person_box is not None:
# #         x1,y1,x2,y2=person_box
# #         cy=(y1+y2)/2.0; curr_ar=get_aspect_ratio(person_box)
# #         curr_area=get_bbox_area(person_box)
# #         if prev_center_y is not None: drop_velocity=cy-prev_center_y
# #         if prev_bbox_area and prev_bbox_area>0:
# #             area_change=abs(curr_area-prev_bbox_area)/prev_bbox_area
# #         prev_center_y=cy; prev_bbox_area=curr_area; prev_aspect_ratio=curr_ar

# #     drop_history.append(max(drop_velocity,0.0))
# #     area_change_history.append(area_change)
# #     aspect_ratio_history.append(curr_ar)
# #     raw_drop_history.append(max(drop_velocity,0.0))
# #     raw_area_history.append(area_change)

# #     if fall_latch_ctr==0: posture_history.append(posture_label)

# #     if lying_consec<LYING_CONFIRM_FRAMES:
# #         if posture_label=="standing":
# #             last_upright_posture="standing"; sitting_consec_pre=0
# #         elif posture_label=="sitting":
# #             sitting_consec_pre+=1
# #             if sitting_consec_pre>=SITTING_CONFIRM_FOR_PREPOSTURE:
# #                 last_upright_posture="sitting"
# #         else: sitting_consec_pre=0

# #     if posture_label=="lying":
# #         lying_consec+=1; standing_consec=0
# #         if lying_consec==LYING_CONFIRM_FRAMES and not episode_locked:
# #             pre_lying_posture=last_upright_posture; episode_locked=True
# #         if on_safe_zone and lying_consec>=LYING_CONFIRM_FRAMES and not safe_lying_locked:
# #             safe_lying_locked=True
# #             fall_reason=f"blocked:person_on_{active_zone['type']}(safe_zone)"
# #     elif posture_label in ("standing","sitting"):
# #         standing_consec+=1
# #         if standing_consec>=STANDING_CONFIRM_FRAMES:
# #             lying_consec=0; frames_since_lying=0; episode_analyzed=False
# #             fall_reason=""; post_fall_lying=False; episode_locked=False
# #             pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
# #     else: standing_consec=0

# #     if lying_consec>=LYING_CONFIRM_FRAMES:
# #         frames_since_lying+=1
# #     else:
# #         if frames_since_lying>0:
# #             post_fall_lying=False; episode_analyzed=False; episode_locked=False
# #             pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
# #         frames_since_lying=0

# #     current_score=0
# #     in_analysis_window=ANALYSIS_START<=frames_since_lying<=ANALYSIS_END

# #     if (in_analysis_window and not episode_analyzed
# #             and not safe_lying_locked and fall_latch_ctr==0):
# #         is_fall,current_score,fall_reason=analyze_fall_timeline(
# #             fall_model_consec,aspect_ratio_history,
# #             pre_posture=pre_lying_posture,current_person_box=person_box)
# #         if is_fall:
# #             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
# #             clip_path = video_session.on_fall()
# #             print(f"[FALL] Clip saving -> {clip_path}")
# #             if leo_db.connected:
# #                 leo_db.log_fall(PATIENT_NAME, clip_path,
# #                                 score=current_score, reason=fall_reason,
# #                                 posture=posture_label, state=final_state)
# #                 leo_db.log_activity(PATIENT_NAME, "fall",
# #                                     f"Fall detected -- score:{current_score}",
# #                                     severity="critical")
# #         else: safe_lying_locked=True

# #     if (fall_detected and fall_model_consec>=FALL_MODEL_CONSEC
# #             and lying_consec>=LYING_CONFIRM_FRAMES
# #             and not safe_lying_locked and fall_latch_ctr==0
# #             and not episode_analyzed):
# #         is_fall,current_score,fall_reason=analyze_fall_timeline(
# #             fall_model_consec,aspect_ratio_history,
# #             pre_posture=pre_lying_posture,current_person_box=person_box)
# #         if is_fall:
# #             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
# #             clip_path = video_session.on_fall()
# #             print(f"[FALL] Clip saving -> {clip_path}")
# #             if leo_db.connected:
# #                 leo_db.log_fall(PATIENT_NAME, clip_path,
# #                                 score=current_score, reason=fall_reason,
# #                                 posture=posture_label, state=final_state)
# #                 leo_db.log_activity(PATIENT_NAME, "fall",
# #                                     f"Fall detected -- score:{current_score}",
# #                                     severity="critical")
# #         else: safe_lying_locked=True

# #     if (posture_label=="none" and fall_model_consec>=FALL_MODEL_CONSEC
# #             and not safe_lying_locked and fall_latch_ctr==0
# #             and not episode_analyzed
# #             and last_known_posture in ("standing","sitting")
# #             and not person_in_safe_zone(person_box,safe_zones)):
# #         is_fall,current_score,fall_reason=analyze_fall_timeline(
# #             fall_model_consec,aspect_ratio_history,
# #             pre_posture=last_known_posture,current_person_box=person_box)
# #         if is_fall:
# #             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
# #             fall_reason=f"[FM-UNKNOWN] {fall_reason}"
# #             clip_path = video_session.on_fall()
# #             print(f"[FALL] Clip saving -> {clip_path}")
# #             if leo_db.connected:
# #                 leo_db.log_fall(PATIENT_NAME, clip_path,
# #                                 score=current_score, reason=fall_reason,
# #                                 posture=posture_label, state=final_state)
# #                 leo_db.log_activity(PATIENT_NAME, "fall",
# #                                     f"Fall detected -- score:{current_score}",
# #                                     severity="critical")

# #     if fall_latch_ctr>0 and on_safe_zone:
# #         fall_latch_ctr=0; recovery_latch_ctr=0
# #         post_fall_lying=False; safe_lying_locked=True
# #         fall_reason="blocked:entered_safe_zone_during_latch"
# #         print("[BLOCK-B] Latch cancelled -- person in safe zone")

# #     if fall_latch_ctr>0:
# #         fall_latch_ctr-=1; final_state="FALL"
# #         if fall_latch_ctr==0: recovery_latch_ctr=RECOVERY_LATCH_FRAMES
# #     elif recovery_latch_ctr>0:
# #         recovery_latch_ctr-=1; final_state="RECOVERY"
# #     else:
# #         if posture_label=="lying":
# #             if post_fall_lying: final_state="LYING (POST-FALL)"
# #             elif on_safe_zone:  final_state=f"LYING (ON {active_zone['type'].upper()})"
# #             else:               final_state="LYING (SAFE)"
# #         elif posture_label=="standing": final_state="STANDING"
# #         elif posture_label=="sitting":  final_state="SITTING"
# #         else:                           final_state="UNKNOWN"

# #     draw_all_zones(frame,safe_zones,active_zone)
# #     draw_banner(frame,final_state)
# #     draw_signals(frame,flow_energy,area_change,max(drop_velocity,0),current_score)
# #     draw_rec_indicator(frame, video_session.clipper.is_saving, frame_count)

# #     H,W=frame.shape[:2]
# #     if on_safe_zone:
# #         col=ZONE_COLORS[active_zone["type"]]
# #         draw_pill_label(frame,f"ON {active_zone['type'].upper()}",W-108,88,col,scale=0.40)
# #     if safe_lying_locked:
# #         draw_pill_label(frame,"SAFE-LOCK",W-100,112,(30,130,60),scale=0.35)

# #     selected_ar=get_aspect_ratio(person_box) if person_box else 0.0
# #     dbg=(f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
# #          f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
# #          f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
# #          f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
# #          f"zone:{active_zone['type'] if active_zone else 'none'}  "
# #          f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
# #     cv2.putText(frame,dbg,(6,H-6),cv2.FONT_HERSHEY_SIMPLEX,0.27,(130,130,155),1)
# #     if fall_reason:
# #         cv2.putText(frame,fall_reason,(6,H-18),
# #                     cv2.FONT_HERSHEY_SIMPLEX,0.28,(55,195,255),1)

# #     cv2.imshow(WIN,frame)
# #     key=cv2.waitKey(1)&0xFF

# #     if key==ord('q'): break
# #     elif key==ord('c'):
# #         print("[INFO] Re-opening zone setup screen...")
# #         cap.release()
# #         cv2.destroyAllWindows()
# #         safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
# #         cap = cv2.VideoCapture(VIDEO_PATH)
# #         cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
# #         cv2.resizeWindow(WIN, FRAME_W, FRAME_H)
# #         cv2.setMouseCallback(WIN, rt_mouse_cb)
# #         print("[INFO] Resuming detection...")

# # cap.release()
# # cv2.destroyAllWindows()

# # video_session.stop()

# # if leo_db.connected:
# #     leo_db.end_session(fall_count=video_session.fall_count)
# #     leo_db.close()

# # print("[INFO] Done.")








# """
# FYP Elderly Fall Detection — v19 (MongoDB + Transparent Setup)
# ===============================================================
#   - Transparent zone setup screen (same size as detection window)
#   - MongoDB integration for all patient data and fall events
#   - Video saving: continuous recording + fall clips
#   - Patient folder: data/patients/{name}/

# FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
# Supervisor: Dr. Zia Ul Rehman
# """

# import cv2
# import numpy as np
# from ultralytics import YOLO
# import torch
# from collections import deque
# import os
# import sys
# import json
# import math

# # ── FYP modules ───────────────────────────────────────
# from patient_storage       import PatientDirs
# from video_recorder        import VideoSession
# from patait_info_collector import AIBrainProfile
# from mongo_storage         import leo_db

# # ══════════════════════════════════════════════════════
# # CONFIGURATION
# # ══════════════════════════════════════════════════════
# VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
# # VIDEO_PATH = 0
# FRAME_W    = 640
# FRAME_H    = 480

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

# # ══════════════════════════════════════════════════════
# # STEP 1 — PATIENT INFO COLLECTOR
# # ══════════════════════════════════════════════════════
# print("\n" + "="*50)
# print("   LEO — AI Home Assistant for the Elderly")
# print("   FYP 2024-25 | BSCS")
# print("="*50)

# _collector       = AIBrainProfile()
# _collector.startup()
# _patient_profile = _collector.get_profile()
# PATIENT_NAME     = _patient_profile["personal"]["name"].lower().replace(" ", "_")

# print(f"\n[INFO] Patient: {PATIENT_NAME}")
# print("[INFO] Loading models...\n")

# patient_dirs = PatientDirs(PATIENT_NAME)
# ZONES_FILE   = str(patient_dirs.root / "safe_zones.json")

# # ══════════════════════════════════════════════════════
# # DETECTION PARAMETERS
# # ══════════════════════════════════════════════════════
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

# # ══════════════════════════════════════════════════════
# # COLORS & METADATA
# # ══════════════════════════════════════════════════════
# ZONE_COLORS = {
#     "bed":  (0,   200, 255),
#     "sofa": (0,   140, 255),
# }
# TYPE_ORDER = ["bed", "sofa"]

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

# # ══════════════════════════════════════════════════════
# # DEVICE + MODELS
# # ══════════════════════════════════════════════════════
# device = "cuda" if torch.cuda.is_available() else "cpu"
# print(f"[INFO] Device: {device}")
# print(f"[INFO] Patient: {PATIENT_NAME}")
# print(f"[INFO] Data folder: {patient_dirs.root}")

# fall_model    = YOLO(FALL_MODEL_PATH).to(device)
# posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

# if isinstance(VIDEO_PATH, str) and not os.path.exists(VIDEO_PATH):
#     print(f"[ERROR] Video not found: {VIDEO_PATH}")
#     sys.exit(1)

# # ══════════════════════════════════════════════════════
# # ZONE SAVE / LOAD
# # ══════════════════════════════════════════════════════

# def save_zones(zones, path=ZONES_FILE):
#     data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
#     with open(path, "w") as f:
#         json.dump(data, f, indent=2)
#     print(f"[ZONES] Saved {len(zones)} zone(s) -> {path}")


# def load_zones(path=ZONES_FILE):
#     if not os.path.exists(path):
#         print(f"[ZONES] No saved file at {path}")
#         return []
#     try:
#         with open(path) as f:
#             data = json.load(f)
#         zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
#         print(f"[ZONES] Loaded {len(zones)} zone(s)")
#         return zones
#     except Exception as e:
#         print(f"[ZONES] Load error: {e}")
#         return []


# def person_zone(person_box, zones):
#     if person_box is None or not zones:
#         return None
#     cx = (person_box[0] + person_box[2]) / 2
#     cy = (person_box[1] + person_box[3]) / 2
#     for z in zones:
#         x1, y1, x2, y2 = z["box"]
#         if x1 <= cx <= x2 and y1 <= cy <= y2:
#             return z
#     return None


# def person_in_safe_zone(person_box, zones):
#     return person_zone(person_box, zones) is not None


# # ══════════════════════════════════════════════════════
# # SHARED DRAW HELPERS
# # ══════════════════════════════════════════════════════

# def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
#     (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
#     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
#     cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
#     cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
#                 (255,255,255), 1, cv2.LINE_AA)


# def draw_crosshair(img, x, y, size=14, col=(0,255,180)):
#     cv2.line(img, (x-size, y), (x+size, y), col, 1, cv2.LINE_AA)
#     cv2.line(img, (x, y-size), (x, y+size), col, 1, cv2.LINE_AA)
#     cv2.circle(img, (x, y), 4, col, 1, cv2.LINE_AA)


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


# # ══════════════════════════════════════════════════════
# # ZONE SETUP SCREEN
# # FROM DOC3: transparent overlay, same size as detection
# # ══════════════════════════════════════════════════════

# def run_setup_screen(video_path, existing_zones):
#     """
#     Transparent zone drawing startup screen.
#     - Same size as detection window (FRAME_W x FRAME_H)
#     - Video frame fully visible underneath (80% brightness)
#     - Zones drawn as semi-transparent rectangles (25% fill)
#     - Options panel is a semi-transparent overlay (top-right corner)
#     - cv2.WINDOW_NORMAL + resizeWindow = single clean window on Windows
#     """

#     # Get background frame — NOT darkened, full visibility
#     bg = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
#     cap_s = cv2.VideoCapture(video_path)
#     if cap_s.isOpened():
#         for _ in range(5):
#             ret, raw = cap_s.read()
#         if ret:
#             bg = cv2.resize(raw, (FRAME_W, FRAME_H))
#     cap_s.release()
#     bg = cv2.addWeighted(bg, 0.80, np.zeros_like(bg), 0.20, 0)

#     # State
#     S = {
#         "zones":   list(existing_zones),
#         "ztype":   "bed",
#         "drawing": False,
#         "p0":      None,
#         "p1":      None,
#         "mouse":   (0, 0),
#         "done":    False,
#         "save":    True,
#     }

#     # Panel overlay position (top-right corner)
#     PNL_W = 180
#     PNL_H = 320
#     PNL_X = FRAME_W - PNL_W - 8
#     PNL_Y = 8
#     BH    = 30
#     BW    = PNL_W - 16
#     BX    = PNL_X + 8

#     # Button definitions: (label, key, y_in_canvas)
#     BTNS = [
#         ("BED  zone",       "bed",   PNL_Y + 55),
#         ("SOFA zone",       "sofa",  PNL_Y + 91),
#         ("Delete last",     "del",   PNL_Y + 148),
#         ("Clear all",       "clear", PNL_Y + 184),
#         ("START >>>",       "start", PNL_Y + 262),
#         ("Skip (no zones)", "skip",  PNL_Y + 298),
#     ]

#     def hit(mx, my):
#         for lbl, key, by in BTNS:
#             if BX <= mx <= BX+BW and by <= my <= by+BH:
#                 return key
#         return None

#     def cb(evt, mx, my, flags, param):
#         S["mouse"] = (mx, my)

#         if evt == cv2.EVENT_MOUSEMOVE:
#             if S["drawing"] and S["p0"]:
#                 S["p1"] = (max(0, min(mx, FRAME_W-1)),
#                            max(0, min(my, FRAME_H-1)))

#         elif evt == cv2.EVENT_LBUTTONDOWN:
#             S["drawing"] = True
#             S["p0"] = (mx, my)
#             S["p1"] = (mx, my)

#         elif evt == cv2.EVENT_LBUTTONUP:
#             if S["drawing"]:
#                 S["drawing"] = False
#                 if S["p0"] and S["p1"]:
#                     x1 = min(S["p0"][0], S["p1"][0])
#                     y1 = min(S["p0"][1], S["p1"][1])
#                     x2 = max(S["p0"][0], S["p1"][0])
#                     y2 = max(S["p0"][1], S["p1"][1])
#                     if (x2-x1) > 15 and (y2-y1) > 15:
#                         k = hit(S["p0"][0], S["p0"][1])
#                         if k:
#                             _handle(k)
#                         else:
#                             S["zones"].append({"type": S["ztype"],
#                                                "box":  (x1,y1,x2,y2)})
#                             print(f"[SETUP] Zone added: {S['ztype']} "
#                                   f"({x1},{y1})-({x2},{y2})")
#                 S["p0"] = S["p1"] = None

#     def _handle(k):
#         if k == "bed":    S["ztype"] = "bed"
#         elif k == "sofa": S["ztype"] = "sofa"
#         elif k == "del":
#             if S["zones"]: S["zones"].pop()
#         elif k == "clear": S["zones"].clear()
#         elif k == "start": S["save"] = True;  S["done"] = True
#         elif k == "skip":  S["save"] = False; S["done"] = True

#     # Window — same size as detection window, single window on Windows
#     WIN_S = f"LEO Zone Setup -- {PATIENT_NAME}"
#     cv2.namedWindow(WIN_S, cv2.WINDOW_NORMAL)
#     cv2.resizeWindow(WIN_S, FRAME_W, FRAME_H)
#     cv2.setMouseCallback(WIN_S, cb)

#     # Show initial frame immediately — no black flash
#     cv2.imshow(WIN_S, bg)
#     cv2.waitKey(1)

#     while not S["done"]:
#         canvas = bg.copy()

#         # 1. Draw committed zones (semi-transparent 25% fill)
#         for z in S["zones"]:
#             x1,y1,x2,y2 = z["box"]
#             col = ZONE_COLORS[z["type"]]
#             ov  = canvas.copy()
#             cv2.rectangle(ov, (x1,y1),(x2,y2), col, -1)
#             cv2.addWeighted(ov, 0.25, canvas, 0.75, 0, canvas)
#             cv2.rectangle(canvas,(x1,y1),(x2,y2),col,2,cv2.LINE_AA)
#             lbl = z["type"].upper()
#             (tw,th),_ = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.42,1)
#             bov = canvas.copy()
#             cv2.rectangle(bov,(x1,y1),(x1+tw+8,y1+th+6),col,-1)
#             cv2.addWeighted(bov,0.75,canvas,0.25,0,canvas)
#             cv2.putText(canvas,lbl,(x1+4,y1+th+2),
#                         cv2.FONT_HERSHEY_SIMPLEX,0.42,(255,255,255),1,cv2.LINE_AA)

#         # 2. Live drag rectangle (20% fill while dragging)
#         if S["drawing"] and S["p0"] and S["p1"]:
#             col = ZONE_COLORS[S["ztype"]]
#             rx1 = min(S["p0"][0],S["p1"][0])
#             ry1 = min(S["p0"][1],S["p1"][1])
#             rx2 = max(S["p0"][0],S["p1"][0])
#             ry2 = max(S["p0"][1],S["p1"][1])
#             ov = canvas.copy()
#             cv2.rectangle(ov,(rx1,ry1),(rx2,ry2),col,-1)
#             cv2.addWeighted(ov,0.20,canvas,0.80,0,canvas)
#             cv2.rectangle(canvas,(rx1,ry1),(rx2,ry2),col,2,cv2.LINE_AA)
#             cv2.putText(canvas,f"{rx2-rx1}x{ry2-ry1}",
#                         (rx1+4,max(ry1-5,14)),
#                         cv2.FONT_HERSHEY_SIMPLEX,0.36,col,1)

#         # 3. Crosshair
#         mx,my = S["mouse"]
#         if not S["drawing"]:
#             col = ZONE_COLORS[S["ztype"]]
#             cv2.line(canvas,(mx-14,my),(mx+14,my),col,1,cv2.LINE_AA)
#             cv2.line(canvas,(mx,my-14),(mx,my+14),col,1,cv2.LINE_AA)
#             cv2.circle(canvas,(mx,my),4,col,1,cv2.LINE_AA)

#         # 4. Top instruction bar (75% opacity)
#         bar = canvas.copy()
#         cv2.rectangle(bar,(0,0),(FRAME_W,26),(8,8,14),-1)
#         cv2.addWeighted(bar,0.75,canvas,0.25,0,canvas)
#         zc  = len(S["zones"])
#         inst = (f"DRAG to draw zone  |  Type: {S['ztype'].upper()}"
#                 f"  |  Zones: {zc}  |  ENTER=start  Q=skip  D=del  TAB=switch")
#         cv2.putText(canvas,inst,(6,18),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.30,(0,220,100),1)

#         # 5. Panel overlay (72% opacity, top-right corner)
#         pov = canvas.copy()
#         cv2.rectangle(pov,(PNL_X-2, PNL_Y-2),
#                           (PNL_X+PNL_W+2, PNL_Y+PNL_H+2),(8,8,18),-1)
#         cv2.addWeighted(pov,0.72,canvas,0.28,0,canvas)
#         cv2.rectangle(canvas,(PNL_X-2,PNL_Y-2),
#                               (PNL_X+PNL_W+2,PNL_Y+PNL_H+2),(60,65,90),1)

#         cv2.putText(canvas,"LEO SETUP",(PNL_X+6,PNL_Y+20),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,210,255),1,cv2.LINE_AA)
#         cv2.putText(canvas,f"Pt: {PATIENT_NAME}",(PNL_X+6,PNL_Y+38),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.28,(100,200,100),1)
#         cv2.line(canvas,(PNL_X+4,PNL_Y+44),(PNL_X+PNL_W-4,PNL_Y+44),(45,45,65),1)
#         cv2.putText(canvas,"ZONE TYPE:",(PNL_X+6,PNL_Y+52),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

#         hov = hit(mx, my)
#         for lbl,key,by in BTNS:
#             active  = (key == S["ztype"] and key in ("bed","sofa"))
#             hovered = (hov == key)
#             if key == "start":
#                 bgc = (0,160,55) if not hovered else (0,200,70)
#                 bdc = (0,230,100)
#             elif key == "skip":
#                 bgc = (28,28,48) if not hovered else (42,42,68)
#                 bdc = (65,70,95)
#             elif key in ("del","clear"):
#                 bgc = (90,18,18) if not hovered else (120,22,22)
#                 bdc = (170,35,35)
#             elif active:
#                 bgc = ZONE_COLORS[key]
#                 bdc = (220,230,255)
#             else:
#                 bgc = (28,30,46) if not hovered else (42,45,68)
#                 bdc = (52,57,82)

#             bov2 = canvas.copy()
#             cv2.rectangle(bov2,(BX,by),(BX+BW,by+BH),bgc,-1)
#             cv2.addWeighted(bov2,0.85,canvas,0.15,0,canvas)
#             cv2.rectangle(canvas,(BX,by),(BX+BW,by+BH),bdc,1)
#             if active:
#                 cv2.circle(canvas,(BX+10,by+BH//2),4,(0,255,140),-1)
#             tw,th = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.35,1)[0]
#             cv2.putText(canvas,lbl,(BX+(BW-tw)//2,by+(BH+th)//2),
#                         cv2.FONT_HERSHEY_SIMPLEX,0.35,(225,230,255),1,cv2.LINE_AA)

#         sep_y1 = PNL_Y + 130
#         sep_y2 = PNL_Y + 248
#         cv2.line(canvas,(PNL_X+4,sep_y1),(PNL_X+PNL_W-4,sep_y1),(45,45,65),1)
#         cv2.putText(canvas,"ACTIONS:",(PNL_X+6,sep_y1+14),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)
#         cv2.line(canvas,(PNL_X+4,sep_y2),(PNL_X+PNL_W-4,sep_y2),(45,45,65),1)
#         cv2.putText(canvas,"WHEN READY:",(PNL_X+6,sep_y2+14),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

#         zcol = (0,200,80) if zc else (80,80,100)
#         cv2.putText(canvas,f"Zones: {zc}",
#                     (PNL_X+6, PNL_Y+PNL_H-10),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.32,zcol,1)

#         cv2.imshow(WIN_S, canvas)

#         k = cv2.waitKey(16) & 0xFF
#         if   k in (13, ord('s'), ord('S')): S["save"]=True;  S["done"]=True
#         elif k in (ord('q'), ord('Q')):     S["save"]=False; S["done"]=True
#         elif k in (ord('d'), ord('D')):
#             if S["zones"]: S["zones"].pop()
#         elif k in (ord('c'), ord('C')):
#             S["zones"].clear()
#         elif k == 9:
#             S["ztype"] = "sofa" if S["ztype"]=="bed" else "bed"

#     cv2.destroyWindow(WIN_S)
#     cv2.waitKey(1)

#     if S["save"] and S["zones"]:
#         save_zones(S["zones"])
#     print(f"[SETUP] {len(S['zones'])} zone(s) confirmed.")
#     return S["zones"]


# # ══════════════════════════════════════════════════════
# # DETECTION HELPERS
# # ══════════════════════════════════════════════════════

# def get_aspect_ratio(box):
#     x1,y1,x2,y2 = box
#     return max(y2-y1,1)/max(x2-x1,1)

# def get_bbox_area(box):
#     x1,y1,x2,y2 = box
#     return max(x2-x1,0)*max(y2-y1,0)

# def compute_flow_energy(gray_curr, gray_prev, box):
#     if gray_prev is None or box is None: return 0.0
#     x1=max(int(box[0]),0); y1=max(int(box[1]),0)
#     x2=min(int(box[2]),gray_curr.shape[1])
#     y2=min(int(box[3]),gray_curr.shape[0])
#     if x2<=x1+4 or y2<=y1+4: return 0.0
#     flow = cv2.calcOpticalFlowFarneback(
#         gray_prev[y1:y2,x1:x2], gray_curr[y1:y2,x1:x2], None,
#         pyr_scale=0.5,levels=2,winsize=12,iterations=2,
#         poly_n=5,poly_sigma=1.1,flags=0)
#     return float(np.mean(np.sqrt(flow[...,0]**2+flow[...,1]**2)))

# def select_main_subject(boxes_labels_confs):
#     if not boxes_labels_confs: return "none", None
#     best_label,best_box,best_area,best_conf = "none",None,-1,-1
#     for (label,box,conf) in boxes_labels_confs:
#         area=get_bbox_area(box); ar=get_aspect_ratio(box)
#         if label=="lying" and ar>LYING_ASPECT_RATIO_MAX: continue
#         if area>best_area or (area==best_area and conf>best_conf):
#             best_area,best_conf=area,conf
#             best_label,best_box=label,box
#     return best_label,best_box

# safe_zones = []

# def analyze_fall_timeline(fmc, ar_hist, pre_posture="none", current_person_box=None):
#     if current_person_box is not None and person_in_safe_zone(current_person_box, safe_zones):
#         return False, 0, "blocked:person_in_safe_zone"

#     flow_list=list(flow_history); drop_list=list(drop_history)
#     area_list=list(area_change_history); post_list=list(posture_history)
#     ar_list=list(ar_hist) if ar_hist else []
#     raw_drops=list(raw_drop_history); raw_areas=list(raw_area_history)
#     score=0; notes=[]

#     if pre_posture=="sitting":
#         if fmc>=FALL_MODEL_CONSEC: notes.append("sitting_override_by_fallmodel")
#         else: return False,0,"blocked:sitting_to_lying(sofa/bed)"

#     upright_count=sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
#                       if p in ("standing","sitting"))
#     if upright_count<MIN_UPRIGHT_FRAMES:
#         return False,0,f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

#     has_sudden_drop=any(d>=SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
#     has_sudden_area=any(a>=SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
#     if not has_sudden_drop and not has_sudden_area and fmc==0:
#         return False,0,"blocked:gradual_transition(no_spike,no_fallmodel)"

#     pre_drops=drop_list[-PRE_LYING_WINDOW:] if drop_list else []
#     max_drop=max(pre_drops) if pre_drops else 0.0
#     if   max_drop>=DROP_FAST_PX: score+=2; notes.append(f"fast_drop={max_drop:.0f}")
#     elif max_drop>=DROP_ANY_PX:  score+=1; notes.append(f"drop={max_drop:.0f}")

#     pre_area=area_list[-PRE_LYING_WINDOW:] if area_list else []
#     max_area_chg=max(pre_area) if pre_area else 0.0
#     if   max_area_chg>=AREA_CHANGE_HIGH: score+=2; notes.append(f"area_chg={max_area_chg:.2f}")
#     elif max_area_chg>=AREA_CHANGE_ANY:  score+=1; notes.append(f"area_any={max_area_chg:.2f}")

#     n=len(flow_list)
#     pre_flow=flow_list[max(0,n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
#                        max(0,n-POST_LYING_WINDOW)]
#     max_pre_flow=max(pre_flow) if pre_flow else 0.0
#     if   max_pre_flow>=FLOW_SPIKE_THRESH: score+=2; notes.append(f"flow_spike={max_pre_flow:.2f}")
#     elif max_pre_flow>=FLOW_ANY_THRESH:   score+=1; notes.append(f"flow={max_pre_flow:.2f}")

#     if len(ar_list)>=4:
#         ar_before=float(np.mean(ar_list[:max(1,len(ar_list)-PRE_LYING_WINDOW)]))
#         ar_after=float(np.mean(ar_list[-3:]))
#         ar_drop=ar_before-ar_after
#         if ar_drop>=ASPECT_DROP_THRESH: score+=2; notes.append(f"aspect_flip={ar_drop:.2f}")

#     if fmc>=FALL_MODEL_CONSEC: score+=3; notes.append(f"fall_model={fmc}f")

#     if (max_drop<DROP_ANY_PX and max_area_chg<AREA_CHANGE_ANY
#             and max_pre_flow<FLOW_ANY_THRESH):
#         return False,score,(f"blocked:no_motion(d={max_drop:.1f} "
#                             f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

#     post_flow=(flow_list[-POST_LYING_WINDOW:]
#                if len(flow_list)>=POST_LYING_WINDOW else flow_list)
#     still_ratio=sum(1 for f in post_flow if f<FLOW_STILL_THRESH)/max(len(post_flow),1)
#     if still_ratio>=0.35: score+=1; notes.append(f"still={still_ratio:.0%}")

#     reason=f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
#     if score>=FALL_SCORE_NEEDED: return True,score,f"FALL:{reason}"
#     return False,score,f"safe:{reason}"


# # ══════════════════════════════════════════════════════
# # DETECTION DISPLAY HELPERS
# # ══════════════════════════════════════════════════════

# def draw_banner(frame, state):
#     col=STATE_META.get(state,((100,100,100),"?"))[0]
#     W=frame.shape[1]
#     ov=frame.copy()
#     cv2.rectangle(ov,(0,0),(W,58),col,-1)
#     cv2.addWeighted(ov,0.55,frame,0.45,0,frame)
#     cv2.rectangle(frame,(0,0),(5,58),col,-1)
#     cv2.line(frame,(0,58),(W,58),col,1)
#     cv2.putText(frame,f"STATE:  {state}",
#                 (16,40),cv2.FONT_HERSHEY_SIMPLEX,
#                 0.95,(255,255,255),2,cv2.LINE_AA)

# def draw_signals(frame, flow_val, area_chg, drop_vel, score):
#     H,W=frame.shape[:2]
#     px,py=6,H-90; pw=192
#     ov=frame.copy()
#     cv2.rectangle(ov,(px-2,py-2),(px+pw,py+80),(12,12,18),-1)
#     cv2.addWeighted(ov,0.78,frame,0.22,0,frame)
#     cv2.rectangle(frame,(px-2,py-2),(px+pw,py+80),(50,50,70),1)
#     sigs=[("FLOW",flow_val,5.0,(0,200,255)),
#           ("AREA",area_chg,0.3,(0,180,120)),
#           ("DROP",drop_vel,20.0,(60,100,255)),
#           ("SCOR",score,FALL_SCORE_NEEDED*1.5,(0,60,255))]
#     bx=px+44; bmax=pw-52
#     for i,(lbl,val,mx,col) in enumerate(sigs):
#         y=py+6+i*18
#         bw=int(min(val/max(mx,0.001),1.0)*bmax)
#         cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(28,28,40),-1)
#         if bw>0: cv2.rectangle(frame,(bx,y+2),(bx+bw,y+12),col,-1)
#         cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(55,55,75),1)
#         cv2.putText(frame,lbl,(px,y+12),cv2.FONT_HERSHEY_SIMPLEX,0.30,(140,140,165),1)
#         cv2.putText(frame,f"{val:.1f}",(bx+bmax+3,y+12),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.27,(170,170,195),1)

# def draw_rec_indicator(frame, is_saving_clip, tick):
#     H,W=frame.shape[:2]
#     pulse = int(180 + 75 * math.sin(tick * 0.2))
#     cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
#     cv2.putText(frame, "REC", (W-45, 25),
#                 cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
#     if is_saving_clip:
#         badge = "  SAVING FALL CLIP  "
#         (bw,bh),_ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
#         bx = W - bw - 60
#         cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
#         cv2.putText(frame, badge, (bx, 30+bh+2),
#                     cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# # ══════════════════════════════════════════════════════
# # STARTUP
# # ══════════════════════════════════════════════════════
# print(f"\n[INFO] Loading saved zones for patient '{PATIENT_NAME}'...")
# safe_zones = load_zones()

# print("[INFO] Opening zone setup screen...")
# safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
# print(f"[INFO] {len(safe_zones)} zone(s) confirmed. Starting detection...\n")

# # Start video session
# video_session = VideoSession(
#     patient_name    = PATIENT_NAME,
#     fps             = 20.0,
#     frame_size      = (FRAME_W, FRAME_H),
#     save_continuous = True,
# )
# video_session.start()

# # Start MongoDB session
# if leo_db.connected:
#     leo_db.save_patient(_patient_profile)
#     leo_db.start_session(
#         patient        = PATIENT_NAME,
#         recording_path = video_session.recorder.saved_path,
#     )

# # ══════════════════════════════════════════════════════
# # STATE VARIABLES
# # ══════════════════════════════════════════════════════
# posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
# flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
# drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
# area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
# aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
# raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
# raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

# prev_gray=prev_center_y=prev_bbox_area=prev_aspect_ratio=None
# lying_consec=standing_consec=fall_model_consec=0
# frames_since_lying=0; episode_analyzed=False
# last_valid_posture="none"; posture_persist_counter=0
# fall_latch_ctr=recovery_latch_ctr=0
# final_state="STARTING"; fall_reason=""
# post_fall_lying=False; pre_lying_posture="none"
# episode_locked=False; last_upright_posture="none"
# sitting_consec_pre=0; safe_lying_locked=False
# last_known_posture="none"
# frame_count=0

# # ══════════════════════════════════════════════════════
# # MAIN DETECTION LOOP
# # ══════════════════════════════════════════════════════
# cap = cv2.VideoCapture(VIDEO_PATH)
# WIN = f"FYP Fall Detection v19 -- {PATIENT_NAME}"
# cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
# cv2.resizeWindow(WIN, FRAME_W, FRAME_H)

# def rt_mouse_cb(event, x, y, flags, param):
#     pass

# cv2.setMouseCallback(WIN, rt_mouse_cb)


# while True:
#     ret, frame = cap.read()
#     if not ret:
#         print("[INFO] Video ended.")
#         break

#     frame_count += 1
#     frame = cv2.resize(frame, (FRAME_W, FRAME_H))
#     gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

#     # FALL MODEL
#     fall_detected=False
#     for r in fall_model(frame,conf=0.5,verbose=False):
#         for box in r.boxes:
#             cls=int(box.cls[0]); label=fall_model.names[cls]
#             conf=float(box.conf[0]); x1,y1,x2,y2=map(int,box.xyxy[0])
#             if label.lower()=="fall": fall_detected=True
#             cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,180),2)
#             cv2.putText(frame,f"{label} {conf:.2f}",(x1,max(y1-8,70)),
#                         cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,0,180),1)
#     fall_model_consec=fall_model_consec+1 if fall_detected else 0

#     # POSTURE MODEL
#     all_detections=[]
#     for r in posture_model(frame,conf=0.45,verbose=False):
#         for box in r.boxes:
#             conf=float(box.conf[0]); cls=int(box.cls[0])
#             label=posture_model.names[cls].lower()
#             x1,y1,x2,y2=map(int,box.xyxy[0])
#             all_detections.append((label,(x1,y1,x2,y2),conf))
#             ar=get_aspect_ratio((x1,y1,x2,y2))
#             reject=(label=="lying" and ar>LYING_ASPECT_RATIO_MAX)
#             color=(120,120,120) if reject else (0,180,0)
#             cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
#             cv2.putText(frame,f"{label}{'[X]' if reject else ''} {conf:.2f}",
#                         (x1,max(y1-26,70)),cv2.FONT_HERSHEY_SIMPLEX,0.38,
#                         (100,100,100) if reject else (0,180,0),1)

#     raw_posture_label,person_box=select_main_subject(all_detections)
#     active_zone=person_zone(person_box,safe_zones)
#     on_safe_zone=active_zone is not None

#     if raw_posture_label!="none":
#         last_valid_posture=raw_posture_label
#         posture_persist_counter=0; posture_label=raw_posture_label
#     else:
#         posture_persist_counter+=1
#         posture_label=(last_valid_posture
#                        if posture_persist_counter<=POSTURE_PERSIST_FRAMES
#                        else "none")
#     if posture_label!="none": last_known_posture=posture_label

#     flow_energy=compute_flow_energy(gray_curr,prev_gray,person_box)
#     flow_history.append(flow_energy)
#     prev_gray=gray_curr.copy()

#     drop_velocity=0.0; area_change=0.0
#     curr_ar=prev_aspect_ratio if prev_aspect_ratio else 1.5
#     if person_box is not None:
#         x1,y1,x2,y2=person_box
#         cy=(y1+y2)/2.0; curr_ar=get_aspect_ratio(person_box)
#         curr_area=get_bbox_area(person_box)
#         if prev_center_y is not None: drop_velocity=cy-prev_center_y
#         if prev_bbox_area and prev_bbox_area>0:
#             area_change=abs(curr_area-prev_bbox_area)/prev_bbox_area
#         prev_center_y=cy; prev_bbox_area=curr_area; prev_aspect_ratio=curr_ar

#     drop_history.append(max(drop_velocity,0.0))
#     area_change_history.append(area_change)
#     aspect_ratio_history.append(curr_ar)
#     raw_drop_history.append(max(drop_velocity,0.0))
#     raw_area_history.append(area_change)

#     if fall_latch_ctr==0: posture_history.append(posture_label)

#     if lying_consec<LYING_CONFIRM_FRAMES:
#         if posture_label=="standing":
#             last_upright_posture="standing"; sitting_consec_pre=0
#         elif posture_label=="sitting":
#             sitting_consec_pre+=1
#             if sitting_consec_pre>=SITTING_CONFIRM_FOR_PREPOSTURE:
#                 last_upright_posture="sitting"
#         else: sitting_consec_pre=0

#     if posture_label=="lying":
#         lying_consec+=1; standing_consec=0
#         if lying_consec==LYING_CONFIRM_FRAMES and not episode_locked:
#             pre_lying_posture=last_upright_posture; episode_locked=True
#         if on_safe_zone and lying_consec>=LYING_CONFIRM_FRAMES and not safe_lying_locked:
#             safe_lying_locked=True
#             fall_reason=f"blocked:person_on_{active_zone['type']}(safe_zone)"
#     elif posture_label in ("standing","sitting"):
#         standing_consec+=1
#         if standing_consec>=STANDING_CONFIRM_FRAMES:
#             lying_consec=0; frames_since_lying=0; episode_analyzed=False
#             fall_reason=""; post_fall_lying=False; episode_locked=False
#             pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
#     else: standing_consec=0

#     if lying_consec>=LYING_CONFIRM_FRAMES:
#         frames_since_lying+=1
#     else:
#         if frames_since_lying>0:
#             post_fall_lying=False; episode_analyzed=False; episode_locked=False
#             pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
#         frames_since_lying=0

#     current_score=0
#     in_analysis_window=ANALYSIS_START<=frames_since_lying<=ANALYSIS_END

#     if (in_analysis_window and not episode_analyzed
#             and not safe_lying_locked and fall_latch_ctr==0):
#         is_fall,current_score,fall_reason=analyze_fall_timeline(
#             fall_model_consec,aspect_ratio_history,
#             pre_posture=pre_lying_posture,current_person_box=person_box)
#         if is_fall:
#             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
#             clip_path = video_session.on_fall()
#             print(f"[FALL] Clip saving -> {clip_path}")
#             if leo_db.connected:
#                 leo_db.log_fall(PATIENT_NAME, clip_path,
#                                 score=current_score, reason=fall_reason,
#                                 posture=posture_label, state=final_state)
#                 leo_db.log_activity(PATIENT_NAME, "fall",
#                                     f"Fall detected -- score:{current_score}",
#                                     severity="critical")
#         else: safe_lying_locked=True

#     if (fall_detected and fall_model_consec>=FALL_MODEL_CONSEC
#             and lying_consec>=LYING_CONFIRM_FRAMES
#             and not safe_lying_locked and fall_latch_ctr==0
#             and not episode_analyzed):
#         is_fall,current_score,fall_reason=analyze_fall_timeline(
#             fall_model_consec,aspect_ratio_history,
#             pre_posture=pre_lying_posture,current_person_box=person_box)
#         if is_fall:
#             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
#             clip_path = video_session.on_fall()
#             print(f"[FALL] Clip saving -> {clip_path}")
#             if leo_db.connected:
#                 leo_db.log_fall(PATIENT_NAME, clip_path,
#                                 score=current_score, reason=fall_reason,
#                                 posture=posture_label, state=final_state)
#                 leo_db.log_activity(PATIENT_NAME, "fall",
#                                     f"Fall detected -- score:{current_score}",
#                                     severity="critical")
#         else: safe_lying_locked=True

#     if (posture_label=="none" and fall_model_consec>=FALL_MODEL_CONSEC
#             and not safe_lying_locked and fall_latch_ctr==0
#             and not episode_analyzed
#             and last_known_posture in ("standing","sitting")
#             and not person_in_safe_zone(person_box,safe_zones)):
#         is_fall,current_score,fall_reason=analyze_fall_timeline(
#             fall_model_consec,aspect_ratio_history,
#             pre_posture=last_known_posture,current_person_box=person_box)
#         if is_fall:
#             fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
#             fall_reason=f"[FM-UNKNOWN] {fall_reason}"
#             clip_path = video_session.on_fall()
#             print(f"[FALL] Clip saving -> {clip_path}")
#             if leo_db.connected:
#                 leo_db.log_fall(PATIENT_NAME, clip_path,
#                                 score=current_score, reason=fall_reason,
#                                 posture=posture_label, state=final_state)
#                 leo_db.log_activity(PATIENT_NAME, "fall",
#                                     f"Fall detected -- score:{current_score}",
#                                     severity="critical")

#     if fall_latch_ctr>0 and on_safe_zone:
#         fall_latch_ctr=0; recovery_latch_ctr=0
#         post_fall_lying=False; safe_lying_locked=True
#         fall_reason="blocked:entered_safe_zone_during_latch"
#         print("[BLOCK-B] Latch cancelled -- person in safe zone")

#     if fall_latch_ctr>0:
#         fall_latch_ctr-=1; final_state="FALL"
#         if fall_latch_ctr==0: recovery_latch_ctr=RECOVERY_LATCH_FRAMES
#     elif recovery_latch_ctr>0:
#         recovery_latch_ctr-=1; final_state="RECOVERY"
#     else:
#         if posture_label=="lying":
#             if post_fall_lying: final_state="LYING (POST-FALL)"
#             elif on_safe_zone:  final_state=f"LYING (ON {active_zone['type'].upper()})"
#             else:               final_state="LYING (SAFE)"
#         elif posture_label=="standing": final_state="STANDING"
#         elif posture_label=="sitting":  final_state="SITTING"
#         else:                           final_state="UNKNOWN"

#     draw_all_zones(frame,safe_zones,active_zone)
#     draw_banner(frame,final_state)
#     draw_signals(frame,flow_energy,area_change,max(drop_velocity,0),current_score)
#     draw_rec_indicator(frame, video_session.clipper.is_saving, frame_count)

#     H,W=frame.shape[:2]
#     if on_safe_zone:
#         col=ZONE_COLORS[active_zone["type"]]
#         draw_pill_label(frame,f"ON {active_zone['type'].upper()}",W-108,88,col,scale=0.40)
#     if safe_lying_locked:
#         draw_pill_label(frame,"SAFE-LOCK",W-100,112,(30,130,60),scale=0.35)

#     selected_ar=get_aspect_ratio(person_box) if person_box else 0.0
#     dbg=(f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
#          f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
#          f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
#          f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
#          f"zone:{active_zone['type'] if active_zone else 'none'}  "
#          f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
#     cv2.putText(frame,dbg,(6,H-6),cv2.FONT_HERSHEY_SIMPLEX,0.27,(130,130,155),1)
#     if fall_reason:
#         cv2.putText(frame,fall_reason,(6,H-18),
#                     cv2.FONT_HERSHEY_SIMPLEX,0.28,(55,195,255),1)

#     # Feed the FULLY DRAWN frame (with overlays) to recorder
#     video_session.feed(frame)

#     cv2.imshow(WIN,frame)
#     key=cv2.waitKey(1)&0xFF

#     if key==ord('q'): break
#     elif key==ord('c'):
#         print("[INFO] Re-opening zone setup screen...")
#         cap.release()
#         cv2.destroyAllWindows()
#         safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
#         cap = cv2.VideoCapture(VIDEO_PATH)
#         cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
#         cv2.resizeWindow(WIN, FRAME_W, FRAME_H)
#         cv2.setMouseCallback(WIN, rt_mouse_cb)
#         print("[INFO] Resuming detection...")

# cap.release()
# cv2.destroyAllWindows()

# video_session.stop()

# if leo_db.connected:
#     leo_db.end_session(fall_count=video_session.fall_count)
#     leo_db.close()

# print("[INFO] Done.")





















"""
FYP Elderly Fall Detection — v19 (MongoDB + Transparent Setup)
===============================================================
  - Transparent zone setup screen (same size as detection window)
  - MongoDB integration for all patient data and fall events
  - Video saving: continuous recording + fall clips
  - Patient folder: data/patients/{name}/

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

import cv2
import numpy as np
from ultralytics import YOLO
import torch
from collections import deque
import os
import sys
import json
import math

# ── FYP modules ───────────────────────────────────────
from patient_storage       import PatientDirs
from video_recorder        import VideoSession
from patait_info_collector import AIBrainProfile
from mongo_storage         import leo_db
from twilio_alerts         import twilio_alerts

# ─── API PUSH to FastAPI (for Flutter live video) ──────────────────
import requests, base64, threading, queue as _queue

API_BASE    = "http://localhost:8000"   # FastAPI backend URL
_push_q     = _queue.Queue(maxsize=3)  # never block detection loop

def _api_pusher():
    """Background thread: drain queue, push frames + state to FastAPI."""
    while True:
        try:
            payload = _push_q.get(timeout=1)
            try:
                requests.post(f"{API_BASE}/video/push-frame",
                              json=payload, timeout=0.4)
            except Exception:
                pass   # backend offline — silently ignore
        except _queue.Empty:
            pass

_pusher = threading.Thread(target=_api_pusher, daemon=True, name="APIPusher")
_pusher.start()
print("[API] Frame pusher thread started → frames will stream to Flutter app")

def _push_to_api(frame, state, posture, score, fall_detected, on_safe_zone):
    """Encode annotated frame and enqueue for background push (non-blocking)."""
    try:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        b64 = base64.b64encode(buf.tobytes()).decode()
        payload = {
            "frame_b64":     b64,
            "state":         str(state),
            "posture":       str(posture),
            "fall_detected": bool(fall_detected),
            "on_safe_zone":  bool(on_safe_zone),
            "confidence":    round(min(float(score) / 4.0, 1.0), 3),
            "patient":       PATIENT_NAME,
        }
        if _push_q.full():
            try: _push_q.get_nowait()   # drop oldest, keep latest
            except _queue.Empty: pass
        _push_q.put_nowait(payload)
    except Exception:
        pass
# ───────────────────────────────────────────────────────────────────

# ══════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════
VIDEO_PATH = "D:\\Python\\FYP\\AI_Model_vision_chat\\testing_vedios\\cofeeroom_video (56).avi"
# VIDEO_PATH = 0
FRAME_W    = 640
FRAME_H    = 480

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

# ══════════════════════════════════════════════════════
# STEP 1 — PATIENT INFO COLLECTOR
# ══════════════════════════════════════════════════════
print("\n" + "="*50)
print("   LEO — AI Home Assistant for the Elderly")
print("   FYP 2024-25 | BSCS")
print("="*50)

_collector       = AIBrainProfile()
_collector.startup()
_patient_profile = _collector.get_profile()
PATIENT_NAME     = _patient_profile["personal"]["name"].lower().replace(" ", "_")

print(f"\n[INFO] Patient: {PATIENT_NAME}")
print("[INFO] Loading models...\n")

patient_dirs = PatientDirs(PATIENT_NAME)
ZONES_FILE   = str(patient_dirs.root / "safe_zones.json")

# ══════════════════════════════════════════════════════
# DETECTION PARAMETERS
# ══════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════
# COLORS & METADATA
# ══════════════════════════════════════════════════════
ZONE_COLORS = {
    "bed":  (0,   200, 255),
    "sofa": (0,   140, 255),
}
TYPE_ORDER = ["bed", "sofa"]

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

# ══════════════════════════════════════════════════════
# DEVICE + MODELS
# ══════════════════════════════════════════════════════
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Device: {device}")
print(f"[INFO] Patient: {PATIENT_NAME}")
print(f"[INFO] Data folder: {patient_dirs.root}")

fall_model    = YOLO(FALL_MODEL_PATH).to(device)
posture_model = YOLO(POSTURE_MODEL_PATH).to(device)

if isinstance(VIDEO_PATH, str) and not os.path.exists(VIDEO_PATH):
    print(f"[ERROR] Video not found: {VIDEO_PATH}")
    sys.exit(1)

# ══════════════════════════════════════════════════════
# ZONE SAVE / LOAD
# ══════════════════════════════════════════════════════

def save_zones(zones, path=ZONES_FILE):
    data = [{"type": z["type"], "box": list(z["box"])} for z in zones]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[ZONES] Saved {len(zones)} zone(s) -> {path}")


def load_zones(path=ZONES_FILE):
    if not os.path.exists(path):
        print(f"[ZONES] No saved file at {path}")
        return []
    try:
        with open(path) as f:
            data = json.load(f)
        zones = [{"type": d["type"], "box": tuple(d["box"])} for d in data]
        print(f"[ZONES] Loaded {len(zones)} zone(s)")
        return zones
    except Exception as e:
        print(f"[ZONES] Load error: {e}")
        return []


def person_zone(person_box, zones):
    if person_box is None or not zones:
        return None
    cx = (person_box[0] + person_box[2]) / 2
    cy = (person_box[1] + person_box[3]) / 2
    for z in zones:
        x1, y1, x2, y2 = z["box"]
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return z
    return None


def person_in_safe_zone(person_box, zones):
    return person_zone(person_box, zones) is not None


# ══════════════════════════════════════════════════════
# SHARED DRAW HELPERS
# ══════════════════════════════════════════════════════

def draw_pill_label(img, text, x, y, col, scale=0.40, pad=4):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), col, -1)
    cv2.rectangle(img, (x-pad, y-th-pad), (x+tw+pad, y+pad), (255,255,255), 1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255,255,255), 1, cv2.LINE_AA)


def draw_crosshair(img, x, y, size=14, col=(0,255,180)):
    cv2.line(img, (x-size, y), (x+size, y), col, 1, cv2.LINE_AA)
    cv2.line(img, (x, y-size), (x, y+size), col, 1, cv2.LINE_AA)
    cv2.circle(img, (x, y), 4, col, 1, cv2.LINE_AA)


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


# ══════════════════════════════════════════════════════
# ZONE SETUP SCREEN
# FROM DOC3: transparent overlay, same size as detection
# ══════════════════════════════════════════════════════

def run_setup_screen(video_path, existing_zones):
    """
    Transparent zone drawing startup screen.
    - Same size as detection window (FRAME_W x FRAME_H)
    - Video frame fully visible underneath (80% brightness)
    - Zones drawn as semi-transparent rectangles (25% fill)
    - Options panel is a semi-transparent overlay (top-right corner)
    - cv2.WINDOW_NORMAL + resizeWindow = single clean window on Windows
    """

    # Get background frame — NOT darkened, full visibility
    bg = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    cap_s = cv2.VideoCapture(video_path)
    if cap_s.isOpened():
        for _ in range(5):
            ret, raw = cap_s.read()
        if ret:
            bg = cv2.resize(raw, (FRAME_W, FRAME_H))
    cap_s.release()
    bg = cv2.addWeighted(bg, 0.80, np.zeros_like(bg), 0.20, 0)

    # State
    S = {
        "zones":   list(existing_zones),
        "ztype":   "bed",
        "drawing": False,
        "p0":      None,
        "p1":      None,
        "mouse":   (0, 0),
        "done":    False,
        "save":    True,
    }

    # Panel overlay position (top-right corner)
    PNL_W = 180
    PNL_H = 320
    PNL_X = FRAME_W - PNL_W - 8
    PNL_Y = 8
    BH    = 30
    BW    = PNL_W - 16
    BX    = PNL_X + 8

    # Button definitions: (label, key, y_in_canvas)
    BTNS = [
        ("BED  zone",       "bed",   PNL_Y + 55),
        ("SOFA zone",       "sofa",  PNL_Y + 91),
        ("Delete last",     "del",   PNL_Y + 148),
        ("Clear all",       "clear", PNL_Y + 184),
        ("START >>>",       "start", PNL_Y + 262),
        ("Skip (no zones)", "skip",  PNL_Y + 298),
    ]

    def hit(mx, my):
        for lbl, key, by in BTNS:
            if BX <= mx <= BX+BW and by <= my <= by+BH:
                return key
        return None

    def cb(evt, mx, my, flags, param):
        S["mouse"] = (mx, my)

        if evt == cv2.EVENT_MOUSEMOVE:
            if S["drawing"] and S["p0"]:
                S["p1"] = (max(0, min(mx, FRAME_W-1)),
                           max(0, min(my, FRAME_H-1)))

        elif evt == cv2.EVENT_LBUTTONDOWN:
            S["drawing"] = True
            S["p0"] = (mx, my)
            S["p1"] = (mx, my)

        elif evt == cv2.EVENT_LBUTTONUP:
            if S["drawing"]:
                S["drawing"] = False
                if S["p0"] and S["p1"]:
                    x1 = min(S["p0"][0], S["p1"][0])
                    y1 = min(S["p0"][1], S["p1"][1])
                    x2 = max(S["p0"][0], S["p1"][0])
                    y2 = max(S["p0"][1], S["p1"][1])
                    if (x2-x1) > 15 and (y2-y1) > 15:
                        k = hit(S["p0"][0], S["p0"][1])
                        if k:
                            _handle(k)
                        else:
                            S["zones"].append({"type": S["ztype"],
                                               "box":  (x1,y1,x2,y2)})
                            print(f"[SETUP] Zone added: {S['ztype']} "
                                  f"({x1},{y1})-({x2},{y2})")
                S["p0"] = S["p1"] = None

    def _handle(k):
        if k == "bed":    S["ztype"] = "bed"
        elif k == "sofa": S["ztype"] = "sofa"
        elif k == "del":
            if S["zones"]: S["zones"].pop()
        elif k == "clear": S["zones"].clear()
        elif k == "start": S["save"] = True;  S["done"] = True
        elif k == "skip":  S["save"] = False; S["done"] = True

    # Window — same size as detection window, single window on Windows
    WIN_S = f"LEO Zone Setup -- {PATIENT_NAME}"
    cv2.namedWindow(WIN_S, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN_S, FRAME_W, FRAME_H)
    cv2.setMouseCallback(WIN_S, cb)

    # Show initial frame immediately — no black flash
    cv2.imshow(WIN_S, bg)
    cv2.waitKey(1)

    while not S["done"]:
        canvas = bg.copy()

        # 1. Draw committed zones (semi-transparent 25% fill)
        for z in S["zones"]:
            x1,y1,x2,y2 = z["box"]
            col = ZONE_COLORS[z["type"]]
            ov  = canvas.copy()
            cv2.rectangle(ov, (x1,y1),(x2,y2), col, -1)
            cv2.addWeighted(ov, 0.25, canvas, 0.75, 0, canvas)
            cv2.rectangle(canvas,(x1,y1),(x2,y2),col,2,cv2.LINE_AA)
            lbl = z["type"].upper()
            (tw,th),_ = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.42,1)
            bov = canvas.copy()
            cv2.rectangle(bov,(x1,y1),(x1+tw+8,y1+th+6),col,-1)
            cv2.addWeighted(bov,0.75,canvas,0.25,0,canvas)
            cv2.putText(canvas,lbl,(x1+4,y1+th+2),
                        cv2.FONT_HERSHEY_SIMPLEX,0.42,(255,255,255),1,cv2.LINE_AA)

        # 2. Live drag rectangle (20% fill while dragging)
        if S["drawing"] and S["p0"] and S["p1"]:
            col = ZONE_COLORS[S["ztype"]]
            rx1 = min(S["p0"][0],S["p1"][0])
            ry1 = min(S["p0"][1],S["p1"][1])
            rx2 = max(S["p0"][0],S["p1"][0])
            ry2 = max(S["p0"][1],S["p1"][1])
            ov = canvas.copy()
            cv2.rectangle(ov,(rx1,ry1),(rx2,ry2),col,-1)
            cv2.addWeighted(ov,0.20,canvas,0.80,0,canvas)
            cv2.rectangle(canvas,(rx1,ry1),(rx2,ry2),col,2,cv2.LINE_AA)
            cv2.putText(canvas,f"{rx2-rx1}x{ry2-ry1}",
                        (rx1+4,max(ry1-5,14)),
                        cv2.FONT_HERSHEY_SIMPLEX,0.36,col,1)

        # 3. Crosshair
        mx,my = S["mouse"]
        if not S["drawing"]:
            col = ZONE_COLORS[S["ztype"]]
            cv2.line(canvas,(mx-14,my),(mx+14,my),col,1,cv2.LINE_AA)
            cv2.line(canvas,(mx,my-14),(mx,my+14),col,1,cv2.LINE_AA)
            cv2.circle(canvas,(mx,my),4,col,1,cv2.LINE_AA)

        # 4. Top instruction bar (75% opacity)
        bar = canvas.copy()
        cv2.rectangle(bar,(0,0),(FRAME_W,26),(8,8,14),-1)
        cv2.addWeighted(bar,0.75,canvas,0.25,0,canvas)
        zc  = len(S["zones"])
        inst = (f"DRAG to draw zone  |  Type: {S['ztype'].upper()}"
                f"  |  Zones: {zc}  |  ENTER=start  Q=skip  D=del  TAB=switch")
        cv2.putText(canvas,inst,(6,18),
                    cv2.FONT_HERSHEY_SIMPLEX,0.30,(0,220,100),1)

        # 5. Panel overlay (72% opacity, top-right corner)
        pov = canvas.copy()
        cv2.rectangle(pov,(PNL_X-2, PNL_Y-2),
                          (PNL_X+PNL_W+2, PNL_Y+PNL_H+2),(8,8,18),-1)
        cv2.addWeighted(pov,0.72,canvas,0.28,0,canvas)
        cv2.rectangle(canvas,(PNL_X-2,PNL_Y-2),
                              (PNL_X+PNL_W+2,PNL_Y+PNL_H+2),(60,65,90),1)

        cv2.putText(canvas,"LEO SETUP",(PNL_X+6,PNL_Y+20),
                    cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,210,255),1,cv2.LINE_AA)
        cv2.putText(canvas,f"Pt: {PATIENT_NAME}",(PNL_X+6,PNL_Y+38),
                    cv2.FONT_HERSHEY_SIMPLEX,0.28,(100,200,100),1)
        cv2.line(canvas,(PNL_X+4,PNL_Y+44),(PNL_X+PNL_W-4,PNL_Y+44),(45,45,65),1)
        cv2.putText(canvas,"ZONE TYPE:",(PNL_X+6,PNL_Y+52),
                    cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

        hov = hit(mx, my)
        for lbl,key,by in BTNS:
            active  = (key == S["ztype"] and key in ("bed","sofa"))
            hovered = (hov == key)
            if key == "start":
                bgc = (0,160,55) if not hovered else (0,200,70)
                bdc = (0,230,100)
            elif key == "skip":
                bgc = (28,28,48) if not hovered else (42,42,68)
                bdc = (65,70,95)
            elif key in ("del","clear"):
                bgc = (90,18,18) if not hovered else (120,22,22)
                bdc = (170,35,35)
            elif active:
                bgc = ZONE_COLORS[key]
                bdc = (220,230,255)
            else:
                bgc = (28,30,46) if not hovered else (42,45,68)
                bdc = (52,57,82)

            bov2 = canvas.copy()
            cv2.rectangle(bov2,(BX,by),(BX+BW,by+BH),bgc,-1)
            cv2.addWeighted(bov2,0.85,canvas,0.15,0,canvas)
            cv2.rectangle(canvas,(BX,by),(BX+BW,by+BH),bdc,1)
            if active:
                cv2.circle(canvas,(BX+10,by+BH//2),4,(0,255,140),-1)
            tw,th = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.35,1)[0]
            cv2.putText(canvas,lbl,(BX+(BW-tw)//2,by+(BH+th)//2),
                        cv2.FONT_HERSHEY_SIMPLEX,0.35,(225,230,255),1,cv2.LINE_AA)

        sep_y1 = PNL_Y + 130
        sep_y2 = PNL_Y + 248
        cv2.line(canvas,(PNL_X+4,sep_y1),(PNL_X+PNL_W-4,sep_y1),(45,45,65),1)
        cv2.putText(canvas,"ACTIONS:",(PNL_X+6,sep_y1+14),
                    cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)
        cv2.line(canvas,(PNL_X+4,sep_y2),(PNL_X+PNL_W-4,sep_y2),(45,45,65),1)
        cv2.putText(canvas,"WHEN READY:",(PNL_X+6,sep_y2+14),
                    cv2.FONT_HERSHEY_SIMPLEX,0.27,(80,85,105),1)

        zcol = (0,200,80) if zc else (80,80,100)
        cv2.putText(canvas,f"Zones: {zc}",
                    (PNL_X+6, PNL_Y+PNL_H-10),
                    cv2.FONT_HERSHEY_SIMPLEX,0.32,zcol,1)

        cv2.imshow(WIN_S, canvas)

        k = cv2.waitKey(16) & 0xFF
        if   k in (13, ord('s'), ord('S')): S["save"]=True;  S["done"]=True
        elif k in (ord('q'), ord('Q')):     S["save"]=False; S["done"]=True
        elif k in (ord('d'), ord('D')):
            if S["zones"]: S["zones"].pop()
        elif k in (ord('c'), ord('C')):
            S["zones"].clear()
        elif k == 9:
            S["ztype"] = "sofa" if S["ztype"]=="bed" else "bed"

    cv2.destroyWindow(WIN_S)
    cv2.waitKey(1)

    if S["save"] and S["zones"]:
        save_zones(S["zones"])
    print(f"[SETUP] {len(S['zones'])} zone(s) confirmed.")
    return S["zones"]


# ══════════════════════════════════════════════════════
# DETECTION HELPERS
# ══════════════════════════════════════════════════════

def get_aspect_ratio(box):
    x1,y1,x2,y2 = box
    return max(y2-y1,1)/max(x2-x1,1)

def get_bbox_area(box):
    x1,y1,x2,y2 = box
    return max(x2-x1,0)*max(y2-y1,0)

def compute_flow_energy(gray_curr, gray_prev, box):
    if gray_prev is None or box is None: return 0.0
    x1=max(int(box[0]),0); y1=max(int(box[1]),0)
    x2=min(int(box[2]),gray_curr.shape[1])
    y2=min(int(box[3]),gray_curr.shape[0])
    if x2<=x1+4 or y2<=y1+4: return 0.0
    flow = cv2.calcOpticalFlowFarneback(
        gray_prev[y1:y2,x1:x2], gray_curr[y1:y2,x1:x2], None,
        pyr_scale=0.5,levels=2,winsize=12,iterations=2,
        poly_n=5,poly_sigma=1.1,flags=0)
    return float(np.mean(np.sqrt(flow[...,0]**2+flow[...,1]**2)))

def select_main_subject(boxes_labels_confs):
    if not boxes_labels_confs: return "none", None
    best_label,best_box,best_area,best_conf = "none",None,-1,-1
    for (label,box,conf) in boxes_labels_confs:
        area=get_bbox_area(box); ar=get_aspect_ratio(box)
        if label=="lying" and ar>LYING_ASPECT_RATIO_MAX: continue
        if area>best_area or (area==best_area and conf>best_conf):
            best_area,best_conf=area,conf
            best_label,best_box=label,box
    return best_label,best_box

safe_zones = []

def analyze_fall_timeline(fmc, ar_hist, pre_posture="none", current_person_box=None):
    if current_person_box is not None and person_in_safe_zone(current_person_box, safe_zones):
        return False, 0, "blocked:person_in_safe_zone"

    flow_list=list(flow_history); drop_list=list(drop_history)
    area_list=list(area_change_history); post_list=list(posture_history)
    ar_list=list(ar_hist) if ar_hist else []
    raw_drops=list(raw_drop_history); raw_areas=list(raw_area_history)
    score=0; notes=[]

    if pre_posture=="sitting":
        if fmc>=FALL_MODEL_CONSEC: notes.append("sitting_override_by_fallmodel")
        else: return False,0,"blocked:sitting_to_lying(sofa/bed)"

    upright_count=sum(1 for p in post_list[-UPRIGHT_LOOKBACK:]
                      if p in ("standing","sitting"))
    if upright_count<MIN_UPRIGHT_FRAMES:
        return False,0,f"blocked:no_upright({upright_count}<{MIN_UPRIGHT_FRAMES})"

    has_sudden_drop=any(d>=SUDDEN_DROP_THRESH for d in raw_drops[-PRE_LYING_WINDOW:])
    has_sudden_area=any(a>=SUDDEN_AREA_THRESH  for a in raw_areas[-PRE_LYING_WINDOW:])
    if not has_sudden_drop and not has_sudden_area and fmc==0:
        return False,0,"blocked:gradual_transition(no_spike,no_fallmodel)"

    pre_drops=drop_list[-PRE_LYING_WINDOW:] if drop_list else []
    max_drop=max(pre_drops) if pre_drops else 0.0
    if   max_drop>=DROP_FAST_PX: score+=2; notes.append(f"fast_drop={max_drop:.0f}")
    elif max_drop>=DROP_ANY_PX:  score+=1; notes.append(f"drop={max_drop:.0f}")

    pre_area=area_list[-PRE_LYING_WINDOW:] if area_list else []
    max_area_chg=max(pre_area) if pre_area else 0.0
    if   max_area_chg>=AREA_CHANGE_HIGH: score+=2; notes.append(f"area_chg={max_area_chg:.2f}")
    elif max_area_chg>=AREA_CHANGE_ANY:  score+=1; notes.append(f"area_any={max_area_chg:.2f}")

    n=len(flow_list)
    pre_flow=flow_list[max(0,n-PRE_LYING_WINDOW-POST_LYING_WINDOW):
                       max(0,n-POST_LYING_WINDOW)]
    max_pre_flow=max(pre_flow) if pre_flow else 0.0
    if   max_pre_flow>=FLOW_SPIKE_THRESH: score+=2; notes.append(f"flow_spike={max_pre_flow:.2f}")
    elif max_pre_flow>=FLOW_ANY_THRESH:   score+=1; notes.append(f"flow={max_pre_flow:.2f}")

    if len(ar_list)>=4:
        ar_before=float(np.mean(ar_list[:max(1,len(ar_list)-PRE_LYING_WINDOW)]))
        ar_after=float(np.mean(ar_list[-3:]))
        ar_drop=ar_before-ar_after
        if ar_drop>=ASPECT_DROP_THRESH: score+=2; notes.append(f"aspect_flip={ar_drop:.2f}")

    if fmc>=FALL_MODEL_CONSEC: score+=3; notes.append(f"fall_model={fmc}f")

    if (max_drop<DROP_ANY_PX and max_area_chg<AREA_CHANGE_ANY
            and max_pre_flow<FLOW_ANY_THRESH):
        return False,score,(f"blocked:no_motion(d={max_drop:.1f} "
                            f"a={max_area_chg:.2f} f={max_pre_flow:.2f})")

    post_flow=(flow_list[-POST_LYING_WINDOW:]
               if len(flow_list)>=POST_LYING_WINDOW else flow_list)
    still_ratio=sum(1 for f in post_flow if f<FLOW_STILL_THRESH)/max(len(post_flow),1)
    if still_ratio>=0.35: score+=1; notes.append(f"still={still_ratio:.0%}")

    reason=f"score={score}/{FALL_SCORE_NEEDED} [{' | '.join(notes)}]"
    if score>=FALL_SCORE_NEEDED: return True,score,f"FALL:{reason}"
    return False,score,f"safe:{reason}"


# ══════════════════════════════════════════════════════
# DETECTION DISPLAY HELPERS
# ══════════════════════════════════════════════════════

def draw_banner(frame, state):
    col=STATE_META.get(state,((100,100,100),"?"))[0]
    W=frame.shape[1]
    ov=frame.copy()
    cv2.rectangle(ov,(0,0),(W,58),col,-1)
    cv2.addWeighted(ov,0.55,frame,0.45,0,frame)
    cv2.rectangle(frame,(0,0),(5,58),col,-1)
    cv2.line(frame,(0,58),(W,58),col,1)
    cv2.putText(frame,f"STATE:  {state}",
                (16,40),cv2.FONT_HERSHEY_SIMPLEX,
                0.95,(255,255,255),2,cv2.LINE_AA)

def draw_signals(frame, flow_val, area_chg, drop_vel, score):
    H,W=frame.shape[:2]
    px,py=6,H-90; pw=192
    ov=frame.copy()
    cv2.rectangle(ov,(px-2,py-2),(px+pw,py+80),(12,12,18),-1)
    cv2.addWeighted(ov,0.78,frame,0.22,0,frame)
    cv2.rectangle(frame,(px-2,py-2),(px+pw,py+80),(50,50,70),1)
    sigs=[("FLOW",flow_val,5.0,(0,200,255)),
          ("AREA",area_chg,0.3,(0,180,120)),
          ("DROP",drop_vel,20.0,(60,100,255)),
          ("SCOR",score,FALL_SCORE_NEEDED*1.5,(0,60,255))]
    bx=px+44; bmax=pw-52
    for i,(lbl,val,mx,col) in enumerate(sigs):
        y=py+6+i*18
        bw=int(min(val/max(mx,0.001),1.0)*bmax)
        cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(28,28,40),-1)
        if bw>0: cv2.rectangle(frame,(bx,y+2),(bx+bw,y+12),col,-1)
        cv2.rectangle(frame,(bx,y+2),(bx+bmax,y+12),(55,55,75),1)
        cv2.putText(frame,lbl,(px,y+12),cv2.FONT_HERSHEY_SIMPLEX,0.30,(140,140,165),1)
        cv2.putText(frame,f"{val:.1f}",(bx+bmax+3,y+12),
                    cv2.FONT_HERSHEY_SIMPLEX,0.27,(170,170,195),1)

def draw_rec_indicator(frame, is_saving_clip, tick):
    H,W=frame.shape[:2]
    pulse = int(180 + 75 * math.sin(tick * 0.2))
    cv2.circle(frame, (W-20, 20), 7, (0, 0, pulse), -1)
    cv2.putText(frame, "REC", (W-45, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 200), 1)
    if is_saving_clip:
        badge = "  SAVING FALL CLIP  "
        (bw,bh),_ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
        bx = W - bw - 60
        cv2.rectangle(frame, (bx-4, 30), (bx+bw+4, 30+bh+8), (0,0,180), -1)
        cv2.putText(frame, badge, (bx, 30+bh+2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255,255,255), 1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════
print(f"\n[INFO] Loading saved zones for patient '{PATIENT_NAME}'...")
safe_zones = load_zones()

print("[INFO] Opening zone setup screen...")
safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
print(f"[INFO] {len(safe_zones)} zone(s) confirmed. Starting detection...\n")

# Start video session
video_session = VideoSession(
    patient_name    = PATIENT_NAME,
    fps             = 20.0,
    frame_size      = (FRAME_W, FRAME_H),
    save_continuous = True,
)
video_session.start()

# Start MongoDB session
if leo_db.connected:
    leo_db.save_patient(_patient_profile)
    leo_db.start_session(
        patient        = PATIENT_NAME,
        recording_path = video_session.recorder.saved_path,
    )

# ══════════════════════════════════════════════════════
# STATE VARIABLES
# ══════════════════════════════════════════════════════
posture_history      = deque(maxlen=UPRIGHT_LOOKBACK+PRE_LYING_WINDOW+10)
flow_history         = deque(maxlen=PRE_LYING_WINDOW+POST_LYING_WINDOW+10)
drop_history         = deque(maxlen=PRE_LYING_WINDOW+10)
area_change_history  = deque(maxlen=PRE_LYING_WINDOW+10)
aspect_ratio_history = deque(maxlen=PRE_LYING_WINDOW+10)
raw_drop_history     = deque(maxlen=PRE_LYING_WINDOW+10)
raw_area_history     = deque(maxlen=PRE_LYING_WINDOW+10)

prev_gray=prev_center_y=prev_bbox_area=prev_aspect_ratio=None
lying_consec=standing_consec=fall_model_consec=0
frames_since_lying=0; episode_analyzed=False
last_valid_posture="none"; posture_persist_counter=0
fall_latch_ctr=recovery_latch_ctr=0
final_state="STARTING"; fall_reason=""
post_fall_lying=False; pre_lying_posture="none"
episode_locked=False; last_upright_posture="none"
sitting_consec_pre=0; safe_lying_locked=False
last_known_posture="none"
frame_count=0

# ══════════════════════════════════════════════════════
# MAIN DETECTION LOOP
# ══════════════════════════════════════════════════════
cap = cv2.VideoCapture(VIDEO_PATH)
WIN = f"FYP Fall Detection v19 -- {PATIENT_NAME}"
cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN, FRAME_W, FRAME_H)

def rt_mouse_cb(event, x, y, flags, param):
    pass

cv2.setMouseCallback(WIN, rt_mouse_cb)


while True:
    ret, frame = cap.read()
    if not ret:
        print("[INFO] Video ended.")
        break

    frame_count += 1
    frame = cv2.resize(frame, (FRAME_W, FRAME_H))
    gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # FALL MODEL
    fall_detected=False
    for r in fall_model(frame,conf=0.5,verbose=False):
        for box in r.boxes:
            cls=int(box.cls[0]); label=fall_model.names[cls]
            conf=float(box.conf[0]); x1,y1,x2,y2=map(int,box.xyxy[0])
            if label.lower()=="fall": fall_detected=True
            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,180),2)
            cv2.putText(frame,f"{label} {conf:.2f}",(x1,max(y1-8,70)),
                        cv2.FONT_HERSHEY_SIMPLEX,0.42,(0,0,180),1)
    fall_model_consec=fall_model_consec+1 if fall_detected else 0

    # POSTURE MODEL
    all_detections=[]
    for r in posture_model(frame,conf=0.45,verbose=False):
        for box in r.boxes:
            conf=float(box.conf[0]); cls=int(box.cls[0])
            label=posture_model.names[cls].lower()
            x1,y1,x2,y2=map(int,box.xyxy[0])
            all_detections.append((label,(x1,y1,x2,y2),conf))
            ar=get_aspect_ratio((x1,y1,x2,y2))
            reject=(label=="lying" and ar>LYING_ASPECT_RATIO_MAX)
            color=(120,120,120) if reject else (0,180,0)
            cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
            cv2.putText(frame,f"{label}{'[X]' if reject else ''} {conf:.2f}",
                        (x1,max(y1-26,70)),cv2.FONT_HERSHEY_SIMPLEX,0.38,
                        (100,100,100) if reject else (0,180,0),1)

    raw_posture_label,person_box=select_main_subject(all_detections)
    active_zone=person_zone(person_box,safe_zones)
    on_safe_zone=active_zone is not None

    if raw_posture_label!="none":
        last_valid_posture=raw_posture_label
        posture_persist_counter=0; posture_label=raw_posture_label
    else:
        posture_persist_counter+=1
        posture_label=(last_valid_posture
                       if posture_persist_counter<=POSTURE_PERSIST_FRAMES
                       else "none")
    if posture_label!="none": last_known_posture=posture_label

    flow_energy=compute_flow_energy(gray_curr,prev_gray,person_box)
    flow_history.append(flow_energy)
    prev_gray=gray_curr.copy()

    drop_velocity=0.0; area_change=0.0
    curr_ar=prev_aspect_ratio if prev_aspect_ratio else 1.5
    if person_box is not None:
        x1,y1,x2,y2=person_box
        cy=(y1+y2)/2.0; curr_ar=get_aspect_ratio(person_box)
        curr_area=get_bbox_area(person_box)
        if prev_center_y is not None: drop_velocity=cy-prev_center_y
        if prev_bbox_area and prev_bbox_area>0:
            area_change=abs(curr_area-prev_bbox_area)/prev_bbox_area
        prev_center_y=cy; prev_bbox_area=curr_area; prev_aspect_ratio=curr_ar

    drop_history.append(max(drop_velocity,0.0))
    area_change_history.append(area_change)
    aspect_ratio_history.append(curr_ar)
    raw_drop_history.append(max(drop_velocity,0.0))
    raw_area_history.append(area_change)

    if fall_latch_ctr==0: posture_history.append(posture_label)

    if lying_consec<LYING_CONFIRM_FRAMES:
        if posture_label=="standing":
            last_upright_posture="standing"; sitting_consec_pre=0
        elif posture_label=="sitting":
            sitting_consec_pre+=1
            if sitting_consec_pre>=SITTING_CONFIRM_FOR_PREPOSTURE:
                last_upright_posture="sitting"
        else: sitting_consec_pre=0

    if posture_label=="lying":
        lying_consec+=1; standing_consec=0
        if lying_consec==LYING_CONFIRM_FRAMES and not episode_locked:
            pre_lying_posture=last_upright_posture; episode_locked=True
        if on_safe_zone and lying_consec>=LYING_CONFIRM_FRAMES and not safe_lying_locked:
            safe_lying_locked=True
            fall_reason=f"blocked:person_on_{active_zone['type']}(safe_zone)"
    elif posture_label in ("standing","sitting"):
        standing_consec+=1
        if standing_consec>=STANDING_CONFIRM_FRAMES:
            lying_consec=0; frames_since_lying=0; episode_analyzed=False
            fall_reason=""; post_fall_lying=False; episode_locked=False
            pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
    else: standing_consec=0

    if lying_consec>=LYING_CONFIRM_FRAMES:
        frames_since_lying+=1
    else:
        if frames_since_lying>0:
            post_fall_lying=False; episode_analyzed=False; episode_locked=False
            pre_lying_posture="none"; sitting_consec_pre=0; safe_lying_locked=False
        frames_since_lying=0

    current_score=0
    in_analysis_window=ANALYSIS_START<=frames_since_lying<=ANALYSIS_END

    if (in_analysis_window and not episode_analyzed
            and not safe_lying_locked and fall_latch_ctr==0):
        is_fall,current_score,fall_reason=analyze_fall_timeline(
            fall_model_consec,aspect_ratio_history,
            pre_posture=pre_lying_posture,current_person_box=person_box)
        if is_fall:
            fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
            clip_path = video_session.on_fall()
            print(f"[FALL] Clip saving -> {clip_path}")
            if leo_db.connected:
                leo_db.log_fall(PATIENT_NAME, clip_path,
                                score=current_score, reason=fall_reason,
                                posture=posture_label, state=final_state)
                leo_db.log_activity(PATIENT_NAME, "fall",
                                    f"Fall detected -- score:{current_score}",
                                    severity="critical")
            # Send SMS to emergency contacts
            contacts = _patient_profile.get("emergency_contacts", [])
            twilio_alerts.send_fall_alert(
                patient   = PATIENT_NAME,
                contacts  = contacts,
                clip_path = str(clip_path),
                score     = current_score,
                posture   = posture_label,
            )
        else: safe_lying_locked=True

    if (fall_detected and fall_model_consec>=FALL_MODEL_CONSEC
            and lying_consec>=LYING_CONFIRM_FRAMES
            and not safe_lying_locked and fall_latch_ctr==0
            and not episode_analyzed):
        is_fall,current_score,fall_reason=analyze_fall_timeline(
            fall_model_consec,aspect_ratio_history,
            pre_posture=pre_lying_posture,current_person_box=person_box)
        if is_fall:
            fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
            clip_path = video_session.on_fall()
            print(f"[FALL] Clip saving -> {clip_path}")
            if leo_db.connected:
                leo_db.log_fall(PATIENT_NAME, clip_path,
                                score=current_score, reason=fall_reason,
                                posture=posture_label, state=final_state)
                leo_db.log_activity(PATIENT_NAME, "fall",
                                    f"Fall detected -- score:{current_score}",
                                    severity="critical")
        else: safe_lying_locked=True

    if (posture_label=="none" and fall_model_consec>=FALL_MODEL_CONSEC
            and not safe_lying_locked and fall_latch_ctr==0
            and not episode_analyzed
            and last_known_posture in ("standing","sitting")
            and not person_in_safe_zone(person_box,safe_zones)):
        is_fall,current_score,fall_reason=analyze_fall_timeline(
            fall_model_consec,aspect_ratio_history,
            pre_posture=last_known_posture,current_person_box=person_box)
        if is_fall:
            fall_latch_ctr=FALL_LATCH_FRAMES; episode_analyzed=True; post_fall_lying=True
            fall_reason=f"[FM-UNKNOWN] {fall_reason}"
            clip_path = video_session.on_fall()
            print(f"[FALL] Clip saving -> {clip_path}")
            if leo_db.connected:
                leo_db.log_fall(PATIENT_NAME, clip_path,
                                score=current_score, reason=fall_reason,
                                posture=posture_label, state=final_state)
                leo_db.log_activity(PATIENT_NAME, "fall",
                                    f"Fall detected -- score:{current_score}",
                                    severity="critical")

    if fall_latch_ctr>0 and on_safe_zone:
        fall_latch_ctr=0; recovery_latch_ctr=0
        post_fall_lying=False; safe_lying_locked=True
        fall_reason="blocked:entered_safe_zone_during_latch"
        print("[BLOCK-B] Latch cancelled -- person in safe zone")

    if fall_latch_ctr>0:
        fall_latch_ctr-=1; final_state="FALL"
        if fall_latch_ctr==0: recovery_latch_ctr=RECOVERY_LATCH_FRAMES
    elif recovery_latch_ctr>0:
        recovery_latch_ctr-=1; final_state="RECOVERY"
    else:
        if posture_label=="lying":
            if post_fall_lying: final_state="LYING (POST-FALL)"
            elif on_safe_zone:  final_state=f"LYING (ON {active_zone['type'].upper()})"
            else:               final_state="LYING (SAFE)"
        elif posture_label=="standing": final_state="STANDING"
        elif posture_label=="sitting":  final_state="SITTING"
        else:                           final_state="UNKNOWN"

    draw_all_zones(frame,safe_zones,active_zone)
    draw_banner(frame,final_state)
    draw_signals(frame,flow_energy,area_change,max(drop_velocity,0),current_score)
    draw_rec_indicator(frame, video_session.clipper.is_saving, frame_count)

    H,W=frame.shape[:2]
    if on_safe_zone:
        col=ZONE_COLORS[active_zone["type"]]
        draw_pill_label(frame,f"ON {active_zone['type'].upper()}",W-108,88,col,scale=0.40)
    if safe_lying_locked:
        draw_pill_label(frame,"SAFE-LOCK",W-100,112,(30,130,60),scale=0.35)

    selected_ar=get_aspect_ratio(person_box) if person_box else 0.0
    dbg=(f"p:{posture_label}  ar:{selected_ar:.2f}  ly:{lying_consec}  "
         f"fs:{frames_since_lying}  drop:{drop_velocity:.1f}  "
         f"area:{area_change:.2f}  flow:{flow_energy:.2f}  "
         f"fm:{fall_model_consec}  latch:{fall_latch_ctr}  "
         f"zone:{active_zone['type'] if active_zone else 'none'}  "
         f"sl:{safe_lying_locked}  pre:{pre_lying_posture}")
    cv2.putText(frame,dbg,(6,H-6),cv2.FONT_HERSHEY_SIMPLEX,0.27,(130,130,155),1)
    if fall_reason:
        cv2.putText(frame,fall_reason,(6,H-18),
                    cv2.FONT_HERSHEY_SIMPLEX,0.28,(55,195,255),1)

    # Feed the FULLY DRAWN frame (with overlays) to recorder
    video_session.feed(frame)

    # ── Push to FastAPI so Flutter app gets live video ──────────────
    # Runs every frame but pushes are non-blocking (background thread)
    _push_to_api(
        frame        = frame,
        state        = final_state,
        posture      = posture_label,
        score        = current_score,
        fall_detected= (fall_latch_ctr > 0),
        on_safe_zone = on_safe_zone,
    )
    # ────────────────────────────────────────────────────────────────

    cv2.imshow(WIN,frame)
    key=cv2.waitKey(1)&0xFF

    if key==ord('q'): break
    elif key==ord('c'):
        print("[INFO] Re-opening zone setup screen...")
        cap.release()
        cv2.destroyAllWindows()
        safe_zones = run_setup_screen(VIDEO_PATH, safe_zones)
        cap = cv2.VideoCapture(VIDEO_PATH)
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN, FRAME_W, FRAME_H)
        cv2.setMouseCallback(WIN, rt_mouse_cb)
        print("[INFO] Resuming detection...")

cap.release()
cv2.destroyAllWindows()

video_session.stop()

if leo_db.connected:
    leo_db.end_session(fall_count=video_session.fall_count)
    leo_db.close()

print("[INFO] Done.")