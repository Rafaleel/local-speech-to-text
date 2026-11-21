"""Per-theme pill skins: each theme repaints the whole pill (case, buttons, status visuals, waveform)."""
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainterPath, QPen, QPolygonF, QRadialGradient
)

from src.ui import themes

NOPEN = Qt.PenStyle.NoPen
NOBRUSH = Qt.BrushStyle.NoBrush
CENTER = Qt.AlignmentFlag.AlignCenter


def C(color: str, alpha: int = 255) -> QColor:
    return themes.qcolor(color, alpha)


def mix(a: str, b: str, f: float) -> QColor:
    x, y = QColor(a), QColor(b)
    return QColor(*(int(u + (v - u) * f) for u, v in
                    ((x.red(), y.red()), (x.green(), y.green()), (x.blue(), y.blue()))))


def vgrad(rect: QRectF, top: QColor, bottom: QColor) -> QLinearGradient:
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0, top)
    grad.setColorAt(1, bottom)
    return grad


def stair_path(rect: QRectF, c: float) -> QPainterPath:
    l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
    pts = [(l + 2*c, t), (r - 2*c, t), (r - 2*c, t + c), (r - c, t + c), (r - c, t + 2*c), (r, t + 2*c),
           (r, b - 2*c), (r - c, b - 2*c), (r - c, b - c), (r - 2*c, b - c), (r - 2*c, b), (l + 2*c, b),
           (l + 2*c, b - c), (l + c, b - c), (l + c, b - 2*c), (l, b - 2*c),
           (l, t + 2*c), (l + c, t + 2*c), (l + c, t + c), (l + 2*c, t + c)]
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    path.closeSubpath()
    return path


def chamfer_path(rect: QRectF, cuts: tuple) -> QPainterPath:
    """cuts = (top-left, top-right, bottom-right, bottom-left) chamfer sizes."""
    l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
    tl, tr, br, bl = cuts
    pts = [(l + tl, t), (r - tr, t), (r, t + tr), (r, b - br), (r - br, b), (l + bl, b), (l, b - bl), (l, t + tl)]
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    path.closeSubpath()
    return path


def pixels(p, cx, cy, rows, scale, color):
    """Draw a bitmap of '0'/'1' rows centered on (cx, cy)."""
    p.setPen(NOPEN)
    p.setBrush(color)
    x0 = cx - len(rows[0]) * scale / 2
    y0 = cy - len(rows) * scale / 2
    for j, row in enumerate(rows):
        for i, bit in enumerate(row):
            if bit == "1":
                p.drawRect(QRectF(x0 + i * scale, y0 + j * scale, scale, scale))


def bars(p, rect, levels, t, glow=False):
    """Default waveform: rounded bars fading in from the left."""
    p.setPen(NOPEN)
    for index, level in enumerate(levels):
        height = 2 + level * (rect.height() - 3)
        bar = QRectF(index * 6, (rect.height() - height) / 2, 3, height)
        if glow:
            p.setBrush(C(t["ink"], 30))
            p.drawRoundedRect(bar.adjusted(-1.5, -1.5, 1.5, 1.5), 3, 3)
        p.setBrush(C(t["ink"], 100 + index * 11))
        p.drawRoundedRect(bar, 1.5, 1.5)


