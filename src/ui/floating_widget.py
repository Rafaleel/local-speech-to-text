from PySide6.QtCore import Qt, Signal, QTimer, QElapsedTimer, QSize, QRect, QRectF, QPointF

from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QIcon, QPixmap, QAction, QLinearGradient, QPainterPath, QPolygonF
)

from types import SimpleNamespace

from src.ui import skins, themes

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, QMenu,
    QApplication, QMessageBox, QStackedWidget, QSizePolicy
)


def create_icon(kind: str, color: str = "") -> QIcon:
    color = color or themes.active()["text"]
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "mic":
        painter.drawRoundedRect(9, 3, 6, 12, 3, 3)
        painter.drawArc(6, 7, 12, 12, 180 * 16, 180 * 16)
        painter.drawLine(12, 19, 12, 22)
        painter.drawLine(8, 22, 16, 22)
    elif kind == "stop":
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(6, 6, 12, 12, 2, 2)
    elif kind == "history":
        painter.drawEllipse(4, 4, 16, 16)
        painter.drawLine(12, 7, 12, 12)
        painter.drawLine(12, 12, 16, 14)
    elif kind == "settings":
        for y, x in ((6, 9), (12, 15), (18, 11)):
            painter.drawLine(4, y, 20, y)
            painter.setBrush(QColor("#171e25"))
            painter.drawEllipse(QRectF(x - 2.5, y - 2.5, 5, 5))
    elif kind == "copy":
        painter.drawRoundedRect(8, 8, 12, 13, 2, 2)
        painter.drawLine(5, 16, 4, 16)
        painter.drawLine(4, 16, 4, 3)
        painter.drawLine(4, 3, 15, 3)
    elif kind == "close":
        painter.drawLine(7, 7, 17, 17)
        painter.drawLine(17, 7, 7, 17)
    else:
        painter.setBrush(QColor(color))
        for x in (5, 12, 19):
            painter.drawEllipse(QRectF(x - 1.8, 10.2, 3.6, 3.6))
    painter.end()
    return QIcon(pixmap)


