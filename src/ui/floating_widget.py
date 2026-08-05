from PySide6.QtCore import Qt, Signal, QTimer

from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QIcon, QPixmap, QAction, QLinearGradient
)

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, QMenu,
    QApplication
)


def _create_history_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(
        QColor("#38BDF8"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
    )
    painter.setPen(pen)
    painter.drawLine(8, 7, 19, 7)
    painter.drawLine(8, 12, 19, 12)
    painter.drawLine(8, 17, 15, 17)
    painter.setBrush(QBrush(QColor("#38BDF8")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 6, 2, 2)
    painter.drawEllipse(4, 11, 2, 2)
    painter.drawEllipse(4, 16, 2, 2)
    painter.end()
    return QIcon(pixmap)


def _create_trash_quit_icon() -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(
        QColor("#F87171"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
    )
    painter.setPen(pen)
    painter.drawLine(5, 6, 19, 6)
    painter.drawLine(9, 4, 15, 4)
    painter.drawLine(7, 6, 8, 19)
    painter.drawLine(17, 6, 16, 19)
    painter.drawLine(8, 19, 16, 19)
    painter.drawLine(10, 9, 10, 16)
    painter.drawLine(14, 9, 14, 16)
    painter.end()
    return QIcon(pixmap)


def _create_pin_icon(pinned: bool = False) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#38BDF8") if pinned else QColor("#94A3B8")
    pen = QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(8, 4, 8, 8)
    painter.drawLine(12, 12, 12, 20)
    painter.drawLine(6, 12, 18, 12)
    painter.end()
    return QIcon(pixmap)


class AudioWaveformWidget(QWidget):
    """Custom widget rendering 5 centered animated equalizer bars."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 22)
        self._target_level = 0.0
        self._current_levels = [0.12] * 5

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 FPS
        self._timer.timeout.connect(self._animate_step)

    def set_volume_level(self, level: float):
        self._target_level = level
        if not self._timer.isActive():
            self._timer.start()

    def start_animating(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop_animating(self):
        self._timer.stop()
        self._target_level = 0.0
        self._current_levels = [0.12] * 5
        self.update()

    def _animate_step(self):
        variations = [0.75, 1.15, 1.4, 1.05, 0.8]
        decay = 0.35
        all_low = True

        for i in range(5):
            target = max(0.12, min(1.0, self._target_level * variations[i]))
            self._current_levels[i] += (
                target - self._current_levels[i]
            ) * decay
            if self._current_levels[i] > 0.15:
                all_low = False

        self.update()
        if all_low and self._target_level <= 0.01:
            self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Red accent gradient for modern aesthetic
        brush = QBrush(QColor("#EF4444"))
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)

        w = self.width()
        h = self.height()
        bar_w = 4.5
        spacing = 4.0
        total_w = 5 * bar_w + 4 * spacing
        start_x = (w - total_w) / 2.0

        for i, lvl in enumerate(self._current_levels):
            bar_h = max(4.0, h * lvl)
            x = start_x + i * (bar_w + spacing)
            y = (h - bar_h) / 2.0
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2.0, 2.0)

        painter.end()


class FloatingPillWidget(QWidget):
    open_history_requested = Signal()
    toggle_recording_requested = Signal()
    quit_requested = Signal()
    always_on_top_changed = Signal(bool)

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.always_on_top = True
        self._apply_window_flags()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("FloatingPill")

        # idle, recording, transcribing, success, error
        self.status_state = "idle"

        # Shimmer animation for transcribing state
        self._shimmer_offset = 0.0
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(30)
        self._shimmer_timer.timeout.connect(self._step_shimmer)

        self._init_ui()
        self._init_system_tray()

    def _step_shimmer(self):
        self._shimmer_offset = (self._shimmer_offset + 0.025) % 1.0
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
        self.btn_pin.setIcon(_create_pin_icon(enable))
        if enable:
            self.btn_pin.setToolTip("Fixado no topo (Clique para desafixar)")
            self.btn_pin.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 189, 248, 0.35);
                    border: 1px solid rgba(56, 189, 248, 0.7);
                    border-radius: 6px;
                }
            """)
        else:
            self.btn_pin.setToolTip(
                "Desafixado do topo (Clique para fixar no topo)"
            )
            self.btn_pin.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.08);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-radius: 6px;
                }
            """)
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
            x = (screen.width() - self.width()) // 2
            y = 70
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

    def _init_ui(self):
        self.setFixedSize(350, 46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 4, 10, 4)
        layout.setSpacing(6)

        # Audio Waveform Equalizer Widget
        self.waveform_widget = AudioWaveformWidget(self)
        self.waveform_widget.hide()

        # Status Text (Portuguese user-facing text)
        self.status_label = QLabel("Pronto para Gravar", self)
        self.status_label.setObjectName("StatusText")
        self.status_label.setStyleSheet(
            "color: #94A3B8; font-size: 12px; font-weight: 500;"
        )

        # Pin / Always-On-Top Button
        self.btn_pin = QPushButton(self)
        self.btn_pin.setIcon(_create_pin_icon(True))
        self.btn_pin.setToolTip("Fixado sempre no topo (Clique para alternar)")
        self.btn_pin.setFixedSize(30, 30)
        self.btn_pin.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.35);
                border: 1px solid rgba(56, 189, 248, 0.7);
                border-radius: 6px;
            }
        """)
        self.btn_pin.clicked.connect(self._toggle_pin)

        # History Button
        self.btn_history = QPushButton(self)
        self.btn_history.setIcon(_create_history_icon())
        self.btn_history.setToolTip("Abrir Histórico e Configurações")
        self.btn_history.setFixedSize(30, 30)
        self.btn_history.setStyleSheet("""
            QPushButton {
                background-color: rgba(2, 132, 199, 0.25);
                border: 1px solid rgba(56, 189, 248, 0.4);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(2, 132, 199, 0.75);
                border-color: rgba(56, 189, 248, 0.9);
            }
        """)
        self.btn_history.clicked.connect(self.open_history_requested.emit)

        # Quit Button
        self.btn_quit = QPushButton(self)
        self.btn_quit.setIcon(_create_trash_quit_icon())
        self.btn_quit.setToolTip("Sair e Encerrar o Aplicativo (Lixeira/Sair)")
        self.btn_quit.setFixedSize(30, 30)
        self.btn_quit.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.25);
                border: 1px solid rgba(248, 113, 113, 0.4);
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.85);
                border-color: rgba(248, 113, 113, 0.9);
            }
        """)
        self.btn_quit.clicked.connect(self.quit_requested.emit)

        layout.addWidget(self.status_label, 1)
        layout.addWidget(
            self.waveform_widget, 1, Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(self.btn_pin)
        layout.addWidget(self.btn_history)
        layout.addWidget(self.btn_quit)

    def set_status(self, state: str, message: str = ""):
        self.status_state = state

        if state == "transcribing":
            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        else:
            self._shimmer_timer.stop()
            self._shimmer_offset = 0.0

        if state == "recording":
            self.status_label.hide()
            self.waveform_widget.show()
            self.waveform_widget.start_animating()
        else:
            self.waveform_widget.stop_animating()
            self.waveform_widget.hide()
            self.status_label.show()

            if state == "idle":
                self.status_label.setText("Pronto para Gravar")
                self.status_label.setStyleSheet(
                    "color: #94A3B8; font-weight: 500;"
                )
            elif state == "transcribing":
                self.status_label.setText("Processando IA...")
                self.status_label.setStyleSheet(
                    "color: #F59E0B; font-weight: 600;"
                )
            elif state == "success":
                self.status_label.setText("✓ Transcrição copiada!")
                self.status_label.setStyleSheet(
                    "color: #10B981; font-weight: 700;"
                )
            elif state == "error":
                self.status_label.setText("✕ Erro na transcrição")
                self.status_label.setStyleSheet(
                    "color: #F87171; font-weight: 700;"
                )
            else:
                self.status_label.setText(message if message else state)
                self.status_label.setStyleSheet(
                    "color: #94A3B8; font-weight: 500;"
                )

        self.update()

    def update_volume_level(self, level: float):
        if self.status_state == "recording":
            self.waveform_widget.set_volume_level(level)

        self.update()

    def position_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 70
        self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base translucent glass background
        rect = self.rect().adjusted(1, 1, -1, -1)
        bg_color = QColor(15, 23, 42, 240)
        border_color = QColor(255, 255, 255, 45)

        if self.status_state == "recording":
            border_color = QColor(239, 68, 68, 220)
        elif self.status_state == "transcribing":
            border_color = QColor(245, 158, 11, 220)
        elif self.status_state == "success":
            border_color = QColor(16, 185, 129, 220)
        elif self.status_state == "error":
            border_color = QColor(248, 113, 113, 220)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(rect, 20, 20)

        # Transcribing Glassmorphism Shimmer Light Sweep Overlay
        if self.status_state == "transcribing":
            shimmer_grad = QLinearGradient(0, 0, self.width(), 0)
            off = self._shimmer_offset
            shimmer_grad.setColorAt(
                max(0.0, off - 0.2), QColor(245, 158, 11, 0)
            )
            shimmer_grad.setColorAt(off, QColor(245, 158, 11, 50))
            shimmer_grad.setColorAt(
                min(1.0, off + 0.2), QColor(245, 158, 11, 0)
            )

            painter.setBrush(QBrush(shimmer_grad))
            painter.setPen(Qt.PenStyle.NoPen)
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

        icon_pixmap = QPixmap(32, 32)
        icon_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor("#0284C7")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        self.tray_icon.setIcon(QIcon(icon_pixmap))
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
