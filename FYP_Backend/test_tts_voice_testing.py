# # ═══════════════════════════════════════════════════════════════════
# # SECTION 7C — VOICE OUTPUT  (Kokoro ONNX TTS)
# # Leo speaks responses aloud using Kokoro ONNX text-to-speech
# #
# # Requires:
# #   pip install kokoro-onnx soundfile
# #   pip install python-vlc   (or sounddevice / pygame as fallback)
# #
# # Model files (auto-downloaded on first run, ~310 MB total):
# #   kokoro-v1.0.onnx   → from thewh1teagle/kokoro-onnx releases
# #   voices-v1.0.bin    → from thewh1teagle/kokoro-onnx releases
# #
# # Files are saved next to leo.py so they only download once.
# # ═══════════════════════════════════════════════════════════════════

# try:
#     from kokoro_onnx import Kokoro as _KokoroOnnx
#     import soundfile as _sf
#     KOKORO_AVAILABLE = True
# except ImportError:
#     KOKORO_AVAILABLE = False
#     print("[TTS] kokoro-onnx or soundfile not installed.")
#     print("      Fix:  pip install kokoro-onnx soundfile")


# class VoiceOutput:
#     """
#     Kokoro ONNX TTS — Leo speaks responses aloud.

#     Model files are auto-downloaded next to leo.py on first run.

#     Available voices:
#       af_heart, af_bella, af_nicole, af_nova, af_river,
#       af_sarah, af_sky, af_alloy, af_aoede, af_jessica,
#       af_kore, am_adam, am_echo, am_michael,
#       bf_emma, bf_isabella, bm_george, bm_lewis
#     """

#     VOICE       = "af_heart"
#     SPEED       = 1.0
#     LANG        = "en-us"

#     MODEL_URL  = ("https://github.com/thewh1teagle/kokoro-onnx/releases/"
#                   "download/model-files-v1.0/kokoro-v1.0.onnx")
#     VOICES_URL = ("https://github.com/thewh1teagle/kokoro-onnx/releases/"
#                   "download/model-files-v1.0/voices-v1.0.bin")

#     MODEL_FILE  = BASE_DIR / "kokoro-v1.0.onnx"
#     VOICES_FILE = BASE_DIR / "voices-v1.0.bin"

#     def __init__(self):
#         self.available      = KOKORO_AVAILABLE
#         self._kokoro        = None
#         self._audio_backend = None

#         if not self.available:
#             print("[TTS] kokoro-onnx not installed — text only.")
#             print("      Fix:  pip install kokoro-onnx soundfile")
#             return

#         try:
#             self._ensure_model_files()
#             print("[TTS] Loading Kokoro ONNX model...")
#             self._kokoro = _KokoroOnnx(str(self.MODEL_FILE), str(self.VOICES_FILE))
#             print(f"[TTS] Ready — voice: {self.VOICE}")
#         except Exception as e:
#             print(f"[TTS] Kokoro ONNX load failed: {e}")
#             self.available = False
#             return

#         self._audio_backend = self._detect_backend()

#     def _ensure_model_files(self):
#         """Download model and voices files if they don't exist yet."""
#         import urllib.request

#         if not self.MODEL_FILE.exists():
#             print("[TTS] Downloading kokoro-v1.0.onnx (~300 MB)...")
#             urllib.request.urlretrieve(self.MODEL_URL, str(self.MODEL_FILE))
#             print("[TTS] Model downloaded.")

#         if not self.VOICES_FILE.exists():
#             print("[TTS] Downloading voices-v1.0.bin (~10 MB)...")
#             urllib.request.urlretrieve(self.VOICES_URL, str(self.VOICES_FILE))
#             print("[TTS] Voices downloaded.")

#     def _detect_backend(self) -> str:
#         """
#         Try each audio playback method in order.
#         Returns the name of the working backend (or 'none').
#         """
#         import numpy as np

#         test_audio  = np.zeros(2400, dtype=np.float32)
#         sample_rate = 24000

