import os
import threading
import wave
import numpy as np
import sounddevice as sd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BEEP_UP_PATH = os.path.join(BASE_DIR, "beep_up.wav")
BEEP_DOWN_PATH = os.path.join(BASE_DIR, "beep_down.wav")


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio array using linear interpolation."""

    if orig_sr == target_sr:
        return audio
    num_samples = int(len(audio) * target_sr / orig_sr)
    indices = np.linspace(0, len(audio) - 1, num_samples)
    if audio.ndim == 1:
        return np.interp(indices, np.arange(len(audio)), audio)
    else:
        resampled = np.zeros((num_samples, audio.shape[1]), dtype=audio.dtype)
        x_orig = np.arange(len(audio))
        for ch in range(audio.shape[1]):
            resampled[:, ch] = np.interp(indices, x_orig, audio[:, ch])
        return resampled


def _play_wav(file_path: str, volume: float = 0.40):
    """Play WAV file asynchronously with 40% volume and full buffer wait."""
    def run():
        try:
            if not os.path.exists(file_path):
                return

            with wave.open(file_path, "rb") as wf:
                framerate = wf.getframerate()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                frames = wf.readframes(wf.getnframes())

                dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
                dtype = dtype_map.get(sampwidth, np.int16)
                raw_data = np.frombuffer(
                    frames, dtype=dtype).astype(np.float32)

                if sampwidth == 2:
                    raw_data /= 32768.0
                elif sampwidth == 1:
                    raw_data = (raw_data - 128.0) / 128.0
                elif sampwidth == 4:
                    raw_data /= 2147483648.0

                if nchannels > 1:
                    raw_data = raw_data.reshape(-1, nchannels)

                # Scaled volume to 40%
                audio_data = raw_data * volume

                # Use 48000 Hz resampling for Linux audio server compatibility
                target_sr = 48000 if framerate == 44100 else framerate
                audio_data = _resample(audio_data, framerate, target_sr)

                sd.play(audio_data, samplerate=target_sr)
                sd.wait()
        except Exception as e:
            print(
                f"[AudioCues] Error playing WAV {file_path}: {e}", flush=True)

    threading.Thread(target=run, daemon=True).start()


def play_start_sound():
    """Play beep_up.wav at 40% volume (start recording)."""
    _play_wav(BEEP_UP_PATH, volume=0.40)


def play_stop_sound():
    """Play beep_down.wav at 40% volume (stop recording)."""
    _play_wav(BEEP_DOWN_PATH, volume=0.40)


def play_cancel_sound():
    """Play beep_down.wav at 40% volume (cancel recording)."""
    _play_wav(BEEP_DOWN_PATH, volume=0.40)
