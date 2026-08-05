import threading
from typing import Optional
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


class AudioRecorder(QObject):
    volume_signal = Signal(float)

    def __init__(self, sample_rate: int = 16000):
        super().__init__()
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_data = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"[AudioRecorder] Status: {status}", flush=True)
        if self.is_recording:
            with self._lock:
                self.audio_data.append(indata.copy())
            rms = float(np.sqrt(np.mean(indata**2)))
            level = min(1.0, rms * 18.0)
            self.volume_signal.emit(level)

    def start_recording(self):
        with self._lock:
            self.audio_data.clear()
            self.is_recording = True

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback
        )
        self._stream.start()
        print("[AudioRecorder] Recording started...", flush=True)

    def stop_recording(self) -> np.ndarray:
        self.is_recording = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self.audio_data:
                return np.array([], dtype=np.float32)
            recorded_np = np.concatenate(self.audio_data, axis=0).flatten()
            self.audio_data.clear()

        duration = len(recorded_np) / self.sample_rate
        max_amp = (
            float(np.max(np.abs(recorded_np))) if len(recorded_np) > 0 else 0.0
        )
        print(
            f"[AudioRecorder] Recording finished. Duration: {duration:.2f}s | "
            f"Max Amplitude: {max_amp:.4f}",
            flush=True
        )

        if max_amp < 0.001:
            print(
                "[AudioRecorder] WARNING: Recorded audio volume is extremely "
                "low or silent. Check your microphone.",
                flush=True
            )

        return recorded_np
