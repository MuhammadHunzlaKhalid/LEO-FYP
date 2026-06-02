"""
LEO — Video Recorder with Fall Clip Auto-Save
===============================================
Handles two types of video saving:

  1. CONTINUOUS RECORDING
     • Records the full session as one .avi file
     • Saved under:  data/patients/{name}/videos/{date}/recording_{time}.avi

  2. FALL CLIP AUTO-SAVE
     • Keeps a rolling buffer of the last PRE_FALL_SECONDS
     • When a fall is detected, flushes buffer + records POST_FALL_SECONDS more
     • Saved under:  data/patients/{name}/videos/{date}/fall_{time}.avi

FYP 2024-25 | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti
Supervisor: Dr. Zia Ul Rehman
"""

from __future__ import annotations

import collections
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from patient_storage import PatientDirs


# ═══════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════
PRE_FALL_SECONDS  = 10   # seconds of footage BEFORE fall to save
POST_FALL_SECONDS = 10   # seconds of footage AFTER fall to save
FOURCC            = cv2.VideoWriter_fourcc(*"XVID")
DEFAULT_FPS       = 20.0
FRAME_SIZE        = (640, 480)


# ═══════════════════════════════════════════════════════
#  CONTINUOUS RECORDER
# ═══════════════════════════════════════════════════════
class ContinuousRecorder:
    """
    Records every frame to a single .avi file for the session.
    Call start() once, write_frame() for every frame, stop() at end.
    """

    def __init__(
        self,
        patient_name: str,
        fps: float = DEFAULT_FPS,
        frame_size: tuple = FRAME_SIZE,
    ):
        self.pd         = PatientDirs(patient_name)
        self.fps        = fps
        self.frame_size = frame_size
        self._writer: Optional[cv2.VideoWriter] = None
        self._path: Optional[Path] = None
        self._frame_count = 0

    def start(self) -> Path:
        """Open the video writer. Returns the file path."""
        self._path   = self.pd.new_recording_path()
        self._writer = cv2.VideoWriter(
            str(self._path), FOURCC, self.fps, self.frame_size
        )
        if not self._writer.isOpened():
            raise RuntimeError(f"[Recorder] Cannot open writer at {self._path}")
        self._frame_count = 0
        print(f"[Recorder] ▶ Recording started → {self._path}")
        return self._path

    def write_frame(self, frame: np.ndarray):
        """Write one frame. Resizes automatically if needed."""
        if self._writer is None:
            return
        if frame.shape[1] != self.frame_size[0] or frame.shape[0] != self.frame_size[1]:
            frame = cv2.resize(frame, self.frame_size)
        self._writer.write(frame)
        self._frame_count += 1

    def stop(self) -> Optional[Path]:
        """Flush and close the writer."""
        if self._writer:
            self._writer.release()
            self._writer = None
            print(
                f"[Recorder] ■ Recording stopped → {self._path} "
                f"({self._frame_count} frames)"
            )
        return self._path

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    @property
    def saved_path(self) -> Optional[Path]:
        return self._path


# ═══════════════════════════════════════════════════════
#  FALL CLIP SAVER  (circular buffer)
# ═══════════════════════════════════════════════════════
class FallClipSaver:
    """
    Maintains a circular buffer of the last N seconds of frames.
    When trigger_fall() is called:
      - Saves the buffered pre-fall frames
      - Keeps recording for POST_FALL_SECONDS more
      - Closes the clip file automatically

    Thread-safe via a lock.
    """

    def __init__(
        self,
        patient_name: str,
        fps: float = DEFAULT_FPS,
        frame_size: tuple = FRAME_SIZE,
        pre_seconds: int = PRE_FALL_SECONDS,
        post_seconds: int = POST_FALL_SECONDS,
    ):
        self.pd           = PatientDirs(patient_name)
        self.fps          = fps
        self.frame_size   = frame_size
        self.pre_seconds  = pre_seconds
        self.post_seconds = post_seconds

        # Circular buffer — holds (pre_seconds × fps) frames
        buf_size       = int(pre_seconds * fps)
        self._buffer   = collections.deque(maxlen=buf_size)
        self._lock     = threading.Lock()

        # Clip writer state
        self._writer:      Optional[cv2.VideoWriter] = None
        self._clip_path:   Optional[Path]            = None
        self._post_frames_remaining = 0
        self._saving = False

    def feed_frame(self, frame: np.ndarray):
        """
        Call this for EVERY frame (even when no fall is happening).
        Feeds the circular buffer and, if a fall was triggered,
        also writes to the clip file.
        """
        if frame.shape[1] != self.frame_size[0] or frame.shape[0] != self.frame_size[1]:
            frame = cv2.resize(frame, self.frame_size)

        frame_copy = frame.copy()

        with self._lock:
            self._buffer.append(frame_copy)

            if self._saving and self._writer:
                self._writer.write(frame_copy)
                self._post_frames_remaining -= 1
                if self._post_frames_remaining <= 0:
                    self._close_clip()

    def trigger_fall(self) -> Optional[Path]:
        """
        Call this when a fall is detected.
        Flushes the pre-fall buffer to a new clip file and
        continues recording for POST_FALL_SECONDS.
        Returns the clip path (or None if already saving).
        """
        with self._lock:
            if self._saving:
                # Already saving a clip — don't start another
                return self._clip_path

            self._clip_path = self.pd.new_fall_clip_path()
            self._writer    = cv2.VideoWriter(
                str(self._clip_path), FOURCC, self.fps, self.frame_size
            )
            if not self._writer.isOpened():
                print(f"[FallClip] ✗ Cannot open writer at {self._clip_path}")
                self._writer = None
                return None

            # Write buffered pre-fall frames
            pre_frames = list(self._buffer)
            for f in pre_frames:
                self._writer.write(f)

            self._post_frames_remaining = int(self.post_seconds * self.fps)
            self._saving = True

            print(
                f"[FallClip] 🎥 FALL CLIP saving → {self._clip_path} "
                f"({len(pre_frames)} pre-frames + {self.post_seconds}s post)"
            )
            return self._clip_path

    def _close_clip(self):
        """Internal — must be called with self._lock held."""
        if self._writer:
            self._writer.release()
            self._writer = None
        self._saving = False
        self._post_frames_remaining = 0
        print(f"[FallClip] ✅ Fall clip saved → {self._clip_path}")

    def force_close(self):
        """Force-close any open clip (call on app shutdown)."""
        with self._lock:
            if self._saving:
                self._close_clip()

    @property
    def is_saving(self) -> bool:
        return self._saving

    @property
    def last_clip_path(self) -> Optional[Path]:
        return self._clip_path


