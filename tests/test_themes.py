"""Every theme must render the stylesheet, the pill in each state and the themes tab."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from src.db.database import DatabaseManager
from src.ui import themes
from src.ui.floating_widget import FloatingPillWidget
from src.ui.history_window import HistoryWindow
from src.ui.skins import skin_for
from src.ui.styles import build_qss


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        themes.set_active(themes.DEFAULT_THEME)

    def test_all_themes_render_everywhere(self):
        with tempfile.TemporaryDirectory() as directory:
            db = DatabaseManager(directory + '/t.db')
            pill, history = FloatingPillWidget(db), HistoryWindow(db)
            for key, theme in themes.THEMES.items():
                themes.set_active(key)
                self.app.setStyleSheet(build_qss(theme))
                pill.apply_theme()
                history.apply_theme()
                self.assertEqual((pill.width(), pill.height()), skin_for(theme).size)
                for state in ('idle', 'settling', 'recording', 'transcribing', 'review', 'success', 'error'):
                    pill.set_status(state, 'x')
                    self.assertFalse(pill.grab().isNull())
                    self.assertEqual((pill.width(), pill.height()), skin_for(theme).size)
                self.assertTrue(history.theme_buttons[key].isChecked())
            pill.tray_icon.hide()

    def test_unknown_theme_falls_back(self):
        self.assertEqual(themes.set_active('nope'), themes.DEFAULT_THEME)


if __name__ == '__main__':
    unittest.main()
