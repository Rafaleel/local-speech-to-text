from pathlib import Path
from string import Template

from src.ui.themes import DEFAULT_THEME, THEMES, rgba

APP_STYLE_QSS = """
QWidget {
    font-family: "$font";
    font-style: normal;
    font-size: 13px;
    color: $text;
}
QDialog, QWidget#PageContent, QWidget#MainArea { background: $bg; }
QWidget#WorkspaceHeader {
    background: $surface;
    border-bottom: 1px solid $border;
}
QWidget#FloatingPill { background: transparent; }
QLabel#Brand { font-size: 16px; font-weight: 700; }
QLabel#PageTitle { font-size: 31px; font-weight: 700; }
QTabBar {
    background: $surface;
    border-radius: $rl;
}
QTabBar::tab {
    padding: 8px 12px;
    margin: 3px;
    color: $muted;
    background: transparent;
    border: 1px solid transparent;
    border-radius: $r;
    font-weight: 700;
}
QTabBar::tab:hover { background: $raised; }
QTabBar::tab:selected { background: $accent_bg; border-color: $accent; color: $accent_fg; }
QTabBar::tab:focus { border-color: $focus; }
QLabel#StatusText { font-size: 13px; font-weight: 700; }
QLabel#SecondaryText, QLabel#Metadata { color: $muted; }
QLabel#Metadata { font-size: 12px; }
QLabel#Shortcut {
    color: $muted;
    border: 1px solid $border;
    border-radius: $r;
    padding: 5px 7px;
    font-size: 11px;
}
QLabel#EmptyState {
    color: $muted;
    background: $surface;
    border: 1px dashed $border;
    border-radius: $rl;
    padding: 42px 16px;
}
QWidget#HistoryCard {
    background: $surface;
    border-bottom: 1px solid $border;
}
QWidget#HistoryCard:hover { background: $raised; }
QLabel#Transcript { font-size: 15px; }
QLabel#SectionTitle { font-size: 17px; font-weight: 700; }
QWidget#SettingsSection {
    background: $surface;
    border: 1px solid $border;
    border-radius: $rl;
}
QPushButton {
    background: $surface;
    border: 1px solid $border;
    border-radius: $r;
    padding: 7px 12px;
    font-weight: 700;
}
QPushButton:hover { background: $raised; }
QPushButton:pressed { background: $accent_bg; }
QPushButton:focus { border-color: $focus; }
QPushButton:disabled { background: $bg; color: $muted; }
QPushButton#HistoryAction { background: transparent; border-color: transparent; padding: 6px 7px; }
QPushButton#HistoryAction:hover { background: $raised; }
QPushButton#HistoryAction:focus { border-color: $focus; }
QPushButton#PrimaryButton { color: $bg; background: $accent; border-color: $accent; padding: 9px 15px; }
QPushButton#PrimaryButton:hover { background: $accent_fg; }
QPushButton#PrimaryButton:focus { border-color: $focus; }
QPushButton#RecordButton, QPushButton#PillAction { background: transparent; border: none; }
QWidget#PillAudioPanel { background: transparent; border: none; }
QLabel#PillClock {
    color: $ink;
    font-family: "$font";
    font-size: 15px;
    font-weight: 700;
}
QPushButton::menu-indicator { image: none; width: 0; }
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {
    background: $surface;
    border: 1px solid $border;
    border-radius: $r;
    padding: 8px 10px;
    placeholder-text-color: $muted;
    selection-background-color: $accent_bg;
    selection-color: $accent_fg;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: $focus;
}
QComboBox { min-height: 18px; padding-right: 24px; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(assets/chevron.png); width: 12px; height: 12px; }
QComboBox QAbstractItemView, QMenu {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    selection-background-color: $accent_bg;
}
QMenu { padding: 5px; }
QMenu::item { padding: 8px 16px; }
QMenu::item:selected { background: $accent_bg; }
QMenu#PillMenu {
    background: $surface; border: 1px solid $border; border-radius: $rl;
}
QMenu#PillMenu::item:selected { background: $accent_bg; }
QMenu#PillMenu::separator { height: 1px; background: $border; margin: 3px 7px; }
QCheckBox { spacing: 8px; padding: 4px; border: 1px solid transparent; }
QCheckBox:focus { border-color: $focus; border-radius: 5px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid $muted; border-radius: $r; background: $surface;
}
QCheckBox::indicator:checked { background: $accent; border-color: $accent_fg; image: url(assets/check.svg); }
QScrollBar:vertical { background: transparent; width: 9px; margin: 1px; }
QScrollBar::handle:vertical { background: $border; min-height: 30px; border-radius: $r; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: $raised; color: $text; border: 1px solid $border; padding: 6px; }
QPushButton#ThemeCard {
    text-align: left; padding: 10px 12px; border-radius: $rl; font-weight: 400;
}
QPushButton#ThemeCard:checked { background: $accent_bg; border: 2px solid $accent; color: $accent_fg; }
"""

_TEMPLATE = Template(APP_STYLE_QSS)
assets = Path(__file__).resolve().parents[2] / "assets"


def build_qss(theme: dict) -> str:
    """Render the stylesheet for a theme; substitute() raises on a missing token."""
    values = {
        **theme,
        "rec": rgba(theme["accent"], 46), "rec_hover": rgba(theme["accent"], 78),
        "rec_pressed": rgba(theme["accent"], 30), "rec_on": rgba(theme["err"], 160),
        "rec_on_hover": rgba(theme["err"], 195), "rec_off": rgba(theme["glow"], 24),
        "act_hover": rgba(theme["text"], 26), "act_pressed": rgba(theme["text"], 14),
    }
    out = _TEMPLATE.substitute(values)
    for filename in ("check.svg", "chevron.png"):
        out = out.replace(f"assets/{filename}", (assets / filename).as_posix())
    return out


APP_STYLE_QSS = build_qss(THEMES[DEFAULT_THEME])