# ═══════════════════════════════════════════════════════
#  COMBINED SESSION  (easy one-object interface)
# ═══════════════════════════════════════════════════════
class VideoSession:
    """
    One object that manages BOTH the continuous recorder
    and the fall clip saver for a patient session.

    Usage:
        session = VideoSession("ahmed")
        session.start()

        for frame in camera:
            session.feed(frame)            # every frame
            if fall_detected:
                session.on_fall()          # saves clip automatically

        session.stop()
    """

    def __init__(
        self,
        patient_name: str,
        fps: float = DEFAULT_FPS,
        frame_size: tuple = FRAME_SIZE,
        save_continuous: bool = True,
    ):
        self.patient_name    = patient_name
        self.save_continuous = save_continuous

        self.recorder = ContinuousRecorder(patient_name, fps, frame_size)
        self.clipper  = FallClipSaver(patient_name, fps, frame_size)

        self._fall_count = 0
        self._start_time: Optional[float] = None

    def start(self):
        """Begin the session."""
        self._start_time = time.time()
        if self.save_continuous:
            self.recorder.start()
        print(
            f"[VideoSession] ▶ Session started for patient '{self.patient_name}'"
        )

    def feed(self, frame: np.ndarray):
        """Feed every camera frame here."""
        if self.save_continuous and self.recorder.is_recording:
            self.recorder.write_frame(frame)
        self.clipper.feed_frame(frame)

    def on_fall(self) -> Optional[Path]:
        """Call when fall is detected. Returns clip path."""
        self._fall_count += 1
        clip_path = self.clipper.trigger_fall()
        return clip_path

    def stop(self):
        """End the session and close all writers."""
        self.clipper.force_close()
        rec_path = self.recorder.stop() if self.save_continuous else None
        elapsed  = time.time() - self._start_time if self._start_time else 0

        print(
            f"\n[VideoSession] ■ Session ended for '{self.patient_name}'\n"
            f"   Duration  : {elapsed / 60:.1f} min\n"
            f"   Falls     : {self._fall_count}\n"
            f"   Recording : {rec_path}\n"
        )

    @property
    def fall_count(self) -> int:
        return self._fall_count


# ═══════════════════════════════════════════════════════
#  STANDALONE TEST  (run: python video_recorder.py)
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    patient = sys.argv[1] if len(sys.argv) > 1 else "test_patient"
    src     = int(sys.argv[2]) if len(sys.argv) > 2 else 0   # 0 = webcam

    print(f"\n=== VideoSession test | patient={patient} | src={src} ===\n")

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print("[ERROR] Cannot open video source")
        sys.exit(1)

    session = VideoSession(patient, fps=20.0)
    session.start()

    print("Press F to simulate FALL, Q to quit")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (640, 480))
        session.feed(frame)

        # Show status
        overlay = frame.copy()
        cv2.putText(overlay,
                    f"Falls: {session.fall_count}   "
                    f"Clip saving: {session.clipper.is_saving}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 100) if not session.clipper.is_saving else (0, 0, 255),
                    2)
        cv2.imshow("VideoSession Test", overlay)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key in (ord('f'), ord('F')):
            clip = session.on_fall()
            print(f"[TEST] Fall triggered → {clip}")

    cap.release()
    cv2.destroyAllWindows()
    session.stop()