#         # 1. sounddevice
#         try:
#             import sounddevice as _sd
#             _sd.play(test_audio, sample_rate)
#             _sd.wait()
#             print("[TTS] Audio backend: sounddevice ✓")
#             return "sounddevice"
#         except Exception as e:
#             print(f"[TTS] sounddevice unavailable: {e}")

#         # 2. VLC  (your confirmed-working backend)
#         try:
#             import vlc as _vlc
#             _vlc.Instance()
#             print("[TTS] Audio backend: VLC ✓")
#             return "vlc"
#         except Exception as e:
#             print(f"[TTS] VLC unavailable: {e}")

#         # 3. pygame
#         try:
#             import pygame
#             pygame.mixer.init(frequency=sample_rate, size=-16, channels=1, buffer=512)
#             pygame.mixer.quit()
#             print("[TTS] Audio backend: pygame ✓")
#             return "pygame"
#         except Exception as e:
#             print(f"[TTS] pygame unavailable: {e}")

#         # 4. winsound (Windows only)
#         try:
#             import winsound
#             print("[TTS] Audio backend: winsound ✓")
#             return "winsound"
#         except Exception as e:
#             print(f"[TTS] winsound unavailable: {e}")

#         # 5. playsound
#         try:
#             from playsound import playsound  # noqa: F401
#             print("[TTS] Audio backend: playsound ✓")
#             return "playsound"
#         except Exception as e:
#             print(f"[TTS] playsound unavailable: {e}")

#         print("[TTS] ⚠ NO AUDIO BACKEND FOUND — voice output disabled.")
#         print("      Fix: pip install sounddevice   or   pip install python-vlc")
#         return "none"

#     def speak(self, text: str):
#         """
#         Generate speech with Kokoro ONNX, save to temp WAV, play it.
#         kokoro_onnx.create() returns (samples_np_array, sample_rate).
#         """
#         if not self.available or not self._kokoro or not text:
#             return

#         try:
#             samples, sample_rate = self._kokoro.create(
#                 text  = text,
#                 voice = self.VOICE,
#                 speed = self.SPEED,
#                 lang  = self.LANG,
#             )

#             # Write to a temp WAV using soundfile
#             tmp_path = os.path.join(tempfile.gettempdir(), "leo_tts_out.wav")
#             _sf.write(tmp_path, samples, sample_rate)

#             self._play_wav(tmp_path)

#         except Exception as e:
#             print(f"[TTS] Speak error: {e}")
#             import traceback; traceback.print_exc()

#     def _play_wav(self, wav_path: str):
#         """Play a WAV file using the detected backend, with fallback chain."""
#         backend = self._audio_backend or "vlc"

#         # ── 1. sounddevice ────────────────────────────────────────────────────
#         if backend == "sounddevice":
#             try:
#                 import sounddevice as _sd
#                 data, sr = _sf.read(wav_path, dtype="float32")
#                 _sd.play(data, sr)
#                 _sd.wait()
#                 self._cleanup(wav_path)
#                 return
#             except Exception as e:
#                 print(f"[TTS] sounddevice playback failed: {e}")
#                 self._audio_backend = "vlc"

#         # ── 2. VLC ────────────────────────────────────────────────────────────
#         if self._audio_backend in ("vlc", "sounddevice") or backend == "vlc":
#             try:
#                 import vlc as _vlc, time
#                 player = _vlc.MediaPlayer(wav_path)
#                 player.play()
#                 time.sleep(0.3)
#                 while True:
#                     state = player.get_state()
#                     if state in [_vlc.State.Ended, _vlc.State.Stopped,
#                                  _vlc.State.Error]:
#                         break
#                     time.sleep(0.1)
#                 player.stop()
#                 self._cleanup(wav_path)
#                 return
#             except Exception as e:
#                 print(f"[TTS] VLC playback failed: {e}")
#                 self._audio_backend = "pygame"

