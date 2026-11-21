import os
import sys

# On Linux Wayland/GNOME, force xcb (XWayland) for window positioning
if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QApplication, QInputDialog

from src.audio.audio_cues import (
    play_start_sound, play_stop_sound, play_cancel_sound
)
from src.db.database import DatabaseManager
from src.audio.recorder import AudioRecorder
from src.engine.stt_engine import TranscribeWorker, ModelManager
from src.utils.injector import TextInjector
from src.utils.hotkey import GlobalHotkeyListener
from src.ui import themes
from src.ui.styles import build_qss
from src.ui.floating_widget import FloatingPillWidget
from src.ui.history_window import HistoryWindow


class VoiceToTextApp(QObject):
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Core Services
        self.db = DatabaseManager()
        themes.set_active(self.db.get_setting("theme", themes.DEFAULT_THEME))
        self.app.setStyleSheet(build_qss(themes.active()))
        self.recorder = AudioRecorder()
        self.transcribe_worker: TranscribeWorker = None
        self.review_dialog = None
        self.retry_audio = None

        # Status reset timer to manage pill status timeouts safely
        self.status_reset_timer = QTimer(self)
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(self._reset_pill_status)

        # UI Components
        self.floating_pill = FloatingPillWidget(db_manager=self.db)
        self.history_window = HistoryWindow(self.db)

        # Connect Microphone Volume Stream to Floating Pill Waveform
        self.recorder.volume_signal.connect(
            self.floating_pill.update_volume_level
        )

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

        # Connect UI Signals
        self.floating_pill.open_history_requested.connect(
            self.show_history_window
        )
        self.floating_pill.open_settings_requested.connect(
            self.show_settings_window
        )
        self.floating_pill.toggle_recording_requested.connect(
            self.toggle_recording
        )
        self.floating_pill.quit_requested.connect(self.quit_app)
        self.floating_pill.retry_requested.connect(self.retry_transcription)
        self.floating_pill.cancel_recording_requested.connect(self.cancel_recording)
        self.floating_pill.always_on_top_changed.connect(
            lambda enable: self.db.set_setting(
                "always_on_top", "true" if enable else "false"
            )
        )

        self.history_window.settings_changed.connect(self.apply_settings)
        self.history_window.theme_changed.connect(self.apply_theme)

        # Global Hotkey Listener
        hotkey_mode = self.db.get_setting("hotkey_mode", "toggle")
        self.hotkey_listener = GlobalHotkeyListener(
            on_start_recording=self.start_recording,
            on_stop_recording=self.stop_recording,
            on_cancel_recording=self.cancel_recording,
            mode=hotkey_mode,
            combination_str="<ctrl>+<space>"
        )
        self.hotkey_listener.start()

        self.floating_pill.show()

    def show_history_window(self):
        self.history_window.refresh_history()
        self.history_window.show_page(0)
        self._show_workspace()

    def show_settings_window(self):
        self.history_window.show_page(1)
        self._show_workspace()

    def _show_workspace(self):
        self.history_window.show()
        self.history_window.raise_()
        self.history_window.activateWindow()

    @Slot()
    def toggle_recording(self):
        if self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    @Slot()
    def start_recording(self):
        if self.review_dialog is not None or self.recorder.is_recording:
            return
        if self.transcribe_worker is not None:
            print(
                "[Main] Previous transcription still in progress...",
                flush=True
            )
            return

        self.vram_unload_timer.stop()
        self.status_reset_timer.stop()
        try:
            self.recorder.start_recording(self.db.get_setting("microphone", "") or None)
        except Exception as error:
            self.floating_pill.set_status(
                "error", f"Não foi possível abrir o microfone. {error}"
            )
            self._manage_vram_offload()
            return
        self.retry_audio = None
        self.floating_pill.set_status("recording", "Gravando...")

        if self.db.get_setting("sound_effects", "true").lower() == "true":
            play_start_sound()

    @Slot()
    def cancel_recording(self):
        if not self.recorder.is_recording:
            return

        self.recorder.stop_recording()
        self.floating_pill.set_status("idle", "Gravação cancelada")
        print("[Main] Recording cancelled by user (ESC).", flush=True)

        if self.db.get_setting("sound_effects", "true").lower() == "true":
            play_cancel_sound()

        self.status_reset_timer.start(2500)

    @Slot()
    def stop_recording(self):
        if not self.recorder.is_recording:
            return

        if self.db.get_setting("sound_effects", "true").lower() == "true":
            play_stop_sound()

        audio_data = self.recorder.stop_recording()

        if len(audio_data) == 0 or (len(audio_data) / 16000) < 0.5:
            self.floating_pill.set_status("idle", "Áudio muito curto")
            self.status_reset_timer.start(3000)
            print("[Main] Audio recording too short, discarded.", flush=True)
            return

        self._transcribe(audio_data)

    @Slot()
    def retry_transcription(self):
        if self.retry_audio is None or self.transcribe_worker is not None:
            return
        self._transcribe(self.retry_audio)

    def _transcribe(self, audio_data):
        self.retry_audio = audio_data
        self.vram_unload_timer.stop()
        self.floating_pill.set_status("transcribing", "Preparando modelo…")

        # Load current settings for STT
        model_size = self.db.get_setting("model_size", "large-v3-turbo")
        device = self.db.get_setting("device", "cuda")
        compute_type = self.db.get_setting("compute_type", "float16")
        vram_policy = self.db.get_setting("vram_offload_policy", "never")
        language = self.db.get_setting("language", "auto")

        # Start background worker thread
        self.transcribe_worker = TranscribeWorker(
            audio_data=audio_data,
            sample_rate=16000,
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            vram_offload_policy=vram_policy,
            language=language,
            hotwords=self.db.get_setting("hotwords", "") or None
        )

        self.transcribe_worker.finished_signal.connect(
            self._on_transcription_finished
        )
        self.transcribe_worker.failed_signal.connect(
            self._on_transcription_failed
        )
        self.transcribe_worker.status_signal.connect(self._on_transcription_status)
        self.transcribe_worker.finished.connect(self.transcribe_worker.deleteLater)
        self.transcribe_worker.finished.connect(self._worker_finished)
        self.transcribe_worker.start()

    @Slot(str)
    def _on_transcription_status(self, message):
        self.floating_pill.set_status("transcribing", message)

    @Slot()
    def _worker_finished(self):
        self.transcribe_worker = None

    @Slot(str, str, float)
    def _on_transcription_finished(
        self, text: str, language: str, duration: float
    ):
        self.retry_audio = None
        if text and self.db.get_setting("review_before_copy", "false") == "true":
            self._review_text(text, language, duration)
            self._manage_vram_offload()
            return
        self._deliver_transcription(text, language, duration)
        self._manage_vram_offload()

    def _review_text(self, text: str, language: str, duration: float):
        dialog = QInputDialog(self.floating_pill)
        dialog.setWindowTitle("Revisar ditado")
        dialog.setLabelText("Edite o texto antes de copiar.")
        dialog.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput)
        dialog.setOkButtonText("Copiar")
        dialog.setCancelButtonText("Descartar")
        dialog.setTextValue(text)
        dialog.resize(480, 280)
        self.review_dialog = dialog
        self.floating_pill.set_status("review", "Revise o texto")
        dialog.textValueSelected.connect(
            lambda edited: self._deliver_transcription(edited.strip(), language, duration, copy=True)
        )
        dialog.rejected.connect(lambda: self.floating_pill.set_status("idle"))
        dialog.finished.connect(self._close_review)
        dialog.open()

    @Slot()
    def _close_review(self):
        self.review_dialog.deleteLater()
        self.review_dialog = None

    def _deliver_transcription(self, text, language, duration, *, copy=False):
        if text:
            save = self.db.get_setting("save_history", "true") == "true"
            if save:
                try:
                    self.db.add_transcription(text, language, duration)
                except Exception as error:
                    self.floating_pill.set_status(
                        "error", f"Não foi possível salvar no histórico. {error}"
                    )
                    if copy or self.db.get_setting("copy_to_clipboard", "true") == "true":
                        TextInjector.copy_to_clipboard(text)
                    return
                if self.history_window.isVisible():
                    self.history_window.refresh_history()
            if copy or self.db.get_setting("copy_to_clipboard", "true") == "true":
                copied = TextInjector.copy_to_clipboard(text)
                if copied:
                    self.floating_pill.set_status("success", "Texto copiado")
                else:
                    message = (
                        "Texto salvo no histórico, mas não foi possível copiar."
                        if save else "Não foi possível copiar o texto."
                    )
                    self.floating_pill.set_status("error", message)
            elif save:
                self.floating_pill.set_status("success", "Salvo no histórico")
            else:
                self.floating_pill.set_status("idle", "Histórico e cópia desativados")
        else:
            self.floating_pill.set_status("idle", "Nenhum texto detectado")

        if self.floating_pill.status_state != "error":
            self.status_reset_timer.start(3000)

    @Slot()
    def _reset_pill_status(self):
        if self.floating_pill.status_state == "success":
            self.floating_pill.set_status("settling")
            self.status_reset_timer.start(650)
        else:
            self.floating_pill.set_status("idle")

    @Slot(str)
    def _on_transcription_failed(self, error_msg: str):
        self.floating_pill.set_status("error", error_msg)
        self.floating_pill.retry_action.setVisible(self.retry_audio is not None)
        print(f"[Main] Failure: {error_msg}", flush=True)
        self.status_reset_timer.stop()
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

    def apply_theme(self, key: str):
        self.db.set_setting("theme", themes.set_active(key))
        self.app.setStyleSheet(build_qss(themes.active()))
        self.floating_pill.apply_theme()
        self.floating_pill.apply_position_preset(self.db.get_setting("pill_position", "bottom"))
        self.history_window.apply_theme()

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
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        if self.transcribe_worker is not None:
            self.transcribe_worker.finished.connect(self.app.quit)
            self.floating_pill.set_status("transcribing", "Encerrando após a transcrição…")
            return
        self.app.quit()

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    app = VoiceToTextApp()
    sys.exit(app.run())