def seg_wave(p, rect, levels, t, cell=3, gap=1, step=6):
    rows = max(1, int(rect.height() // (cell + gap)))
    for index, level in enumerate(levels):
        lit = max(1, round(level * rows))
        for k in range(lit):
            top = k == lit - 1 and lit > 3
            p.setBrush(C("#ffffff", 220) if top else C(t["ink"], 120 + index * 9))
            p.drawRect(QRectF(index * step, rect.height() - (k + 1) * (cell + gap) + gap, cell, cell))


def default_status(p, ctx, t):
    """Centered growing glow while transcribing, check on success, '!' on error."""
    track = ctx.track
    cx, cy = track.center().x(), track.center().y()
    p.setPen(NOPEN)
    if ctx.state == "transcribing":
        half = ctx.phase * track.width() / 2
        glow = QLinearGradient(cx - half, 0, cx + half, 0)
        glow.setColorAt(0.0, C(t["glow"], 0))
        glow.setColorAt(0.5, C(t["glow"], int(230 * (1 - ctx.phase)) + 25))
        glow.setColorAt(1.0, C(t["glow"], 0))
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(QRectF(cx - half, cy - 1.5, 2 * half, 3), 1.5, 1.5)
    elif ctx.state in ("success", "error"):
        ok = ctx.state == "success"
        p.setPen(QPen(C(t["glow"] if ok else t["err"]), 2.2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if ok:
            p.drawPolyline([QPointF(cx - 6, cy), QPointF(cx - 2, cy + 4), QPointF(cx + 6, cy - 4)])
        else:
            p.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 1))
            p.drawPoint(QPointF(cx, cy + 6))


class Skin:
    size = (282, 54)
    margins = (10, 8, 10, 8)
    spacing = 9
    record = 36
    trail = 32
    audio_margins = (8, 8)
    antialias = True
    blinks = False

    def body(self, p, ctx, t):
        raise NotImplementedError

    def button(self, p, r, kind, t, st):
        c = C(t["err"] if st.recording else t["accent"])
        if kind == "record":
            c.setAlpha(150 if st.recording else 46)
        else:
            c = C(t["text"], 26 if st.hover else 0)
        if st.hover and kind == "record":
            c.setAlpha(c.alpha() + 32)
        p.setPen(NOPEN)
        p.setBrush(c)
        p.drawEllipse(r)

    def status(self, p, ctx, t):
        default_status(p, ctx, t)

    def wave(self, p, rect, levels, t):
        bars(p, rect, levels, t)


class Glass(Skin):
    def body(self, p, ctx, t):
        rect = QRectF(0, 0, ctx.w, ctx.h).adjusted(1.5, 1.5, -1.5, -1.5)
        top, bot = QColor(t["pill_top"]), QColor(t["pill_bot"])
        if ctx.rec:
            err = QColor(t["err"])
            top = QColor((top.red() * 3 + err.red()) // 4, (top.green() * 3 + err.green()) // 4,
                         (top.blue() * 3 + err.blue()) // 4)
        top.setAlpha(t["pill_alpha"])
        bot.setAlpha(t["pill_alpha"])
        p.setBrush(QBrush(vgrad(rect, top, bot)))
        p.setPen(QPen(C(t["err"] if ctx.rec else t["rim"], 190), 1.2))
        p.drawRoundedRect(rect, t["pill_r"], t["pill_r"])


    def status(self, p, ctx, t):
        if ctx.state not in ("idle", "settling"):
            default_status(p, ctx, t)
            return
        cx, cy = ctx.track.center().x(), ctx.track.center().y()
        p.setPen(NOPEN)
        for dx, r, a in ((-16, 2.4, 110), (0, 3.2, 230), (16, 2.4, 110)):
            p.setBrush(C(t["rim"], a))
            p.drawEllipse(QPointF(cx + dx, cy), r, r)


class Terminal(Skin):
    size = (330, 62)
    margins = (10, 20, 10, 6)
    blinks = True

    def _mono(self, t, size, bold=True):
        font = QFont(t["font"], size)
        font.setBold(bold)
        return font

    def body(self, p, ctx, t):
        r = QRectF(1, 1, ctx.w - 2, ctx.h - 2)
        p.setBrush(C("#040704", 248))
        p.setPen(QPen(C(t["accent"], 150), 1))
        p.drawRoundedRect(r, 3, 3)
        clip = QPainterPath()
        clip.addRoundedRect(r, 3, 3)
        p.save()
        p.setClipPath(clip)
        p.setPen(NOPEN)
        p.setBrush(C(t["accent"], 34))
        p.drawRect(QRectF(1, 1, ctx.w - 2, 14))
        for i, color in enumerate((t["err"], "#d8c04a", t["accent"])):
            p.setBrush(C(color, 190))
            p.drawRect(QRectF(8 + i * 10, 5, 6, 6))
        p.setFont(self._mono(t, 7, False))
        p.setPen(C(t["muted"]))
        p.drawText(QRectF(0, 1, ctx.w, 14), CENTER, "voice-to-text — zsh")
        p.setPen(QPen(QColor(0, 0, 0, 60), 1))
        for y in range(16, int(ctx.h), 3):
            p.drawLine(0, y, int(ctx.w), y)
        p.restore()

    def button(self, p, r, kind, t, st):
        color = t["err"] if st.recording else t["accent"]
        p.setBrush(C(color, 190) if st.recording else C(color, 40 if st.hover else 0))
        p.setPen(QPen(C(color, 200 if kind == "record" or st.hover else 0), 1))
        p.drawRect(r.adjusted(1, 1, -1, -1))

    def status(self, p, ctx, t):
        tr, cy = ctx.track, ctx.track.center().y()
        p.setFont(self._mono(t, 14))
        if ctx.state in ("idle", "settling"):
            p.setPen(C(t["accent"]))
            p.drawText(QPointF(tr.left() + 6, cy + 5), "$")
            if ctx.blink:
                p.setPen(NOPEN)
                p.setBrush(C(t["accent"]))
                p.drawRect(QRectF(tr.left() + 22, cy - 7, 9, 14))
        elif ctx.state == "transcribing":
            cells, lit = 13, 1 + int(ctx.phase * 7)
            start = tr.center().x() - cells * 8 / 2
            p.setPen(NOPEN)
            for i in range(cells):
                on = abs(i - cells // 2) < lit
                p.setBrush(C(t["accent"], 235 if on else 38))
                p.drawRect(QRectF(start + i * 8, cy - 5, 6, 10))
        elif ctx.state in ("success", "error"):
            ok = ctx.state == "success"
            p.setPen(C(t["accent"] if ok else t["err"]))
            p.drawText(tr, CENTER, "OK" if ok else "ERR")

    def wave(self, p, rect, levels, t):
        seg_wave(p, rect, levels, t, cell=3, gap=1)


class Hud(Skin):
    size = (304, 58)
    margins = (14, 8, 14, 8)
    record = 34
    antialias = True

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        r = QRectF(1, 1, w - 2, h - 2)
        path = chamfer_path(r, (12, 0, 12, 0))
        p.setBrush(QBrush(vgrad(r, C(t["pill_top"], t["pill_alpha"]), C(t["pill_bot"], t["pill_alpha"]))))
        p.setPen(QPen(C(t["err"] if ctx.rec else t["accent"], 170), 1))
        p.drawPath(path)
        p.save()
        p.setClipPath(path)
        p.setPen(QPen(C(t["accent"], 12), 1))
        for x in range(0, int(w), 12):
            p.drawLine(x, 0, x, int(h))
        p.setPen(QPen(C(t["accent"], 85), 1))
        for i, x in enumerate(range(8, int(w) - 8, 6)):
            p.drawLine(x, int(h) - 3, x, int(h) - (7 if i % 5 == 0 else 5))
        p.restore()
        p.setPen(QPen(C(t["accent"]), 2))
        for cx, cy, dx, dy in ((r.right(), r.top(), -1, 1), (r.left(), r.bottom(), 1, -1)):
            p.drawLine(QPointF(cx, cy + dy * 10), QPointF(cx, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx + dx * 10, cy))
        p.setPen(NOPEN)
        p.setBrush(C(t["accent"], 190))
        p.drawRect(QRectF(0, 18, 3, h - 36))
        p.drawRect(QRectF(w - 3, 18, 3, h - 36))

    def button(self, p, r, kind, t, st):
        color = t["err"] if st.recording else t["accent"]
        plate = chamfer_path(r.adjusted(1, 1, -1, -1), (7, 0, 7, 0))
        p.setBrush(C(color, 150 if st.recording else (60 if st.hover else 30)))
        p.setPen(QPen(C(color, 210), 1))
        p.drawPath(plate)
        if kind == "record":
            p.setPen(QPen(C(color, 130), 1))
            p.drawLine(QPointF(r.left() + 3, r.bottom() + 1), QPointF(r.right() - 3, r.bottom() + 1))

    def status(self, p, ctx, t):
        tr, cx, cy = ctx.track, ctx.track.center().x(), ctx.track.center().y()
        p.setPen(NOPEN)
        if ctx.state in ("idle", "settling"):
            for i in range(-3, 4):
                p.setBrush(C(t["accent"], 220 if i == 0 else 70 - abs(i) * 12))
                p.drawRect(QRectF(cx + i * 12 - 3, cy - 3, 6, 6))
        elif ctx.state == "transcribing":
            count = 21
            half = ctx.phase * count / 2
            for i in range(count):
                dist = abs(i - count // 2)
                alpha = int(235 * max(0.0, 1 - dist / max(half, 1))) if dist <= half else 30
                p.setBrush(C(t["accent"], max(alpha, 30)))
                p.drawRect(QRectF(cx + (i - count // 2) * 7 - 2.5, cy - 4, 5, 8))
        elif ctx.state == "success":
            p.setPen(QPen(C(t["accent"]), 2))
            p.setBrush(NOBRUSH)
            p.drawEllipse(QPointF(cx, cy), 10, 10)
            p.drawPolyline([QPointF(cx - 5, cy), QPointF(cx - 1, cy + 4), QPointF(cx + 5, cy - 4)])
        elif ctx.state == "error":
            p.setPen(QPen(C(t["err"]), 2))
            p.setBrush(NOBRUSH)
            p.drawPolygon(QPolygonF([QPointF(cx, cy - 10), QPointF(cx + 11, cy + 8), QPointF(cx - 11, cy + 8)]))
            p.drawLine(QPointF(cx, cy - 3), QPointF(cx, cy + 2))

    def wave(self, p, rect, levels, t):
        seg_wave(p, rect, levels, t, cell=2, gap=1)


class Wood(Skin):
    size = (300, 68)
    margins = (14, 9, 14, 12)
    record = 40
    trail = 32
    audio_margins = (10, 10)

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        r = QRectF(2, 2, w - 4, h - 8)
        p.setPen(NOPEN)
        p.setBrush(C("#000000", 95))
        p.drawRoundedRect(r.translated(0, 4), 13, 13)
        p.setBrush(QBrush(vgrad(r, C(t["pill_top"]), C(t["pill_bot"]))))
        p.setPen(QPen(C("#1a0b03", 230), 1.3))
        p.drawRoundedRect(r, 13, 13)
        clip = QPainterPath()
        clip.addRoundedRect(r, 13, 13)
        p.save()
        p.setClipPath(clip)
        p.setBrush(NOBRUSH)
        for i, y in enumerate(range(int(r.top()) + 2, int(r.bottom()), 3)):
            dark = i % 3 != 0
            p.setPen(QPen(C("#1a0900", 38 + (i % 4) * 9) if dark else C("#ffd9a0", 26), 1))
            grain = QPainterPath(QPointF(r.left(), y))
            grain.cubicTo(w * .28, y - 2 - i % 3, w * .62, y + 2 + i % 2, r.right(), y - 1 + i % 2)
            p.drawPath(grain)
        for k in range(4):  # knot
            p.setPen(QPen(C("#1a0900", 44), 1))
            p.drawEllipse(QPointF(w * .67, r.center().y() - 6), 14 + k * 5, 6 + k * 2.4)
        p.restore()
        p.setPen(QPen(C("#ffe1b0", 105), 1.2))
        p.drawLine(QPointF(r.left() + 13, r.top() + 1.5), QPointF(r.right() - 13, r.top() + 1.5))
        p.setPen(QPen(C("#000000", 90), 1.2))
        p.drawLine(QPointF(r.left() + 13, r.bottom() - 1.5), QPointF(r.right() - 13, r.bottom() - 1.5))
        for sx, sy in ((r.left() + 8, r.top() + 8), (r.right() - 8, r.top() + 8),
                       (r.left() + 8, r.bottom() - 8), (r.right() - 8, r.bottom() - 8)):
            self._screw(p, sx, sy)
        slot = ctx.track.adjusted(-3, 5, 3, -5)
        p.setPen(QPen(C("#000000", 140), 1.2))
        p.setBrush(C("#1b0c04", 150))
        p.drawRoundedRect(slot, 9, 9)
        p.setPen(QPen(C("#ffd9a0", 70), 1))
        p.drawLine(QPointF(slot.left() + 9, slot.bottom() + 1.5), QPointF(slot.right() - 9, slot.bottom() + 1.5))

    @staticmethod
    def _screw(p, x, y):
        grad = QRadialGradient(QPointF(x - 1, y - 1), 4.5)
        grad.setColorAt(0, C("#f3d58a"))
        grad.setColorAt(1, C("#7a5018"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(C("#2a1507"), 0.8))
        p.drawEllipse(QPointF(x, y), 3.3, 3.3)
        p.setPen(QPen(C("#2a1507", 220), 1))
        p.drawLine(QPointF(x - 2, y + 1.2), QPointF(x + 2, y - 1.2))

    def button(self, p, r, kind, t, st):
        radius = min(r.width(), r.height()) / 2 - 2
        c = r.center()
        off = 1.2 if st.pressed else 0
        p.setPen(NOPEN)
        p.setBrush(C("#000000", 115))
        p.drawEllipse(QPointF(c.x(), c.y() + 2), radius, radius)
        rg = QRadialGradient(QPointF(c.x() - radius * .3, c.y() - radius * .35 + off), radius * 1.25)
        rg.setColorAt(0, C("#fbe9a6"))
        rg.setColorAt(.45, C("#d6a443"))
        rg.setColorAt(1, C("#744a12"))
        p.setBrush(QBrush(rg))
        p.setPen(QPen(C("#341d07"), 1.3))
        p.drawEllipse(QPointF(c.x(), c.y() + off), radius, radius)
        dish = QLinearGradient(c.x(), c.y() - radius, c.x(), c.y() + radius)
        dish.setColorAt(0, C("#7d5216", 160))
        dish.setColorAt(1, C("#f3d98f", 140))
        p.setBrush(QBrush(dish))
        p.setPen(NOPEN)
        p.drawEllipse(QPointF(c.x(), c.y() + off), radius * .68, radius * .68)
        if st.recording:
            p.setBrush(NOBRUSH)
            p.setPen(QPen(C(t["err"], 230), 2.2))
            p.drawEllipse(QPointF(c.x(), c.y() + off), radius * .86, radius * .86)
        if st.hover:
            p.setPen(NOPEN)
            p.setBrush(C("#ffffff", 30))
            p.drawEllipse(QPointF(c.x(), c.y() + off), radius, radius)

    def status(self, p, ctx, t):
        tr, cx, cy = ctx.track, ctx.track.center().x(), ctx.track.center().y()
        if ctx.state in ("idle", "settling"):
            p.setPen(QPen(C("#000000", 130), 1))
            p.drawLine(QPointF(cx - 34, cy), QPointF(cx + 34, cy))
            p.setPen(QPen(C("#ffd9a0", 70), 1))
            p.drawLine(QPointF(cx - 34, cy + 1), QPointF(cx + 34, cy + 1))
            p.setPen(NOPEN)
            p.setBrush(C("#000000", 130))
            p.drawPolygon(QPolygonF([QPointF(cx, cy - 4), QPointF(cx + 4, cy), QPointF(cx, cy + 4), QPointF(cx - 4, cy)]))
            return
        if ctx.state == "transcribing":
            radius = max(4.0, ctx.phase * tr.width() / 2)
            glow = QRadialGradient(QPointF(cx, cy), radius)
            glow.setColorAt(0, C(t["glow"], int(210 * (1 - ctx.phase)) + 30))
            glow.setColorAt(1, C(t["glow"], 0))
            p.setPen(NOPEN)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(cx, cy), radius, min(radius, tr.height() / 2 - 3))
        default_status(p, ctx, t)

    def wave(self, p, rect, levels, t):
        bars(p, rect, levels, t, glow=True)


class Eco(Skin):
    size = (292, 62)
    margins = (14, 9, 14, 9)
    record = 40

    @staticmethod
    def _leaf(p, x, y, length, angle, alpha):
        p.save()
        p.translate(x, y)
        p.rotate(angle)
        leaf = QPainterPath(QPointF(0, 0))
        leaf.quadTo(length * .5, -length * .42, length, 0)
        leaf.quadTo(length * .5, length * .42, 0, 0)
        p.setPen(QPen(C("#b4ffc7", alpha), 0.8))
        p.setBrush(C("#7dff9b", alpha // 3))
        p.drawPath(leaf)
        p.drawLine(QPointF(0, 0), QPointF(length * .9, 0))
        p.restore()

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        r = QRectF(3, 3, w - 6, h - 6)
        for width, a in ((7, 18), (4, 36)):
            p.setBrush(NOBRUSH)
            p.setPen(QPen(C(t["glow"], a), width))
            p.drawRoundedRect(r, h / 2 - 3, h / 2 - 3)
        p.setBrush(QBrush(vgrad(r, C(t["pill_top"], 232), C(t["pill_bot"], 238))))
        p.setPen(QPen(C(t["err"] if ctx.rec else t["rim"], 190), 1.2))
        p.drawRoundedRect(r, h / 2 - 3, h / 2 - 3)
        path = QPainterPath()
        path.addRoundedRect(r, h / 2 - 3, h / 2 - 3)
        p.save()
        p.setClipPath(path)
        glow = QRadialGradient(QPointF(w / 2, h / 2), w * .42)
        glow.setColorAt(0, C(t["glow"], 46))
        glow.setColorAt(1, C(t["glow"], 0))
        p.setPen(NOPEN)
        p.setBrush(QBrush(glow))
        p.drawRect(r)
        self._leaf(p, r.left() + 62, r.bottom() + 2, 30, -52, 90)
        self._leaf(p, r.right() - 60, r.top() - 2, 30, 128, 90)
        self._leaf(p, r.center().x() + 30, r.bottom() + 3, 22, -110, 70)
        for i, (fx, fy) in enumerate(((.3, .3), (.52, .78), (.7, .22), (.83, .66), (.18, .72))):
            a = 90 + int(80 * math.sin(ctx.ms / 450 + i * 1.7))
            p.setBrush(C("#f4ffb0", max(a, 20)))
            p.drawEllipse(QPointF(w * fx, h * fy), 1.5, 1.5)
        p.restore()

    def button(self, p, r, kind, t, st):
        color = t["err"] if st.recording else t["accent"]
        radius = min(r.width(), r.height()) / 2 - 3
        c = r.center()
        if kind == "record" and st.disabled:  # busy: flat pale orb, dark icon stays readable
            p.setPen(QPen(C(t["glow"], 150), 1.4))
            p.setBrush(mix(color, "#ffffff", .62))
            p.drawEllipse(c, radius, radius)
            return
        if kind == "record":
            for extra, a in ((5, 22), (2.5, 42)):
                p.setPen(NOPEN)
                p.setBrush(C(color, a + (20 if st.hover else 0)))
                p.drawEllipse(c, radius + extra, radius + extra)
            rg = QRadialGradient(QPointF(c.x() - radius * .35, c.y() - radius * .4), radius * 1.4)
            rg.setColorAt(0, mix(color, "#ffffff", .55))
            rg.setColorAt(.55, C(color, 215))
            rg.setColorAt(1, mix(color, "#000000", .55))
            p.setBrush(QBrush(rg))
            p.setPen(QPen(C(color, 120), 1))
            p.drawEllipse(c, radius, radius)
        else:
            p.setPen(NOPEN)
            p.setBrush(C(t["accent"], 85 if st.hover else 38))
            p.drawEllipse(c, radius, radius)

    def status(self, p, ctx, t):
        tr, cx, cy = ctx.track, ctx.track.center().x(), ctx.track.center().y()
        if ctx.state in ("idle", "settling"):  # a tiny sprout
            p.setPen(QPen(C(t["accent"], 220), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            stem = QPainterPath(QPointF(cx, cy + 10))
            stem.quadTo(cx + 1, cy, cx, cy - 4)
            p.setBrush(NOBRUSH)
            p.drawPath(stem)
            self._leaf(p, cx, cy - 1, 11, -35, 230)
            self._leaf(p, cx, cy + 2, 10, -145, 230)
        elif ctx.state == "transcribing":  # ripples from the center
            p.setBrush(NOBRUSH)
            for k in range(3):
                f = (ctx.phase + k / 3) % 1
                p.setPen(QPen(C(t["glow"], int(190 * (1 - f))), 1.6))
                p.drawEllipse(QPointF(cx, cy), 6 + f * tr.width() * .4, 2 + f * tr.height() * .38)
        else:
            default_status(p, ctx, t)


class Lofi(Skin):
    size = (332, 76)
    margins = (12, 24, 12, 8)
    audio_margins = (40, 40)

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        r = QRectF(2, 2, w - 4, h - 4)
        p.setBrush(C("#000000", 70))
        p.setPen(NOPEN)
        p.drawRoundedRect(r.translated(2, 3), 10, 10)
        p.setBrush(QBrush(vgrad(r, C(t["pill_top"]), C(t["pill_bot"]))))
        p.setPen(QPen(C("#241c30", 230), 1.6))
        p.drawRoundedRect(r, 10, 10)
        label = QRectF(r.left() + 38, r.top() + 5, r.width() - 76, 15)
        p.setBrush(C("#f6e7da", 240))
        p.setPen(QPen(C("#241c30", 140), 1))
        p.drawRoundedRect(label, 3, 3)
        p.setPen(QPen(C(t["accent"], 220), 1.5))
        p.drawLine(QPointF(label.left() + 5, label.bottom() - 3), QPointF(label.right() - 5, label.bottom() - 3))
        font = QFont(t["font"], 7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(C("#4a3a5c"))
        p.drawText(label.adjusted(0, -1, 0, -3), CENTER, "lo-fi beats · side A")
        for sx, sy in ((r.left() + 8, r.top() + 8), (r.right() - 8, r.top() + 8),
                       (r.left() + 8, r.bottom() - 8), (r.right() - 8, r.bottom() - 8)):
            p.setPen(QPen(C("#241c30", 200), 1))
            p.setBrush(C("#d9c3b5"))
            p.drawEllipse(QPointF(sx, sy), 3, 3)
            p.drawLine(QPointF(sx - 2, sy), QPointF(sx + 2, sy))
        win = ctx.track.adjusted(-4, 0, 4, 0)
        p.setBrush(C("#1d1726", 240))
        p.setPen(QPen(C(t["rim"], 140), 1))
        p.drawRoundedRect(win, 8, 8)
        radius = min(win.height() / 2 - 4, 14.0)
        spin = math.radians(ctx.ms * .2) if ctx.state in ("recording", "transcribing") else 0.0
        reels = (QPointF(win.left() + radius + 6, win.center().y()), QPointF(win.right() - radius - 6, win.center().y()))
        p.setPen(QPen(C("#a98a6c", 200), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        tape_y = win.bottom() - 4  # below the reels, so the tape never runs into them
        p.drawLine(QPointF(win.left() + 14, tape_y), QPointF(win.right() - 14, tape_y))
        for index, c in enumerate(reels):
            p.setPen(QPen(C("#241c30"), 1))
            p.setBrush(C("#f6e7da", 235))
            p.drawEllipse(c, radius, radius)
            p.setBrush(C("#1d1726"))
            p.drawEllipse(c, radius * .42, radius * .42)
            p.setPen(QPen(C("#f6e7da"), 1.4))
            for k in range(6):
                a = spin * (1 if index == 0 else 1) + k * math.pi / 3
                p.drawLine(QPointF(c.x() + math.cos(a) * radius * .2, c.y() + math.sin(a) * radius * .2),
                           QPointF(c.x() + math.cos(a) * radius * .42, c.y() + math.sin(a) * radius * .42))

    def button(self, p, r, kind, t, st):
        color = t["err"] if st.recording else (t["accent"] if kind == "record" else "#f6e7da")
        off = 1 if st.pressed else 0
        rr = r.adjusted(2, 2, -3, -3)
        p.setPen(NOPEN)
        p.setBrush(C("#000000", 90))
        p.drawRoundedRect(rr.translated(2, 2), 10, 10)
        p.setBrush(mix(color, "#ffffff", .18) if st.hover else C(color))
        p.setPen(QPen(C("#241c30", 230), 1.6))
        p.drawRoundedRect(rr.translated(off, off), 10, 10)

    def status(self, p, ctx, t):
        if ctx.state in ("idle", "settling", "transcribing"):
            return
        tr, cx, cy = ctx.track, ctx.track.center().x(), ctx.track.center().y()
        if ctx.state == "success":  # a musical note
            p.setPen(NOPEN)
            p.setBrush(C(t["glow"]))
            p.drawEllipse(QPointF(cx - 3, cy + 6), 4.5, 3.5)
            p.setPen(QPen(C(t["glow"]), 2))
            p.drawLine(QPointF(cx + 1, cy + 5), QPointF(cx + 1, cy - 8))
            p.drawLine(QPointF(cx + 1, cy - 8), QPointF(cx + 7, cy - 5))
        else:
            default_status(p, ctx, t)


class Rpg(Skin):
    size = (312, 68)
    margins = (14, 10, 14, 10)
    record = 40
    antialias = False
    blinks = True
    HEART = ("01100110", "11111111", "11111111", "01111110", "00111100", "00011000")
    ARROW = ("1111111", "0111110", "0011100", "0001000")
    STAR = ("0001000", "0001000", "1111111", "0111110", "0011100", "0110110", "1100011")
    CROSS = ("1000001", "0100010", "0010100", "0001000", "0010100", "0100010", "1000001")

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        r = QRectF(1, 1, w - 2, h - 2)
        p.setPen(QPen(C("#0a0614"), 1))
        p.setBrush(C("#0a0614"))
        p.drawPath(stair_path(r, 3))
        inner = r.adjusted(3, 3, -3, -3)
        p.setBrush(QBrush(vgrad(inner, C(t["pill_top"]), C(t["pill_bot"]))))
        p.setPen(QPen(C(t["err"] if ctx.rec else t["rim"]), 3))
        p.drawPath(stair_path(inner, 3))
        p.setBrush(NOBRUSH)
        p.setPen(QPen(C(t["accent"], 150), 1))
        p.drawRect(inner.adjusted(5, 5, -5, -5))
        p.setPen(NOPEN)
        p.setBrush(C(t["accent"]))
        for cx, cy in ((9, 9), (w - 13, 9), (9, h - 13), (w - 13, h - 13)):
            p.drawRect(QRectF(cx, cy, 4, 4))

    def button(self, p, r, kind, t, st):
        base = t["err"] if st.recording else ("#4d3a7c" if not st.hover else "#5d4890")
        rr = r.adjusted(1, 1, -1, -1)
        off = 1 if st.pressed else 0
        p.setPen(NOPEN)
        p.setBrush(C("#0a0614"))
        p.drawPath(stair_path(rr, 2))
        inner = rr.adjusted(2, 2, -2, -2).translated(off, off)
        p.setBrush(C(base))
        p.drawRect(inner)
        p.setBrush(C("#ffffff", 100))
        p.drawRect(QRectF(inner.left(), inner.top(), inner.width(), 2))
        p.drawRect(QRectF(inner.left(), inner.top(), 2, inner.height()))
        p.setBrush(C("#000000", 110))
        p.drawRect(QRectF(inner.left(), inner.bottom() - 2, inner.width(), 2))
        p.drawRect(QRectF(inner.right() - 2, inner.top(), 2, inner.height()))

    def status(self, p, ctx, t):
        tr, cx, cy = ctx.track, ctx.track.center().x(), ctx.track.center().y()
        if ctx.state in ("idle", "settling"):
            for i in (-1, 0, 1):
                pixels(p, cx + i * 22, cy, self.HEART, 2, C(t["err"], 200 if ctx.blink or i else 90))
        elif ctx.state == "transcribing":
            lit = int(ctx.phase * 3) % 3
            p.setPen(NOPEN)
            for i in range(3):
                p.setBrush(C(t["glow"] if i == lit else t["muted"], 255 if i == lit else 110))
                p.drawRect(QRectF(cx - 22 + i * 16, cy - 4 - (4 if i == lit else 0), 8, 8))
        elif ctx.state == "success":
            pixels(p, cx, cy, self.STAR, 3, C(t["glow"]))
        elif ctx.state == "error":
            pixels(p, cx, cy, self.CROSS, 3, C(t["err"]))

    def wave(self, p, rect, levels, t):
        seg_wave(p, rect, levels, t, cell=3, gap=1)


class Stalker(Skin):
    size = (344, 94)
    margins = (16, 26, 16, 12)
    record = 46
    trail = 32
    audio_margins = (12, 12)

    def body(self, p, ctx, t):
        w, h = ctx.w, ctx.h
        case = QRectF(2, 16, w - 4, h - 20)
        for width, color in ((4.2, "#0a0a06"), (2.2, "#c9c9ae")):  # antenna with dark outline
            p.setPen(QPen(C(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(58, 16), QPointF(46, 2))
        p.setPen(NOPEN)
        p.setBrush(C(t["err"]))
        p.drawEllipse(QPointF(46, 2.5), 2.6, 2.6)
        p.setBrush(C("#1a1a12"))
        p.drawRect(QRectF(52, 13, 12, 5))
        p.setBrush(C("#000000", 110))
        p.drawRoundedRect(case.translated(0, 3), 5, 5)
        p.setBrush(QBrush(vgrad(case, C(t["pill_top"]), C(t["pill_bot"]))))
        p.setPen(QPen(C("#090a06"), 1.6))
        p.drawRoundedRect(case, 5, 5)
        clip = QPainterPath()
        clip.addRoundedRect(case, 5, 5)
        p.save()
        p.setClipPath(clip)
        p.setPen(NOPEN)
        for fx, fy, rx, ry, a in ((.2, .85, 38, 9, 46), (.78, .15, 30, 7, 38), (.55, .95, 46, 6, 40)):
            p.setBrush(C(t["err"], a))
            p.drawEllipse(QPointF(w * fx, 16 + (h - 20) * fy), rx, ry)
        p.setPen(QPen(C("#ffffff", 26), 1))
        for x1, y1, x2, y2 in ((30, 30, 62, 26), (210, 80, 260, 84), (120, 22, 150, 25), (290, 40, 318, 36)):
            p.drawLine(x1, y1, x2, y2)
        p.restore()
        p.setPen(QPen(C("#ffffff", 40), 1))
        p.drawLine(QPointF(case.left() + 6, case.top() + 1.5), QPointF(case.right() - 6, case.top() + 1.5))
        panel = case.adjusted(5, 5, -5, -5)
        p.setBrush(NOBRUSH)
        p.setPen(QPen(C("#000000", 110), 1))
        p.drawRoundedRect(panel, 3, 3)
        for rx, ry in ((panel.left(), panel.top()), (panel.right(), panel.top()),
                       (panel.left(), panel.bottom()), (panel.right(), panel.bottom()),
                       (panel.center().x() - 40, panel.top()), (panel.center().x() + 40, panel.bottom())):
            self._rivet(p, rx, ry)
        font = QFont("DejaVu Sans Mono", 7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(C(t["accent"], 150))
        p.drawText(QRectF(74, 17, 70, 10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Р-105М")
        win = ctx.track.adjusted(-4, 3, 4, -3)
        p.setBrush(QBrush(vgrad(win, C("#171204"), C("#3d300c"))))
        p.setPen(QPen(C("#000000", 220), 2))
        p.drawRoundedRect(win, 3, 3)
        font = QFont("DejaVu Sans Mono", 6)
        p.setFont(font)
        for i, x in enumerate(range(int(win.left()) + 8, int(win.right()) - 6, 5)):
            major = i % 5 == 0
            p.setPen(QPen(C(t["accent"], 175 if major else 95), 1))
            p.drawLine(QPointF(x, win.bottom() - 3), QPointF(x, win.bottom() - (10 if major else 6)))
            if i % 10 == 0:
                p.setPen(C(t["accent"], 130))
                p.drawText(QRectF(x - 8, win.top() + 1, 16, 9), CENTER, str(4 + i // 5))
        p.setPen(QPen(C("#ffffff", 45), 1))
        p.drawLine(QPointF(win.left() + 4, win.top() + 1.5), QPointF(win.right() - 4, win.top() + 1.5))
        self._lamp(p, ctx, t, QPointF(w - 24, 31))

    @staticmethod
    def _rivet(p, x, y):
        grad = QRadialGradient(QPointF(x - .8, y - .8), 3.6)
        grad.setColorAt(0, C("#c8c8aa"))
        grad.setColorAt(1, C("#3a3a2a"))
        p.setPen(QPen(C("#000000", 150), 0.7))
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(x, y), 2.3, 2.3)

    @staticmethod
    def _lamp(p, ctx, t, c):
        state = ctx.state
        if state == "error" or state == "recording":
            color, on = t["err"], True
        elif state == "success":
            color, on = "#8fdc5a", True
        elif state == "transcribing":
            color, on = t["glow"], ctx.phase < .5
        else:
            color, on = t["glow"], False
        if on:
            p.setPen(NOPEN)
            p.setBrush(C(color, 55))
            p.drawEllipse(c, 9, 9)
        rg = QRadialGradient(QPointF(c.x() - 1.2, c.y() - 1.2), 5)
        rg.setColorAt(0, C(color) if on else C("#6b5a22"))
        rg.setColorAt(1, mix(color, "#000000", .55) if on else C("#2a2208"))
        p.setPen(QPen(C("#000000", 220), 1))
        p.setBrush(QBrush(rg))
        p.drawEllipse(c, 4.5, 4.5)

    def button(self, p, r, kind, t, st):
        if kind == "record":
            self._knob(p, r, t, st)
            return
        plate = r.adjusted(3, 5, -3, -5)
        off = 1 if st.pressed else 0
        p.setPen(QPen(C("#000000", 220), 1.2))
        p.setBrush(QBrush(vgrad(plate, C("#6a6b52" if st.hover else "#575842"), C("#2b2c1f"))))
        p.drawRoundedRect(plate.translated(0, off), 3, 3)
        p.setPen(QPen(C("#ffffff", 55), 1))
        p.drawLine(QPointF(plate.left() + 3, plate.top() + 1.5 + off), QPointF(plate.right() - 3, plate.top() + 1.5 + off))
        self._rivet(p, plate.left() + 3.5, plate.top() + 3.5 + off)
        self._rivet(p, plate.right() - 3.5, plate.bottom() - 3.5 + off)

    def _knob(self, p, r, t, st):
        c = r.center()
        radius = min(r.width(), r.height()) / 2 - 2
        if st.recording:
            p.setPen(NOPEN)
            p.setBrush(C(t["err"], 70))
            p.drawEllipse(c, radius + 2, radius + 2)
        p.setPen(NOPEN)
        p.setBrush(C("#000000", 130))
        p.drawEllipse(QPointF(c.x(), c.y() + 2), radius, radius)
        p.setBrush(C("#17170f"))
        p.setPen(QPen(C("#000000"), 1.2))
        p.drawEllipse(c, radius, radius)
        p.setPen(QPen(C("#5a5b44"), 1.4))
        for k in range(30):  # knurled edge
            a = k * 2 * math.pi / 30
            p.drawLine(QPointF(c.x() + math.cos(a) * (radius - 3.2), c.y() + math.sin(a) * (radius - 3.2)),
                       QPointF(c.x() + math.cos(a) * radius, c.y() + math.sin(a) * radius))
        face = radius - 4
        rg = QRadialGradient(QPointF(c.x() - face * .3, c.y() - face * .35), face * 1.3)
        rg.setColorAt(0, C("#a3a38a" if st.hover else "#8a8a72"))
        rg.setColorAt(1, C("#2d2d21"))
        p.setPen(QPen(C("#000000", 200), 1))
        p.setBrush(QBrush(rg))
        p.drawEllipse(c, face, face)
        angle = math.radians(35 if st.recording else -50)
        p.setPen(QPen(C(t["err"] if st.recording else t["accent"], 235), 2.6, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(c.x() + math.cos(angle) * face * .55, c.y() + math.sin(angle) * face * .55),
                   QPointF(c.x() + math.cos(angle) * face * .92, c.y() + math.sin(angle) * face * .92))

    def status(self, p, ctx, t):
        win = ctx.track.adjusted(-4, 3, 4, -3)
        if ctx.state == "transcribing":
            f = .5 + .5 * math.sin(ctx.phase * 2 * math.pi)
        elif ctx.state in ("success", "error"):
            f = .5
        else:
            f = .42
        x = win.left() + 10 + f * (win.width() - 20)
        p.setPen(QPen(C(t["err"], 60), 4))
        p.drawLine(QPointF(x, win.top() + 3), QPointF(x, win.bottom() - 2))
        p.setPen(QPen(C(t["err"], 240), 1.5))
        p.drawLine(QPointF(x, win.top() + 2), QPointF(x, win.bottom() - 1))

    def wave(self, p, rect, levels, t):
        p.setPen(QPen(C(t["ink"], 230), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        for index, level in enumerate(levels):
            half = 1 + level * (rect.height() / 2 - 1)
            x = index * 6 + 1.5
            p.drawLine(QPointF(x, rect.height() / 2 - half), QPointF(x, rect.height() / 2 + half))


SKINS = {
    "glass": Glass(), "terminal": Terminal(), "hud": Hud(), "wood": Wood(),
    "eco": Eco(), "lofi": Lofi(), "rpg": Rpg(), "stalker": Stalker(),
}


def skin_for(theme: dict) -> Skin:
    return SKINS[theme["style"]]
