"""UI regressions; run with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from src.db.database import DatabaseManager
from src.ui.floating_widget import FloatingPillWidget
from src.ui.history_window import HistoryWindow
from src.ui.styles import APP_STYLE_QSS


class UIRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLE_QSS)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(self.directory.name + '/test.db')
        self.pill = FloatingPillWidget(self.db)
        self.history = HistoryWindow(self.db)

    def tearDown(self):
        self.pill.tray_icon.hide()
        self.pill.close()
        self.history.close()
        self.pill.deleteLater()
        self.history.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_navigation_and_search_keep_page_selection_in_sync(self):
        self.history.tabs.setCurrentIndex(1)
        self.assertEqual(self.history.tabs.tabText(1), "Configurações")
        self.history.focus_history_search()
        self.assertEqual(self.history.pages.currentIndex(), 0)
        self.assertEqual(self.history.tabs.currentIndex(), 0)

    def test_messages_are_preserved(self):
        for state, message in [('idle', 'Gravação cancelada'),
                               ('idle', 'Nenhuma fala detectada'),
                               ('success', 'Salvo no histórico'),
                               ('transcribing', 'Carregando modelo…')]:
            self.pill.set_status(state, message)
            self.assertEqual(self.pill.status_label.toolTip(), message)

    def test_pill_size_and_main_button_position_are_fixed_across_states(self):
        self.pill.show()
        self.app.processEvents()
        original_geometry = self.pill.geometry()
        button_geometry = self.pill.btn_record.geometry()
        self.assertEqual(self.pill.status_label.toolTip(), "Ditar")
        self.assertTrue(self.pill.audio_panel.isHidden())
        self.assertIn("Histórico", [action.text() for action in self.pill.btn_more.menu().actions()])

        for state in ("recording", "transcribing", "success", "settling", "idle"):
            self.pill.set_status(state)
            self.app.processEvents()
            self.assertEqual(self.pill.geometry(), original_geometry)
            self.assertEqual(self.pill.btn_record.geometry(), button_geometry)
            surface = self.pill.grab().toImage().pixelColor(150, 46)
            self.assertLess(surface.alpha(), 255)
            self.assertGreater(surface.alpha(), 0)
            self.assertFalse(self.pill.btn_record.isHidden())
            self.assertEqual(self.pill.audio_panel.isVisible(), state == "recording")
            if state == "recording":
                self.pill.update_volume_level(0.8)
                self.pill.waveform_widget._sample_level()
                self.assertEqual(self.pill.waveform_widget._levels[-1], 0.8)
            if state == "transcribing":
                self.assertFalse(self.pill.btn_record.isEnabled())
                self.assertEqual(self.pill.waveform_widget._levels[-1], 0.0)

    def test_record_controls_and_error_details(self):
        events = []
        self.pill.toggle_recording_requested.connect(lambda: events.append('toggle'))
        self.pill.cancel_recording_requested.connect(lambda: events.append('cancel'))
        self.pill.set_status('recording')
        self.pill.btn_record.click()
        self.pill.btn_cancel.click()
        self.assertEqual(events, ['toggle', 'cancel'])
        self.assertTrue(self.pill._record_timer.isActive())
        self.pill.set_status('transcribing')
        self.assertFalse(self.pill.btn_record.isEnabled())
        self.assertFalse(self.pill._record_timer.isActive())
        self.pill.set_status('error', 'Dispositivo indisponível')
        self.assertTrue(self.pill.detail_action.isVisible())
        self.assertEqual(self.pill._error_detail, 'Dispositivo indisponível')

    def test_delete_undo_preserves_entry(self):
        self.db.add_transcription('Um texto de teste', 'pt', 5)
        entry = self.db.get_transcriptions()[0]
        self.history._delete_item(entry)
        self.assertEqual(self.db.get_transcriptions(), [])
        self.history._undo_delete()
        self.assertEqual(self.db.get_transcriptions(), [entry])

    def test_history_loads_another_page_and_search_resets_it(self):
        self.history.PAGE_SIZE = 2
        for text in ("Primeira", "Segunda", "Terceira"):
            self.db.add_transcription(text)
        self.history.refresh_history()
        self.assertEqual(self.history._history_offset, 2)
        self.assertFalse(self.history.load_more_button.isHidden())
        self.history.load_more_button.click()
        self.assertEqual(self.history._history_offset, 3)
        self.assertTrue(self.history.load_more_button.isHidden())
        self.history.search_input.setText("Primeira")
        self.assertEqual(self.history._history_offset, 1)

    def test_history_edit_preserves_entry_metadata(self):
        item_id = self.db.add_transcription("Original", "pt", 5)
        original = self.db.get_transcriptions()[0]
        self.assertTrue(self.db.update_transcription(item_id, " Editado "))
        self.assertEqual(self.db.get_transcriptions(), [dict(original, text="Editado")])

    def test_precision_profile_uses_ctranslate2_model(self):
        combo = self.history.combo_profile
        index = next(i for i in range(combo.count()) if combo.itemData(i) == ("cuda", "large-v3"))
        self.history.combo_profile.setCurrentIndex(index)
        self.history._save_settings()
        self.assertEqual(self.db.get_setting("device"), "cuda")
        self.assertEqual(self.db.get_setting("model_size"), "large-v3")

    def test_review_and_history_preferences_are_persisted(self):
        self.assertFalse(self.history.chk_review.isChecked())
        self.assertTrue(self.history.chk_history.isChecked())
        self.history.chk_review.setChecked(True)
        self.history.chk_history.setChecked(False)
        self.history.hotwords_input.setText("PySide6, CTranslate2")
        self.history._save_settings()
        self.assertEqual(self.db.get_setting("hotwords"), "PySide6, CTranslate2")
        self.assertEqual(self.db.get_setting("review_before_copy"), "true")
        self.assertEqual(self.db.get_setting("save_history"), "false")

    def test_review_copies_edited_text_without_saving_history(self):
        from main import VoiceToTextApp

        self.db.set_setting("review_before_copy", "true")
        self.db.set_setting("save_history", "false")
        with (
            patch("main.QApplication", return_value=self.app),
            patch("main.DatabaseManager", return_value=self.db),
            patch("main.GlobalHotkeyListener"),
            patch("main.TextInjector.copy_to_clipboard", return_value=True) as copy,
        ):
            controller = VoiceToTextApp()
            try:
                controller._on_transcription_finished("Texto original", "pt", 1)
                self.assertIsNotNone(controller.review_dialog)
                copy.assert_not_called()
                controller.review_dialog.setTextValue("Texto corrigido")
                controller.review_dialog.accept()
                copy.assert_called_once_with("Texto corrigido")
                self.assertEqual(self.db.get_transcriptions(), [])
                self.assertIsNone(controller.review_dialog)
                self.assertEqual(controller.floating_pill.status_state, "success")
                controller._reset_pill_status()
                self.assertEqual(controller.floating_pill.status_state, "settling")
                self.assertEqual(controller.status_reset_timer.interval(), 650)
                controller._reset_pill_status()
                self.assertEqual(controller.floating_pill.status_state, "idle")
            finally:
                controller.floating_pill.tray_icon.hide()
                controller.floating_pill.close()
                controller.history_window.close()

    def test_search_distinguishes_empty_history(self):
        initial = self.history.scroll_layout.itemAt(0).widget().text()
        self.history.search_input.setText('inexistente')
        result = self.history.scroll_layout.itemAt(0).widget().text()
        self.assertIn('histórico começa', initial)
        self.assertIn('Nenhum resultado', result)


if __name__ == '__main__':
    unittest.main()
