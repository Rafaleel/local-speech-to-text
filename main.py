import os
import sys

# On Linux Wayland/GNOME, force xcb (XWayland) for window positioning
if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QApplication

from src.db.database import DatabaseManager
from src.audio.recorder import AudioRecorder
from src.engine.stt_engine import TranscribeWorker, ModelManager
from src.utils.injector import TextInjector
from src.utils.hotkey import GlobalHotkeyListener
from src.ui.styles import DARK_THEME_QSS
from src.ui.floating_widget import FloatingPillWidget
from src.ui.history_window import HistoryWindow


class VoiceToTextApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setStyleSheet(DARK_THEME_QSS)
        self.app.setQuitOnLastWindowClosed(False)

        # Core Services
        self.db = DatabaseManager()
        self.recorder = AudioRecorder()
        self.transcribe_worker: TranscribeWorker = None

        # UI Components
        self.floating_pill = FloatingPillWidget(db_manager=self.db)
        self.history_window = HistoryWindow(self.db)

        # Load initial position and always_on_top settings
        is_top = self.db.get_setting("always_on_top", "true").lower() == "true"
        position_preset = self.db.get_setting("pill_position", "bottom")

        self.floating_pill.set_always_on_top(is_top)
        self.floating_pill.apply_position_preset(position_preset)

        # VRAM Management Timer
        self.vram_unload_timer = QTimer(self)
        self.vram_unload_timer.setSingleShot(True)
        self.vram_unload_timer.timeout.connect(
            lambda: ModelManager.unload_model("VRAM freed after inactivity.")
        )

        # Status reset timer to prevent overlapping status updates
        self.status_reset_timer = QTimer(self)
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(
            lambda: self.floating_pill.set_status(
                "idle", "Pronto (Ctrl+Espaço)")
        )

        # Connect UI Signals
        self.floating_pill.open_history_requested.connect(
            self.show_history_window
        )
        self.floating_pill.toggle_recording_requested.connect(
            self.toggle_recording
        )
        self.floating_pill.quit_requested.connect(self.quit_app)
        self.floating_pill.always_on_top_changed.connect(
            lambda enable: self.db.set_setting(
                "always_on_top", "true" if enable else "false"
            )
        )

        self.history_window.settings_changed.connect(self.apply_settings)

        # Global Hotkey Listener
        hotkey_mode = self.db.get_setting("hotkey_mode", "toggle")
        self.hotkey_listener = GlobalHotkeyListener(
            on_start_recording=self.start_recording,
            on_stop_recording=self.stop_recording,
            mode=hotkey_mode,
            combination_str="<ctrl>+<space>"
        )
        self.hotkey_listener.start()

        self.floating_pill.show()

    def show_history_window(self):
        self.history_window.refresh_history()
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    @Slot()
    def toggle_recording(self):
        if self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.transcribe_worker and self.transcribe_worker.isRunning():
            print(
                "[Main] Previous transcription still in progress...",
                flush=True
            )
            return

        self.vram_unload_timer.stop()
        self.status_reset_timer.stop()
        self.recorder.start_recording()
        self.floating_pill.set_status("recording", "Gravando...")

    def stop_recording(self):
        if not self.recorder.is_recording:
            return

        audio_data = self.recorder.stop_recording()

        if len(audio_data) == 0 or (len(audio_data) / 16000) < 0.5:
            self.floating_pill.set_status("idle", "Pronto (Ctrl+Espaço)")
            print("[Main] Audio recording too short, discarded.", flush=True)
            return

        self.floating_pill.set_status("transcribing", "Transcrevendo...")

        # Load current settings for STT
        model_size = self.db.get_setting("model_size", "large-v3-turbo")
        device = self.db.get_setting("device", "cuda")
        compute_type = self.db.get_setting("compute_type", "float16")
        vram_policy = self.db.get_setting("vram_offload_policy", "never")

        # Start background worker thread
        self.transcribe_worker = TranscribeWorker(
            audio_data=audio_data,
            sample_rate=16000,
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            vram_offload_policy=vram_policy
        )

        self.transcribe_worker.finished_signal.connect(
            self._on_transcription_finished
        )
        self.transcribe_worker.failed_signal.connect(
            self._on_transcription_failed
        )
        self.transcribe_worker.status_signal.connect(
            lambda msg: self.floating_pill.set_status("transcribing", msg)
        )
        self.transcribe_worker.start()

    @Slot(str, str, float)
    def _on_transcription_finished(
        self, text: str, language: str, duration: float
    ):
        if text:
            print(f"[Main] Transcription saved: \"{text}\"", flush=True)

            # Save to SQLite DB
            self.db.add_transcription(
                text=text,
                language=language,
                duration_seconds=duration
            )

            # Copy to clipboard if enabled
            if self.db.get_setting(
                "copy_to_clipboard", "true"
            ).lower() == "true":
                TextInjector.copy_to_clipboard(text)
                self.floating_pill.set_status("success", "Copiado!")
            else:
                self.floating_pill.set_status("success", "Concluído!")

            # Always refresh history window list
            self.history_window.refresh_history()
        else:
            print(
                "[Main] Warning: No speech detected in recording.", flush=True
            )
            self.floating_pill.set_status("idle", "Nenhum texto detectado")

        # Reset pill status back to idle after 3 seconds
        self.status_reset_timer.start(3000)
        self._manage_vram_offload()

    @Slot(str)
    def _on_transcription_failed(self, error_msg: str):
        self.floating_pill.set_status("error", "Erro na transcrição")
        print(f"[Main] Failure: {error_msg}", flush=True)
        self.status_reset_timer.start(4000)
        self._manage_vram_offload()

    def _manage_vram_offload(self):
        policy = self.db.get_setting("vram_offload_policy", "never")
        if policy == "never":
            return
        elif policy == "immediate":
            ModelManager.unload_model(
                "VRAM freed immediately after transcription.")
        elif policy in ["5s", "15s", "30s"]:
            seconds = int(policy.replace("s", ""))
            self.vram_unload_timer.start(seconds * 1000)

    def apply_settings(self):
        new_mode = self.db.get_setting("hotkey_mode", "toggle")
        self.hotkey_listener.set_mode(new_mode)

        is_top = self.db.get_setting("always_on_top", "true").lower() == "true"
        position_preset = self.db.get_setting("pill_position", "bottom")

        self.floating_pill.set_always_on_top(is_top)
        self.floating_pill.apply_position_preset(position_preset)

        print(
            f"[Main] Settings applied. Mode: {new_mode} | "
            f"AlwaysOnTop: {is_top} | Position: {position_preset}",
            flush=True
        )

    def quit_app(self):
        self.hotkey_listener.stop()
        self.app.quit()

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    app = VoiceToTextApp()
    sys.exit(app.run())