#         # ── 3. pygame ─────────────────────────────────────────────────────────
#         if self._audio_backend in ("pygame", "vlc", "sounddevice"):
#             try:
#                 import pygame, time
#                 data, sr = _sf.read(wav_path, dtype="int16")
#                 if not pygame.mixer.get_init():
#                     pygame.mixer.init(frequency=sr, size=-16, channels=1, buffer=1024)
#                 sound   = pygame.mixer.Sound(wav_path)
#                 channel = sound.play()
#                 while channel.get_busy():
#                     time.sleep(0.05)
#                 self._cleanup(wav_path)
#                 return
#             except Exception as e:
#                 print(f"[TTS] pygame playback failed: {e}")
#                 self._audio_backend = "winsound"

#         # ── 4. winsound ───────────────────────────────────────────────────────
#         try:
#             import winsound
#             winsound.PlaySound(wav_path, winsound.SND_FILENAME)
#             self._cleanup(wav_path)
#             return
#         except Exception as e:
#             print(f"[TTS] winsound playback failed: {e}")
#             self._audio_backend = "playsound"

#         # ── 5. playsound ──────────────────────────────────────────────────────
#         try:
#             from playsound import playsound
#             playsound(wav_path)
#             self._cleanup(wav_path)
#             return
#         except Exception as e:
#             print(f"[TTS] playsound failed: {e}")

#         print("[TTS] ⚠ All audio backends failed.")
#         print("      Fix:  pip install python-vlc   or   pip install sounddevice")

#     @staticmethod
#     def _cleanup(path: str):
#         try:
#             os.unlink(path)
#         except Exception:
#             pass

#     def stop(self):
#         """Best-effort stop of any currently playing audio."""
#         try:
#             import sounddevice as _sd
#             _sd.stop()
#         except Exception:
#             pass
#         try:
#             import pygame
#             if pygame.mixer.get_init():
#                 pygame.mixer.stop()
#         except Exception:
#             pass
        
        
        
        
import sounddevice as sd
import numpy as np
from kokoro_onnx import Kokoro

kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
samples, sample_rate = kokoro.create("Hello Ali, this is a test", voice="af_heart", speed=1.0, lang="en-us")
sd.play(samples, sample_rate)
sd.wait()






"""
audio.py — Leo TTS Voice Output using kokoro-onnx
FYP Project | Hunzla Khalid, Ayesha Abaidullah, Shaiq Bhatti

Uses kokoro_onnx (ONNX runtime) for fast, offline text-to-speech.
Requires:
    pip install kokoro-onnx sounddevice numpy
    # Model files (place next to this file):
    #   kokoro-v1.0.onnx    (~300 MB)
    #   voices-v1.0.bin     (~10 MB)
    # Download from: https://github.com/thewh1teagle/kokoro-onnx/releases

Voices (en-us):
    af_heart, af_bella, af_nicole, af_nova,
    af_river, af_sarah, af_sky, af_alloy,
    am_adam, am_echo, am_michael
British (en-gb):
    bf_emma, bf_isabella, bm_george, bm_lewis
"""

import os
import time
import tempfile
import numpy as np
from pathlib import Path

# ── kokoro-onnx ───────────────────────────────────────────────────
try:
    from kokoro_onnx import Kokoro as _KokoroOnnx
    KOKORO_ONNX_AVAILABLE = True
except ImportError:
    KOKORO_ONNX_AVAILABLE = False
    print("[TTS] kokoro-onnx not installed. Run:  pip install kokoro-onnx")

# ── sounddevice ───────────────────────────────────────────────────
try:
    import sounddevice as _sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("[TTS] sounddevice not installed. Run:  pip install sounddevice")


# ── Model file paths ──────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
ONNX_MODEL = BASE_DIR / "kokoro-v1.0.onnx"
VOICES_BIN = BASE_DIR / "voices-v1.0.bin"