class ThemedButton(QPushButton):
    """Button whose face is painted by the active skin (knob, plate, bracket, pixel key...)."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # mouse clicks must not leave a focus box

    def paintEvent(self, event):
        t = themes.active()
        skin = skins.skin_for(t)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, skin.antialias)
        state = SimpleNamespace(
            hover=self.underMouse() and self.isEnabled(), pressed=self.isDown(),
            disabled=not self.isEnabled(), recording=bool(self.property("recording")),
        )
        skin.button(painter, QRectF(self.rect()), self.kind, t, state)
        size = self.iconSize()
        shift = 1 if state.pressed else 0
        self.icon().paint(painter, QRect((self.width() - size.width()) // 2,
                                         (self.height() - size.height()) // 2 + shift,
                                         size.width(), size.height()))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(t["focus"]), 1.5))
            painter.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        painter.end()


class AudioWaveformWidget(QWidget):
    """Display recent microphone levels from left to right."""

    BAR_COUNT = 15

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(89, 20)
        self._target_level = 0.0
        self._levels = [0.0] * self.BAR_COUNT
        self._timer = QTimer(self)
        self._timer.setInterval(42)
        self._timer.timeout.connect(self._sample_level)

    def set_volume_level(self, level: float):
        self._target_level = level

    def start_animating(self):
        self._timer.start()

    def stop_animating(self):
        self._timer.stop()
        self._target_level = 0.0
        self._levels = [0.0] * self.BAR_COUNT
        self.update()

    def _sample_level(self):
        self._levels = self._levels[1:] + [self._target_level]
        self.update()

    def paintEvent(self, event):
        t = themes.active()
        skin = skins.skin_for(t)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, skin.antialias)
        skin.wave(painter, QRectF(self.rect()), self._levels, t)
        painter.end()


class FloatingPillWidget(QWidget):
    open_history_requested = Signal()
    open_settings_requested = Signal()
    toggle_recording_requested = Signal()
    quit_requested = Signal()
    retry_requested = Signal()
    cancel_recording_requested = Signal()
    always_on_top_changed = Signal(bool)

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.always_on_top = True
        self._apply_window_flags()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("FloatingPill")
        self.setWindowRole("voice-to-text-pill")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus(Qt.FocusReason.OtherFocusReason)

        # idle, recording, transcribing, success, error
        self.status_state = "idle"
        self._error_detail = ""
        self._elapsed = QElapsedTimer()
        self._record_timer = QTimer(self)
        self._record_timer.setInterval(250)
        self._record_timer.timeout.connect(self._update_elapsed)

        # Indeterminate activity indicator.
        self._activity_phase = 0.0
        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(30)
        self._activity_timer.timeout.connect(self._step_activity)

        # Always-running clock (reel spin, twinkles) and a slow blink for idle cursors.
        self._clock = QElapsedTimer()
        self._clock.start()
        self._blink = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(530)
        self._blink_timer.timeout.connect(self._step_blink)

        self._init_ui()
        self._init_system_tray()

    def _step_blink(self):
        self._blink = not self._blink
        self.update()

    def _step_activity(self):
        self._activity_phase = (self._activity_phase + 0.025) % 1.0
        self.update()

    def _apply_window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_always_on_top(self, enable: bool):
        current_pos = self.pos()
        self.always_on_top = enable
        self._apply_window_flags()
        self.pin_action.setChecked(enable)
        # Keep exact position without recentering popup
        self.move(current_pos)
        self.show()

    def _toggle_pin(self):
        new_state = not self.always_on_top
        self.set_always_on_top(new_state)
        self.always_on_top_changed.emit(new_state)

    def apply_position_preset(self, preset: str):
        screen = QApplication.primaryScreen().availableGeometry()
        if preset == "top":
            x = screen.x() + (screen.width() - self.width()) // 2
            y = screen.y() + 70
            self.move(x, y)
        elif preset == "saved" and self.db:
            saved_x = self.db.get_setting("pill_x", "")
            saved_y = self.db.get_setting("pill_y", "")
            if saved_x and saved_y:
                try:
                    sx, sy = int(saved_x), int(saved_y)
                    if screen.contains(sx, sy):
                        self.move(sx, sy)
                        return
                except ValueError:
                    pass
            self.position_bottom_center()

        else:
            self.position_bottom_center()

    def _button(self, icon, label, callback):
        button = ThemedButton("cancel" if icon == "close" else "more", self)
        button.setIcon(create_icon(icon, themes.icon_color()))
        button.setIconSize(QSize(17, 17))
        button.setFixedSize(32, 32)
        button.setObjectName("PillAction")
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.clicked.connect(callback)
        return button

    def _init_ui(self):
        controls = QHBoxLayout(self)
        self.controls = controls

        self.btn_record = ThemedButton("record", self)
        self.btn_record.setObjectName("RecordButton")
        self.btn_record.setIconSize(QSize(18, 18))
        self.btn_record.clicked.connect(self.toggle_recording_requested.emit)
        controls.addWidget(self.btn_record)

        self.body = QStackedWidget(self)
        self.body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label = QLabel(self.body)
        self.status_label.setObjectName("StatusText")
        self.body.addWidget(self.status_label)

        self.audio_panel = QWidget(self.body)
        self.audio_panel.setObjectName("PillAudioPanel")
        audio_layout = QHBoxLayout(self.audio_panel)
        self.audio_layout = audio_layout
        audio_layout.setSpacing(8)
        self.clock = QLabel("00:00", self.audio_panel)
        self.clock.setObjectName("PillClock")
        self.clock.setAccessibleName("Tempo de gravação")
        audio_layout.addWidget(self.clock)
        audio_layout.addStretch(1)
        self.waveform_widget = AudioWaveformWidget(self.audio_panel)
        audio_layout.addWidget(self.waveform_widget)
        self.body.addWidget(self.audio_panel)
        controls.addWidget(self.body, 1)

        self.trailing_controls = QStackedWidget(self)
        self.btn_cancel = self._button(
            "close", "Descartar gravação (Esc)", self.cancel_recording_requested.emit
        )
        self.trailing_controls.addWidget(self.btn_cancel)
        self.btn_more = self._button("more", "Mais opções", lambda: None)
        menu = QMenu(self)
        menu.setObjectName("PillMenu")
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        menu.addAction("Histórico", self.open_history_requested.emit)
        menu.addAction("Configurações", self.open_settings_requested.emit)
        menu.addSeparator()
        self.pin_action = menu.addAction("Manter sempre no topo")
        self.pin_action.setCheckable(True)
        self.pin_action.setChecked(self.always_on_top)
        self.pin_action.triggered.connect(self.set_always_on_top)
        self.pin_action.triggered.connect(self.always_on_top_changed.emit)
        self.detail_action = menu.addAction("Detalhes do erro", self._show_error)
        self.detail_action.setVisible(False)
        self.retry_action = menu.addAction("Tentar transcrever novamente", self.retry_requested.emit)
        self.retry_action.setVisible(False)
        menu.addSeparator()
        menu.addAction("Sair do aplicativo", self.quit_requested.emit)
        self.btn_more.setMenu(menu)
        self.trailing_controls.addWidget(self.btn_more)
        controls.addWidget(self.trailing_controls)
        self._apply_skin_geometry()
        self.set_status("idle")

    def _apply_skin_geometry(self):
        skin = skins.skin_for(themes.active())
        self.setFixedSize(*skin.size)
        self.controls.setContentsMargins(*skin.margins)
        self.controls.setSpacing(skin.spacing)
        self.btn_record.setFixedSize(skin.record, skin.record)
        self.btn_record.setIconSize(QSize(18, 18))
        self.trailing_controls.setFixedSize(skin.trail, skin.trail)
        for button in (self.btn_cancel, self.btn_more):
            button.setFixedSize(skin.trail, skin.trail)
        self.audio_layout.setContentsMargins(skin.audio_margins[0], 0, skin.audio_margins[1], 0)
        self.controls.activate()  # lay out now so painting never uses stale geometry

    def _show_error(self):
        QMessageBox.warning(self, "Detalhes do erro", self._error_detail)

    def _update_elapsed(self):
        seconds = self._elapsed.elapsed() // 1000
        self.clock.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")

    def set_status(self, state: str, message: str = ""):
        t = themes.active()
        previous = self.status_state
        self.status_state = state
        recording = state == "recording"
        enabled = state not in ("transcribing", "review")
        self.btn_record.setEnabled(enabled)
        self.btn_record.setProperty("recording", recording)
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)
        self.btn_record.setIcon(create_icon(
            "stop" if recording else "mic",
            (t["icon_on"] if recording else themes.icon_color())
            if enabled else (t["glow"] if t["style"] == "glass" else themes.icon_color())
        ))
        label = "Parar e transcrever" if recording else "Ditar (Ctrl+Espaço)"
        self.btn_record.setToolTip(label)
        self.btn_record.setAccessibleName(label)
        self.body.setCurrentWidget(self.audio_panel if recording else self.status_label)
        self.trailing_controls.setCurrentWidget(self.btn_cancel if recording else self.btn_more)
        self.detail_action.setVisible(state == "error")
        self.retry_action.setVisible(False)
        self._activity_timer.stop()
        self._record_timer.stop()
        self._blink_timer.stop()
        if skins.skin_for(t).blinks and state in ("idle", "settling"):
            self._blink = True
            self._blink_timer.start()
        if recording:
            if previous != "recording":
                self._elapsed.start()
                self.waveform_widget.start_animating()
            self._record_timer.start()
            self._update_elapsed()
        else:
            self.waveform_widget.stop_animating()
            defaults = {
                "idle": "Ditar",
                "settling": "Pronto para ditar",
                "transcribing": "Transcrevendo…",
                "success": "Salvo no histórico",
                "error": "Falha na transcrição",
            }
            text = message if message and state != "error" else defaults.get(state, state)
            self.status_label.setText("")  # state is painted in paintEvent; text stays as tooltip
            self.status_label.setToolTip(text)
            self.status_label.setAccessibleName(text)
            if state == "transcribing":
                self._activity_timer.start()
            if state == "error":
                self._error_detail = message or "Ocorreu um erro ao transcrever."
        self.update()

    def apply_theme(self):
        """Rebuild pixmap icons and repaint after the active theme changed."""
        for button, icon in ((self.btn_cancel, "close"), (self.btn_more, "more")):
            button.setIcon(create_icon(icon, themes.icon_color()))
        self._apply_skin_geometry()
        self.set_status(self.status_state)

    def update_volume_level(self, level: float):
        if self.status_state == "recording":
            self.waveform_widget.set_volume_level(level)

        self.update()

    def position_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.bottom() - self.height() - 70
        self.move(x, y)

    def paintEvent(self, event):
        t = themes.active()
        skin = skins.skin_for(t)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, skin.antialias)
        ctx = SimpleNamespace(
            state=self.status_state, rec=self.status_state == "recording", phase=self._activity_phase,
            blink=self._blink, ms=self._clock.elapsed(), w=self.width(), h=self.height(),
            track=QRectF(self.body.geometry()),
        )
        skin.body(painter, ctx, t)
        if ctx.state != "recording":
            skin.status(painter, ctx, t)
        painter.end()

    # Dragging logic with Wayland support via startSystemMove
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:

            win_handle = self.windowHandle()
            if win_handle and hasattr(win_handle, "startSystemMove"):
                win_handle.startSystemMove()
            event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.db:
            pos = self.pos()
            self.db.set_setting("pill_x", str(pos.x()))
            self.db.set_setting("pill_y", str(pos.y()))
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.open_history_requested.emit()

    # System Tray Integration
    def _init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)

        self.tray_icon.setIcon(create_icon("mic", "#f47987"))
        self.tray_icon.setToolTip("Voice-to-Text (Whisper)")

        tray_menu = QMenu()

        action_history = QAction("Histórico de Transcrições", self)
        action_history.triggered.connect(self.open_history_requested.emit)

        action_toggle = QAction("Iniciar/Parar Gravação", self)
        action_toggle.triggered.connect(self.toggle_recording_requested.emit)

        action_quit = QAction("Sair", self)
        action_quit.triggered.connect(self.quit_requested.emit)

        tray_menu.addAction(action_history)
        tray_menu.addAction(action_toggle)
        tray_menu.addSeparator()
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
