import ctypes
import gc
import glob
import os
import time
from typing import Optional
import numpy as np
from PySide6.QtCore import QThread, QTimer, Signal


def _load_nvidia_libraries():
    """Dynamically load NVIDIA libraries (cublas, cudnn) installed via pip."""
    try:
        import site
        for sp in site.getsitepackages():
            nvidia_dir = os.path.join(sp, "nvidia")
            if os.path.exists(nvidia_dir):
                for lib_file in glob.glob(
                    os.path.join(nvidia_dir, "*/lib/*.so*")
                ):
                    try:
                        ctypes.CDLL(lib_file)
                    except Exception:
                        pass
    except Exception:
        pass


_load_nvidia_libraries()


class ModelManager:
    _loaded_model = None
    _current_key = None
    _active_device = "cpu"

    @classmethod
    def get_model(
        cls,
        model_size: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16"
    ):
        key = (model_size, device, compute_type)
        if cls._loaded_model is not None and cls._current_key == key:
            return cls._loaded_model, cls._active_device

        from faster_whisper import WhisperModel

        if device == "cuda":
            try:
                print(
                    f"[STTEngine] Loading model '{model_size}' on GPU "
                    f"(NVIDIA CUDA, compute_type={compute_type})...",
                    flush=True
                )
                model = WhisperModel(
                    model_size, device="cuda", compute_type=compute_type
                )
                cls._loaded_model = model
                cls._current_key = key
                cls._active_device = "cuda"
                print(
                    f"[STTEngine] Model '{model_size}' loaded into GPU VRAM "
                    "successfully.",
                    flush=True
                )
                return model, "cuda"
            except Exception as e:
                print(
                    f"[STTEngine] GPU CUDA initialization failed ({e}). "
                    "Falling back to CPU (int8)...",
                    flush=True
                )

        print(
            f"[STTEngine] Loading model '{model_size}' on CPU (int8)...",
            flush=True
        )
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        cls._loaded_model = model
        cls._current_key = (model_size, "cpu", "int8")
        cls._active_device = "cpu"
        print(
            f"[STTEngine] Model '{model_size}' loaded successfully on CPU.",
            flush=True
        )
        return model, "cpu"

    @classmethod
    def unload_model(cls, reason: str = ""):
        if cls._loaded_model is not None:
            del cls._loaded_model
            cls._loaded_model = None
            cls._current_key = None
            cls._active_device = "cpu"
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            print(f"[STTEngine] VRAM/Memory released. {reason}", flush=True)


class TranscribeWorker(QThread):
    finished_signal = Signal(str, str, float)  # text, language, duration
    failed_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        model_size: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        vram_offload_policy: str = "never",
        initial_prompt: Optional[str] = None
    ):
        super().__init__()
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.vram_offload_policy = vram_offload_policy
        self.initial_prompt = initial_prompt or (
            "Direct transcription in Portuguese and technical English."
        )

    def run(self):
        start_time = time.time()
        try:
            if len(self.audio_data) == 0:
                self.finished_signal.emit("", "pt", 0.0)
                return

            duration = len(self.audio_data) / self.sample_rate

            self.status_signal.emit("Fetching model...")
            model, active_device = ModelManager.get_model(
                model_size=self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )

            status_msg = (
                "Transcrevendo (GPU CUDA)..."
                if active_device == "cuda" else "Transcrevendo (CPU)..."
            )
            self.status_signal.emit(status_msg)

            segments, info = model.transcribe(
                self.audio_data,
                beam_size=5,
                task="transcribe",
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                no_speech_threshold=0.6
            )
            segments = list(segments)

            # If no speech probability is high, consider audio as silence
            if getattr(info, 'no_speech_prob', 0.0) > 0.65:
                text_parts = []
            else:
                text_parts = [segment.text.strip() for segment in segments]

            full_text = " ".join(text_parts).strip()

            elapsed = time.time() - start_time
            ns_prob = getattr(info, 'no_speech_prob', 0.0)
            print(
                f"[STTEngine] Transcription via {active_device.upper()} "
                f"completed in {elapsed:.2f}s (Model: {self.model_size} | "
                f"Language: {info.language.upper()}, "
                f"Prob: {info.language_probability:.2f}, "
                f"NoSpeechProb: {ns_prob:.2f}) -> \"{full_text}\"",
                flush=True
            )

            self.finished_signal.emit(full_text, info.language, duration)

        except Exception as e:
            print(f"[STTEngine] Transcription error: {e}", flush=True)
            self.failed_signal.emit(str(e))
