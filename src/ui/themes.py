"""Theme definitions. One dict per theme feeds both the QSS template and the pill's paint code."""
from PySide6.QtGui import QColor

DEFAULT_THEME = "glass"

_BASE = {
    "bg": "#0d0d10", "surface": "#17171b", "raised": "#2d282f", "border": "#333038",
    "text": "#f5f2ed", "muted": "#bbb7bd", "accent": "#f47a87", "accent_bg": "#3f1d27",
    "accent_fg": "#ffc5ce", "focus": "#f8d658", "font": "Liberation Sans",
    "r": 7, "rl": 10, "btn_r": 16, "rec_r": 18, "pill_r": 15,
    "glow": "#f6d45a", "err": "#ff9997", "ink": "#ff7776",
    "pill_top": "#32282f", "pill_bot": "#0b090e", "rim": "#ffe8f0",
    "style": "glass", "pill_alpha": 205, "icon": "", "icon_on": "#fff2f2",
}

_THEMES = {
    "glass": {"label": "Vidro", "desc": "Escuro translúcido, o visual padrão."},
    "terminal": {
        "icon": "#3dff7a", "label": "Terminal CLI", "desc": "Fósforo verde, fonte monoespaçada e cantos retos.",
        "bg": "#070b07", "surface": "#0d140d", "raised": "#142214", "border": "#1f4d28",
        "text": "#b8f5b0", "muted": "#6fae6c", "accent": "#3dff7a", "accent_bg": "#0f2a16",
        "accent_fg": "#3dff7a", "focus": "#e5ff4d", "font": "JetBrains Mono", "r": 2, "rl": 2,
        "btn_r": 2, "rec_r": 2, "pill_r": 3, "glow": "#3dff7a", "err": "#ff6b5e", "ink": "#3dff7a",
        "pill_top": "#0d160d", "pill_bot": "#060a06", "rim": "#3dff7a", "style": "terminal",
        "pill_alpha": 240,
    },
    "hud": {
        "icon": "#19d3ff", "label": "FUI / HUD", "desc": "Interface futurista ciano com colchetes de mira.",
        "bg": "#040a10", "surface": "#08141f", "raised": "#0e2638", "border": "#0f4a63",
        "text": "#c6f1ff", "muted": "#6fb4cc", "accent": "#19d3ff", "accent_bg": "#082a3a",
        "accent_fg": "#7fe6ff", "focus": "#ffb020", "font": "JetBrains Mono", "r": 0, "rl": 0,
        "btn_r": 0, "rec_r": 0, "pill_r": 0, "glow": "#19d3ff", "err": "#ff7a3d", "ink": "#19d3ff",
        "pill_top": "#0a1d2c", "pill_bot": "#040b12", "rim": "#19d3ff", "style": "hud",
        "pill_alpha": 238,
    },
    "wood": {
        "icon": "#2b1706", "label": "Madeira real", "desc": "Skeuomorfismo de madeira escura com veios e relevo.",
        "bg": "#24150c", "surface": "#352012", "raised": "#4a2f1a", "border": "#5e3d22",
        "text": "#f3e2c7", "muted": "#c9ad85", "accent": "#e0a458", "accent_bg": "#5a3a1c",
        "accent_fg": "#ffd9a0", "focus": "#ffe08a", "font": "FreeSerif", "r": 6, "rl": 9,
        "btn_r": 16, "rec_r": 18, "pill_r": 13, "glow": "#ffd27a", "err": "#ff8a5c",
        "ink": "#e0a458", "pill_top": "#6b4224", "pill_bot": "#2e1a0d", "rim": "#f0c88c",
        "style": "wood", "pill_alpha": 255,
    },
    "eco": {
        "icon": "#05261a", "label": "Eco luminoso", "desc": "Verde orgânico com brilho suave e bordas arredondadas.",
        "bg": "#07150f", "surface": "#0e271c", "raised": "#163828", "border": "#1f5a3c",
        "text": "#e6f7ea", "muted": "#8fc9a3", "accent": "#7dff9b", "accent_bg": "#12402a",
        "accent_fg": "#b4ffc7", "focus": "#f4ff7a", "font": "Liberation Sans", "r": 12, "rl": 16,
        "btn_r": 16, "rec_r": 18, "pill_r": 27, "glow": "#9dffb3", "err": "#ffb07a",
        "ink": "#7dff9b", "pill_top": "#14382a", "pill_bot": "#071a12", "rim": "#9dffb3",
        "style": "eco", "pill_alpha": 225,
    },
    "lofi": {
        "icon": "#3b2a48", "label": "Lo-fi", "desc": "Tons pastel quentes, traço de caderno e clima de estudo.",
        "bg": "#241e2e", "surface": "#322a3f", "raised": "#41364f", "border": "#5a4a6e",
        "text": "#f6e7da", "muted": "#c4aebd", "accent": "#ffb38a", "accent_bg": "#4d3548",
        "accent_fg": "#ffd2b8", "focus": "#ffe08a", "font": "Liberation Sans", "r": 12, "rl": 16,
        "btn_r": 16, "rec_r": 18, "pill_r": 20, "glow": "#ffd29a", "err": "#ff8fa3",
        "ink": "#ffb38a", "pill_top": "#4a3a5c", "pill_bot": "#2a2236", "rim": "#f6c7a8",
        "style": "lofi", "pill_alpha": 235,
    },
    "rpg": {
        "label": "RPG Pixel Art", "desc": "Pixel art de RPG clássico com bordas em degraus.",
        "bg": "#150f22", "surface": "#241a3a", "raised": "#382a58", "border": "#6b4aa8",
        "text": "#fbf3d2", "muted": "#c0b0e0", "accent": "#ffd23f", "accent_bg": "#4a3578",
        "accent_fg": "#ffe98a", "focus": "#5cf2ff", "font": "FreeMono", "r": 0, "rl": 0,
        "btn_r": 0, "rec_r": 0, "pill_r": 0, "glow": "#ffd23f", "err": "#ff5c7a", "ink": "#5cf2ff",
        "pill_top": "#33254f", "pill_bot": "#1a1230", "rim": "#9b7be0", "style": "rpg",
        "pill_alpha": 255,
    },
    "stalker": {
        "label": "S.T.A.L.K.E.R.", "desc": "Zona de exclusão: oliva sujo, ferrugem e âmbar de PDA.",
        "bg": "#0f100b", "surface": "#1a1b12", "raised": "#26281a", "border": "#4a4a32",
        "text": "#d2ccA6", "muted": "#8f8c6c", "accent": "#d0a63a", "accent_bg": "#3a3416",
        "accent_fg": "#f0cf6a", "focus": "#ff8a2a", "font": "DejaVu Sans Mono", "r": 2, "rl": 3,
        "btn_r": 3, "rec_r": 3, "pill_r": 4, "glow": "#d0a63a", "err": "#c4512e", "ink": "#d0a63a",
        "pill_top": "#262718", "pill_bot": "#0d0e09", "rim": "#7b7a52", "style": "stalker",
        "pill_alpha": 245,
    },
}

THEMES = {key: {**_BASE, **value} for key, value in _THEMES.items()}
_active = DEFAULT_THEME


def set_active(key: str) -> str:
    global _active
    _active = key if key in THEMES else DEFAULT_THEME
    return _active


def active_key() -> str:
    return _active


def active() -> dict:
    return THEMES[_active]


def rgba(color: str, alpha: int) -> str:
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def qcolor(color: str, alpha: int = 255) -> QColor:
    c = QColor(color)
    c.setAlpha(alpha)
    return c


def icon_color() -> str:
    """Icon color for pill buttons in the active theme (falls back to the text color)."""
    t = active()
    return t["icon"] or t["text"]