class VoiceOutput:
    """
    Leo's voice output module using kokoro-onnx.

    Quick usage:
        tts = VoiceOutput()
        tts.speak("Hello! I am Leo, your home assistant.")

    Change voice/speed at runtime:
        tts.voice = "am_adam"
        tts.speed = 1.1
    """

    # ── Defaults ─────────────────────────────────────────────────
    DEFAULT_VOICE = "af_heart"   # warm female American English
    DEFAULT_SPEED = 1.0
    DEFAULT_LANG  = "en-us"      # "en-gb" for British voices

    def __init__(
        self,
        onnx_path: str | Path = ONNX_MODEL,
        voices_path: str | Path = VOICES_BIN,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
        lang: str = DEFAULT_LANG,
    ):
        self.voice = voice
        self.speed = speed
        self.lang  = lang

        self.available = False
        self._kokoro   = None

        # Check dependencies
        if not KOKORO_ONNX_AVAILABLE:
            print("[TTS] kokoro-onnx missing — voice output disabled.")
            print("      Fix: pip install kokoro-onnx")
            return

        if not SOUNDDEVICE_AVAILABLE:
            print("[TTS] sounddevice missing — voice output disabled.")
            print("      Fix: pip install sounddevice")
            return

        # Check model files
        onnx_path   = Path(onnx_path)
        voices_path = Path(voices_path)

        if not onnx_path.exists():
            print(f"[TTS] Model file not found: {onnx_path}")
            print("      Download from: https://github.com/thewh1teagle/kokoro-onnx/releases")
            return

        if not voices_path.exists():
            print(f"[TTS] Voices file not found: {voices_path}")
            print("      Download from: https://github.com/thewh1teagle/kokoro-onnx/releases")
            return

        # Load model
        try:
            print(f"[TTS] Loading kokoro-onnx model...")
            self._kokoro   = _KokoroOnnx(str(onnx_path), str(voices_path))
            self.available = True
            print(f"[TTS] Ready — voice: {self.voice}, lang: {self.lang}")
        except Exception as e:
            print(f"[TTS] Failed to load model: {e}")

    # ── Public API ────────────────────────────────────────────────

    def speak(self, text: str):
        """
        Synthesise text and play it immediately (blocking until done).
        Silently skips if TTS is unavailable.
        """
        if not self.available or not text or not text.strip():
            return

        try:
            samples, sample_rate = self._kokoro.create(
                text,
                voice=self.voice,
                speed=self.speed,
                lang=self.lang,
            )
            _sd.play(samples, sample_rate)
            _sd.wait()
        except Exception as e:
            print(f"[TTS] Speak error: {e}")

    def speak_async(self, text: str):
        """
        Synthesise and play in a background thread — non-blocking.
        Returns immediately; audio plays in the background.
        """
        import threading
        t = threading.Thread(target=self.speak, args=(text,), daemon=True)
        t.start()

    def stop(self):
        """Stop any currently playing audio immediately."""
        if SOUNDDEVICE_AVAILABLE:
            try:
                _sd.stop()
            except Exception:
                pass

    def set_voice(self, voice: str, lang: str = None):
        """
        Change voice at runtime.
        Example:
            tts.set_voice("am_adam")
            tts.set_voice("bm_george", lang="en-gb")
        """
        self.voice = voice
        if lang:
            self.lang = lang
        print(f"[TTS] Voice changed → {self.voice} ({self.lang})")

    def list_voices(self) -> list[str]:
        """Return common available voice IDs."""
        return [
            # American English (en-us)
            "af_heart", "af_bella", "af_nicole", "af_nova",
            "af_river", "af_sarah", "af_sky", "af_alloy",
            "am_adam",  "am_echo",  "am_michael",
            # British English (en-gb)
            "bf_emma",  "bf_isabella", "bm_george", "bm_lewis",
        ]


# ═══════════════════════════════════════════════════════════════════
# Quick test — run this file directly to verify everything works
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n[Test] Initialising Leo TTS...")
    tts = VoiceOutput()

    if not tts.available:
        print("\n[Test] TTS not available — check errors above.")
    else:
        print("\n[Test] Speaking test phrase...\n")
        tts.speak("Hello! I am Leo, your home assistant. How are you feeling today?")

        print("\n[Test] Trying a different voice (am_adam)...")
        tts.set_voice("am_adam")
        tts.speak("This is Adam's voice. Leo can use any of these voices.")

        print("\n[Test] Done. TTS is working correctly.")