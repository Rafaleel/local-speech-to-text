from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea,
    QPushButton, QLabel, QTabWidget, QWidget,
    QComboBox, QCheckBox, QMessageBox
)
from src.db.database import DatabaseManager
from src.utils.injector import TextInjector


class HistoryWindow(QDialog):
    settings_changed = Signal()

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Voice-to-Text - Histórico & Configurações")
        self.setMinimumSize(580, 500)
        self.resize(640, 560)

        self._init_ui()
        self.refresh_history()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)

        tabs = QTabWidget(self)

        # Tab 1: History
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText(
            "🔍 Buscar no histórico de transcrições..."
        )
        self.search_input.textChanged.connect(self.refresh_history)
        search_layout.addWidget(self.search_input)

        btn_refresh = QPushButton("🔄 Atualizar", self)
        btn_refresh.setToolTip("Atualizar lista de transcrições")
        btn_refresh.clicked.connect(self.refresh_history)
        search_layout.addWidget(btn_refresh)

        btn_clear = QPushButton("Limpar Histórico", self)
        btn_clear.setObjectName("DangerButton")
        btn_clear.clicked.connect(self._clear_all_history)
        search_layout.addWidget(btn_clear)

        history_layout.addLayout(search_layout)

        # Scroll Area for history cards
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 0, 4)
        self.scroll_layout.setSpacing(10)

        self.scroll_area.setWidget(self.scroll_content)
        history_layout.addWidget(self.scroll_area)

        # Tab 2: Settings (Scrollable)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(14)

        # Language Selection
        lbl_language = QLabel("<b>Idioma da Transcrição:</b>", self)
        self.combo_language = QComboBox(self)
        self.combo_language.addItem(
            "Automático (Detectar idioma do áudio - Padrão)", "auto")
        self.combo_language.addItem("Português (PT)", "pt")
        self.combo_language.addItem("Inglês (EN)", "en")
        self.combo_language.addItem("Espanhol (ES)", "es")

        current_language = self.db.get_setting("language", "auto")
        index_lang = self.combo_language.findData(current_language)
        if index_lang >= 0:
            self.combo_language.setCurrentIndex(index_lang)

        # Hotkey Mode
        lbl_mode = QLabel("<b>Modo de Ativação do Atalho:</b>", self)
        self.combo_mode = QComboBox(self)
        self.combo_mode.addItem(
            "Alternar (Pressiona para iniciar / Pressiona para parar)",
            "toggle"
        )
        self.combo_mode.addItem("Segurar para Falar (Hold-to-Talk)", "hold")

        current_mode = self.db.get_setting("hotkey_mode", "toggle")
        index = self.combo_mode.findData(current_mode)
        if index >= 0:
            self.combo_mode.setCurrentIndex(index)

        # Device
        lbl_device = QLabel(
            "<b>Dispositivo de Inferência (Whisper):</b>", self
        )
        self.combo_device = QComboBox(self)
        self.combo_device.addItem(
            "NVIDIA CUDA (GPU 8GB VRAM - Recomendado)", "cuda"
        )
        self.combo_device.addItem("CPU (Processador)", "cpu")

        current_device = self.db.get_setting("device", "cuda")
        index_dev = self.combo_device.findData(current_device)
        if index_dev >= 0:
            self.combo_device.setCurrentIndex(index_dev)

        # Model Size
        lbl_model = QLabel("<b>Modelo Whisper:</b>", self)
        self.combo_model = QComboBox(self)
        self.combo_model.addItem(
            "large-v3-turbo (Melhor para PT/EN, ultrarrápido)",
            "large-v3-turbo"
        )
        self.combo_model.addItem(
            "large-v3 (Precisão máxima)", "openai/whisper-large-v3"
        )
        self.combo_model.addItem("small (Rápido e leve)", "small")
        self.combo_model.addItem("base (Ultra leve)", "base")

        current_model = self.db.get_setting("model_size", "large-v3-turbo")
        index_mod = self.combo_model.findData(current_model)
        if index_mod >= 0:
            self.combo_model.setCurrentIndex(index_mod)

        # VRAM Offload Policy
        lbl_vram = QLabel(
            "<b>Gerenciamento de VRAM / Memória da GPU:</b>", self
        )
        self.combo_vram = QComboBox(self)
        self.combo_vram.addItem(
            "Manter sempre na VRAM (Instantâneo - Recomendado)", "never"
        )
        self.combo_vram.addItem(
            "Descarregar VRAM após 5 segundos de inatividade", "5s"
        )
        self.combo_vram.addItem(
            "Descarregar VRAM após 15 segundos de inatividade", "15s"
        )
        self.combo_vram.addItem(
            "Descarregar VRAM após 30 segundos de inatividade", "30s"
        )
        self.combo_vram.addItem(
            "Apenas durante a gravação (Liberar VRAM imediatamente)",
            "immediate"
        )

        current_vram = self.db.get_setting("vram_offload_policy", "never")
        index_vram = self.combo_vram.findData(current_vram)
        if index_vram >= 0:
            self.combo_vram.setCurrentIndex(index_vram)

        # Position Preset
        lbl_position = QLabel(
            "<b>Posição Inicial da Pílula Flutuante:</b>", self
        )
        self.combo_position = QComboBox(self)
        self.combo_position.addItem(
            "Parte Inferior (Baixo da tela - Padrão)", "bottom"
        )
        self.combo_position.addItem("Parte Superior (Topo da tela)", "top")
        self.combo_position.addItem(
            "Lembrar Última Posição Onde Foi Arrastada", "saved"
        )

        current_pos = self.db.get_setting("pill_position", "bottom")
        index_pos = self.combo_position.findData(current_pos)
        if index_pos >= 0:
            self.combo_position.setCurrentIndex(index_pos)

        # Clipboard Auto-copy
        clip_layout = QHBoxLayout()
        self.chk_clipboard = QCheckBox(self)
        is_clip = self.db.get_setting(
            "copy_to_clipboard", "true").lower() == "true"
        self.chk_clipboard.setChecked(is_clip)

        lbl_clip = QLabel(
            "Copiar automaticamente para a Área de Transferência "
            "após transcrever",
            self
        )
        lbl_clip.setWordWrap(True)
        lbl_clip.setStyleSheet("color: #F8FAFC; font-size: 13px;")
        lbl_clip.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl_clip.mousePressEvent = lambda _: self.chk_clipboard.toggle()

        clip_layout.addWidget(self.chk_clipboard)
        clip_layout.addWidget(lbl_clip, 1)

        # Save Button
        btn_save_settings = QPushButton("Salvar Configurações", self)
        btn_save_settings.setObjectName("PrimaryButton")
        btn_save_settings.clicked.connect(self._save_settings)

        settings_layout.addWidget(lbl_language)
        settings_layout.addWidget(self.combo_language)
        settings_layout.addWidget(lbl_mode)
        settings_layout.addWidget(self.combo_mode)
        settings_layout.addWidget(lbl_device)
        settings_layout.addWidget(self.combo_device)
        settings_layout.addWidget(lbl_model)
        settings_layout.addWidget(self.combo_model)
        settings_layout.addWidget(lbl_vram)
        settings_layout.addWidget(self.combo_vram)
        settings_layout.addWidget(lbl_position)
        settings_layout.addWidget(self.combo_position)
        settings_layout.addLayout(clip_layout)
        settings_layout.addWidget(btn_save_settings)
        settings_layout.addStretch()

        settings_scroll.setWidget(settings_tab)

        tabs.addTab(history_tab, "📋 Histórico")
        tabs.addTab(settings_scroll, "⚙️ Configurações")

        main_layout.addWidget(tabs)

    def refresh_history(self):
        # Clear previous card widgets
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self.search_input.text().strip()
        items = self.db.get_transcriptions(
            search_query=query if query else None)

        if not items:
            lbl = QLabel(
                "Nenhuma transcrição encontrada ainda.\n"
                "Pressione Ctrl+Espaço para gravar seu áudio!",
                self.scroll_content
            )
            lbl.setStyleSheet(
                "color: #64748B; font-size: 13px; padding: 40px; "
                "text-align: center;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(lbl)
            return

        for item in items:
            card_widget = self._create_history_item_widget(item)
            self.scroll_layout.addWidget(card_widget)

        self.scroll_layout.addStretch()

    def _create_history_item_widget(self, item: dict) -> QWidget:
        widget = QWidget()
        widget.setObjectName("HistoryCard")
        widget.setStyleSheet("""
            QWidget#HistoryCard {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        # Header (date, language, and duration)
        header_layout = QHBoxLayout()
        date_str = item.get("created_at", "")
        lang = (item.get("language") or "pt").upper()
        duration = item.get("duration_seconds") or 0.0

        lbl_info = QLabel(
            f"<b>[{lang}]</b> {date_str} ({duration:.1f}s)", widget)
        lbl_info.setStyleSheet("color: #94A3B8; font-size: 11px;")

        btn_copy = QPushButton("📋 Copiar", widget)
        btn_copy.setFixedWidth(90)
        btn_copy.clicked.connect(
            lambda _, text=item["text"]: TextInjector.copy_to_clipboard(text)
        )

        btn_delete = QPushButton("🗑️ Excluir", widget)
        btn_delete.setObjectName("DangerButton")
        btn_delete.setFixedWidth(90)
        btn_delete.clicked.connect(
            lambda _, item_id=item["id"]: self._delete_item(item_id)
        )

        header_layout.addWidget(lbl_info)
        header_layout.addStretch()
        header_layout.addWidget(btn_copy)
        header_layout.addWidget(btn_delete)

        # Content Text
        lbl_text = QLabel(item.get("text", ""), widget)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet(
            "color: #F8FAFC; font-size: 13px; font-weight: 500; "
            "line-height: 1.4;"
        )

        layout.addLayout(header_layout)
        layout.addWidget(lbl_text)

        return widget

    def _delete_item(self, item_id: int):
        if self.db.delete_transcription(item_id):
            self.refresh_history()

    def _clear_all_history(self):
        reply = QMessageBox.question(
            self,
            "Limpar Histórico",
            "Tem certeza que deseja excluir todo o histórico de transcrições?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_history()
            self.refresh_history()

    def _save_settings(self):
        language = self.combo_language.currentData()
        mode = self.combo_mode.currentData()
        device = self.combo_device.currentData()
        model = self.combo_model.currentData()
        vram_policy = self.combo_vram.currentData()
        position = self.combo_position.currentData()
        clipboard = "true" if self.chk_clipboard.isChecked() else "false"

        self.db.set_setting("language", language)
        self.db.set_setting("hotkey_mode", mode)
        self.db.set_setting("device", device)
        self.db.set_setting("model_size", model)
        self.db.set_setting("vram_offload_policy", vram_policy)
        self.db.set_setting("pill_position", position)
        self.db.set_setting("copy_to_clipboard", clipboard)

        QMessageBox.information(
            self, "Sucesso", "Configurações salvas com sucesso!")
        self.settings_changed.emit()
