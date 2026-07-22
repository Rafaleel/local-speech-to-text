from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QClipboard


class TextInjector:
    @staticmethod
    def copy_to_clipboard(text: str) -> bool:
        """Copy text to clipboard using native Qt Clipboard."""
        if not text:
            return False

        try:
            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                clipboard.setText(text, QClipboard.Mode.Clipboard)
                clipboard.setText(text, QClipboard.Mode.Selection)
                preview = text[:40]
                print(
                    f"[TextInjector] Copied: \"{preview}...\"",
                    flush=True
                )

                return True
        except Exception as e:
            print(f"[TextInjector] Qt Clipboard error: {e}", flush=True)

        return False
