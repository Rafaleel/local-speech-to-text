from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Error as DatabaseError
import sounddevice as sd
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QPixmap, QPainter, QColor, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QStackedWidget,
    QPushButton, QLabel, QTabBar, QWidget, QGridLayout,
    QButtonGroup, QComboBox, QCheckBox, QMessageBox, QMenu, QFileDialog, QInputDialog
)
from src.ui import themes
from src.ui.floating_widget import create_icon
from src.db.database import DatabaseManager
from src.utils.injector import TextInjector


class HistoryWindow(QDialog):
    settings_changed = Signal()
    theme_changed = Signal(str)
    PAGE_SIZE = 30

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._deleted_item = None
        self.setWindowTitle("Voice to Text")
        self.setMinimumSize(560, 480)
        self.resize(800, 640)

        self._init_ui()
        self.refresh_history()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget(self)
        header.setObjectName("WorkspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 13, 24, 13)
        header_layout.setSpacing(8)
        self.brand_icon = QLabel(header)
        self.brand_icon.setPixmap(create_icon("mic", themes.active()["accent"]).pixmap(20, 20))
        header_layout.addWidget(self.brand_icon)
        brand = QLabel("Voice to Text", header)
        brand.setObjectName("Brand")
        header_layout.addWidget(brand)
        header_layout.addStretch(1)
        self.tabs = QTabBar(header)
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.addTab("Histórico")
        self.tabs.addTab("Configurações")
        self.tabs.addTab("Temas")
        header_layout.addWidget(self.tabs)
        header_layout.addStretch(1)
        shortcut = QLabel("Ctrl + Espaço", header)
        shortcut.setObjectName("Shortcut")
        shortcut.setAccessibleName("Atalho de gravação: Ctrl mais Espaço")
        header_layout.addWidget(shortcut)
        main_layout.addWidget(header)

        self.pages = QStackedWidget(self)
        self.pages.setObjectName("MainArea")
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)
        main_layout.addWidget(self.pages, 1)

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(24, 22, 24, 18)
        history_layout.setSpacing(12)

        search_layout = QHBoxLayout()
        title = QLabel("Histórico", history_tab)
        title.setObjectName("PageTitle")
        search_layout.addWidget(title)
        search_layout.addStretch(1)
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText(
            "Buscar transcrições…"
        )
        self.search_input.setAccessibleName("Buscar transcrições")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh_history)
        self.search_input.setMinimumWidth(160)
        self.search_input.setMaximumWidth(300)
        search_layout.addWidget(self.search_input, 1)

        btn_options = QPushButton("Opções", self)
        btn_options.setAccessibleName("Opções do histórico")
        history_menu = QMenu(btn_options)
        history_menu.addAction("Limpar histórico…", self._clear_all_history)
        btn_options.setMenu(history_menu)
        search_layout.addWidget(btn_options)

        history_layout.addLayout(search_layout)

        feedback = QHBoxLayout()
        self.feedback_label = QLabel("")
        self.undo_button = QPushButton("Desfazer exclusão")
        self.undo_button.clicked.connect(self._undo_delete)
        self.undo_button.hide()
        self.feedback_label.setObjectName("SecondaryText")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.hide()
        feedback.addWidget(self.feedback_label, 1)
        feedback.addWidget(self.undo_button)
        history_layout.addLayout(feedback)

        # Scroll Area for history cards
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("PageContent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)

        self.scroll_area.setWidget(self.scroll_content)
        history_layout.addWidget(self.scroll_area)
        self.load_more_button = QPushButton("Carregar mais transcrições", self)
        self.load_more_button.clicked.connect(self._load_history_page)
        history_layout.addWidget(self.load_more_button)

        settings_page = QWidget(self)
        settings_page_layout = QVBoxLayout(settings_page)
        settings_page_layout.setContentsMargins(24, 22, 24, 18)
        settings_page_layout.setSpacing(12)
        title = QLabel("Configurações", settings_page)
        title.setObjectName("PageTitle")
        settings_page_layout.addWidget(title)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setStyleSheet(
            "QScrollArea { border: none; background-color: transparent; }"
        )

        settings_tab = QWidget()
        settings_tab.setObjectName("PageContent")
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(0, 0, 8, 0)
        settings_layout.setSpacing(12)

        # Language Selection
        lbl_language = QLabel("Idioma", self)
        self.combo_language = QComboBox(self)
        self.combo_language.addItem(
            "Automático", "auto")
        self.combo_language.addItem("Português", "pt")
        self.combo_language.addItem("Inglês (EN)", "en")
        self.combo_language.addItem("Espanhol (ES)", "es")

        current_language = self.db.get_setting("language", "auto")
        index_lang = self.combo_language.findData(current_language)
        if index_lang >= 0:
            self.combo_language.setCurrentIndex(index_lang)

        # Hotkey Mode
        lbl_mode = QLabel("Atalho de gravação", self)
        self.combo_mode = QComboBox(self)
        self.combo_mode.addItem(
            "Alternar início e fim",
            "toggle"
        )
        self.combo_mode.addItem("Segurar para falar", "hold")

        current_mode = self.db.get_setting("hotkey_mode", "toggle")
        index = self.combo_mode.findData(current_mode)
        if index >= 0:
            self.combo_mode.setCurrentIndex(index)

        # Device
        lbl_device = QLabel(
            "Dispositivo de processamento", self
        )
        self.combo_device = QComboBox(self)
        self.combo_device.addItem(
            "GPU NVIDIA (CUDA)", "cuda"
        )
        self.combo_device.addItem("CPU (Processador)", "cpu")

        current_device = self.db.get_setting("device", "cuda")
        index_dev = self.combo_device.findData(current_device)
        if index_dev >= 0:
            self.combo_device.setCurrentIndex(index_dev)

        # Model Size
        lbl_model = QLabel("Modelo Whisper", self)
        self.combo_model = QComboBox(self)
        self.combo_model.addItem(
            "large-v3-turbo",
            "large-v3-turbo"
        )
        self.combo_model.addItem(
            "large-v3", "large-v3"
        )
        self.combo_model.addItem("small (Rápido e leve)", "small")
        self.combo_model.addItem("base (Ultra leve)", "base")

        current_model = self.db.get_setting("model_size", "large-v3-turbo")
        if current_model == "openai/whisper-large-v3":
            current_model = "large-v3"
        index_mod = self.combo_model.findData(current_model)
        if index_mod >= 0:
            self.combo_model.setCurrentIndex(index_mod)

        # VRAM Offload Policy
        lbl_vram = QLabel("Uso de memória", self)
        self.combo_vram = QComboBox(self)
        self.combo_vram.addItem(
            "Manter na memória", "never"
        )
        self.combo_vram.addItem(
            "Liberar após 5 s sem uso", "5s"
        )
        self.combo_vram.addItem(
            "Liberar após 15 s sem uso", "15s"
        )
        self.combo_vram.addItem(
            "Liberar após 30 s sem uso", "30s"
        )
        self.combo_vram.addItem(
            "Liberar após transcrever",
            "immediate"
        )

        current_vram = self.db.get_setting("vram_offload_policy", "never")
        index_vram = self.combo_vram.findData(current_vram)
        if index_vram >= 0:
            self.combo_vram.setCurrentIndex(index_vram)

        # Position Preset
        lbl_position = QLabel("Posição da pílula", self)
        self.combo_position = QComboBox(self)
        self.combo_position.addItem(
            "Parte inferior", "bottom"
        )
        self.combo_position.addItem("Parte superior", "top")
        self.combo_position.addItem(
            "Última posição arrastada", "saved"
        )

        current_pos = self.db.get_setting("pill_position", "bottom")
        index_pos = self.combo_position.findData(current_pos)
        if index_pos >= 0:
            self.combo_position.setCurrentIndex(index_pos)

        self.chk_clipboard = QCheckBox("Copiar automaticamente", self)
        self.chk_clipboard.setChecked(
            self.db.get_setting("copy_to_clipboard", "true").lower() == "true"
        )
        self.chk_sounds = QCheckBox("Tocar sons de gravação", self)
        self.chk_sounds.setChecked(
            self.db.get_setting("sound_effects", "true").lower() == "true"
        )

        # Save Button
        btn_save_settings = QPushButton("Salvar alterações", self)
        btn_save_settings.setObjectName("PrimaryButton")
        btn_save_settings.clicked.connect(self._save_settings)

        def group(title, fields, description=""):
            section = QWidget(settings_tab)
            section.setObjectName("SettingsSection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(16, 13, 16, 14)
            section_layout.setSpacing(9)
            heading = QLabel(title, section)
            heading.setObjectName("SectionTitle")
            section_layout.addWidget(heading)
            if description:
                help_label = QLabel(description, section)
                help_label.setWordWrap(True)
                help_label.setObjectName("SecondaryText")
                section_layout.addWidget(help_label)
            form = QGridLayout()
            form.setHorizontalSpacing(20)
            form.setVerticalSpacing(7)
            form.setColumnMinimumWidth(0, 142)
            form.setColumnStretch(1, 1)
            for row, (label, field) in enumerate(fields):
                label.setBuddy(field)
                label.setWordWrap(True)
                field.setAccessibleName(label.text())
                if isinstance(field, QComboBox):
                    field.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                    field.setMinimumContentsLength(10)
                form.addWidget(label, row, 0)
                form.addWidget(field, row, 1)
            section_layout.addLayout(form)
            settings_layout.addWidget(section)
            return section_layout

        self.combo_microphone = QComboBox(self)
        self.combo_microphone.addItem("Padrão do sistema", "")
        saved_microphone = self.db.get_setting("microphone", "")
        try:
            devices = sd.query_devices()
        except sd.PortAudioError:
            devices = []
        for device in devices:
            name = device["name"]
            if device["max_input_channels"] > 0 and self.combo_microphone.findData(name) < 0:
                self.combo_microphone.addItem(name, name)
        if saved_microphone and self.combo_microphone.findData(saved_microphone) < 0:
            self.combo_microphone.addItem(f"{saved_microphone} (indisponível)", saved_microphone)
        self.combo_microphone.setCurrentIndex(self.combo_microphone.findData(saved_microphone))
        microphone_label = QLabel("Microfone", self)
        test_microphone = QPushButton("Verificar microfone", self)
        test_microphone.clicked.connect(self._check_microphone)
        self.microphone_feedback = QLabel("", self)
        self.microphone_feedback.setWordWrap(True)

        self.hotwords_input = QLineEdit(self.db.get_setting("hotwords", ""), self)
        self.hotwords_input.setMaxLength(300)
        self.hotwords_input.setPlaceholderText("Nomes, siglas e termos técnicos")
        hotwords_label = QLabel("Vocabulário do ditado", self)
        recording = group("Gravação", [(microphone_label, self.combo_microphone),
                           (lbl_language, self.combo_language), (lbl_mode, self.combo_mode),
                           (hotwords_label, self.hotwords_input)],
              "Esc descarta a gravação.")
        microphone_check = QHBoxLayout()
        microphone_check.addWidget(test_microphone)
        microphone_check.addWidget(self.microphone_feedback, 1)
        self.microphone_feedback.setObjectName("SecondaryText")
        recording.addLayout(microphone_check)
        behavior = group("Pílula e saída", [(lbl_position, self.combo_position)])
        behavior.addWidget(self.chk_clipboard)
        self.chk_review = QCheckBox("Revisar e editar antes de copiar", self)
        self.chk_review.setChecked(self.db.get_setting("review_before_copy", "false") == "true")
        self.chk_history = QCheckBox("Salvar transcrições no histórico local", self)
        self.chk_history.setChecked(self.db.get_setting("save_history", "true") == "true")
        behavior.addWidget(self.chk_review)
        behavior.addWidget(self.chk_history)
        behavior.addWidget(self.chk_sounds)
        self.chk_clipboard.setAccessibleName("Copiar automaticamente após transcrever")
        self.chk_sounds.setAccessibleName("Tocar sons de gravação")
        profile_label = QLabel("Perfil de transcrição", self)
        self.combo_profile = QComboBox(self)
        self.combo_profile.addItem("Personalizado", None)
        self.combo_profile.addItem("Rápido · base em CPU", ("cpu", "base"))
        self.combo_profile.addItem("Equilibrado · turbo em GPU NVIDIA", ("cuda", "large-v3-turbo"))
        self.combo_profile.addItem("Precisão · large-v3 em GPU NVIDIA", ("cuda", "large-v3"))
        self.combo_profile.currentIndexChanged.connect(self._apply_model_profile)
        self.combo_device.currentIndexChanged.connect(self._sync_model_profile)
        self.combo_model.currentIndexChanged.connect(self._sync_model_profile)
        self._sync_model_profile()
        group("Desempenho", [(profile_label, self.combo_profile)])
        group("Avançado", [(lbl_device, self.combo_device), (lbl_model, self.combo_model),
                          (lbl_vram, self.combo_vram)],
              "Manter o modelo carregado reduz a espera entre transcrições.")
        self.save_feedback = QLabel("")
        self.save_feedback.setObjectName("SecondaryText")
        settings_layout.addStretch()

        settings_scroll.setWidget(settings_tab)

        settings_page_layout.addWidget(settings_scroll, 1)
        footer = QHBoxLayout()
        footer.addWidget(self.save_feedback, 1)
        footer.addWidget(btn_save_settings)
        settings_page_layout.addLayout(footer)
        self.pages.addWidget(history_tab)
        self.pages.addWidget(settings_page)
        self.pages.addWidget(self._build_themes_page())
        next_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab.activated.connect(lambda: self.show_page((self.tabs.currentIndex() + 1) % self.tabs.count()))
        find = QShortcut(QKeySequence.StandardKey.Find, self)
        find.activated.connect(self.focus_history_search)

    def _build_themes_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(12)
        title = QLabel("Temas", page)
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        hint = QLabel("O tema muda a pílula, o histórico e as configurações na hora.", page)
        hint.setObjectName("SecondaryText")
        layout.addWidget(hint)
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        content = QWidget()
        content.setObjectName("PageContent")
        grid = QGridLayout(content)
        grid.setSpacing(12)
        self.theme_group = QButtonGroup(self)
        self.theme_buttons = {}
        for index, (key, theme) in enumerate(themes.THEMES.items()):
            card = QPushButton(f"{theme['label']}\n{theme['desc']}", content)
            card.setObjectName("ThemeCard")
            card.setCheckable(True)
            card.setChecked(key == themes.active_key())
            card.setIcon(self._theme_swatch(theme))
            card.setIconSize(QSize(72, 44))
            card.setMinimumHeight(72)
            card.setAccessibleName(f"Tema {theme['label']}")
            card.clicked.connect(lambda _, k=key: self.theme_changed.emit(k))
            self.theme_group.addButton(card)
            self.theme_buttons[key] = card
            grid.addWidget(card, index, 0)
        grid.setRowStretch(grid.rowCount(), 1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    @staticmethod
    def _theme_swatch(theme: dict) -> QIcon:
        pixmap = QPixmap(72, 44)
        pixmap.fill(QColor(theme["bg"]))
        painter = QPainter(pixmap)
        for i, color in enumerate((theme["surface"], theme["accent"], theme["glow"], theme["err"])):
            painter.fillRect(8 + i * 15, 8, 12, 28, QColor(color))
        painter.end()
        return QIcon(pixmap)

    def apply_theme(self):
        """Refresh pixmap icons and cards that were built with the previous theme."""
        self.brand_icon.setPixmap(create_icon("mic", themes.active()["accent"]).pixmap(20, 20))
        for key, card in self.theme_buttons.items():
            card.setChecked(key == themes.active_key())
        self.refresh_history()

    def show_page(self, index: int):
        self.tabs.setCurrentIndex(index)

    def focus_history_search(self):
        self.show_page(0)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def refresh_history(self):
        # Clear previous card widgets
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._history_offset = 0
        self._load_history_page()

    def _load_history_page(self):
        query = self.search_input.text().strip()
        items = self.db.get_transcriptions(
            search_query=query or None,
            limit=self.PAGE_SIZE + 1,
            offset=self._history_offset,
        )
        self.load_more_button.setVisible(len(items) > self.PAGE_SIZE)
        if self._history_offset:
            self.scroll_layout.takeAt(self.scroll_layout.count() - 1)
        items = items[:self.PAGE_SIZE]

        if not items and not self._history_offset:
            lbl = QLabel(
                ("Nenhum resultado para esta busca.\nTente outras palavras." if query else
                 "Seu histórico começa aqui.\nUse Ctrl+Espaço ou o microfone da pílula para gravar."),
                self.scroll_content
            )
            lbl.setObjectName("EmptyState")
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(lbl)
            self.scroll_layout.addStretch()
            return

        for item in items:
            card_widget = self._create_history_item_widget(item)
            self.scroll_layout.addWidget(card_widget)

        self._history_offset += len(items)
        self.scroll_layout.addStretch()

    def _create_history_item_widget(self, item: dict) -> QWidget:
        widget = QWidget()
        widget.setObjectName("HistoryCard")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(14, 14, 12, 14)
        layout.setSpacing(11)

        # Header (date, language, and duration)
        date_str = item.get("created_at", "")
        try:
            date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).astimezone()
            date_str = ("Hoje, " + date.strftime("%H:%M") if date.date() == datetime.now().date()
                        else date.strftime("%d/%m/%Y · %H:%M"))
        except (ValueError, TypeError):
            pass
        lang = (item.get("language") or "pt").upper()
        duration = item.get("duration_seconds") or 0.0

        lbl_info = QLabel(
            f"{date_str}\n{lang} · {duration:.0f} s", widget)
        lbl_info.setObjectName("Metadata")
        lbl_info.setFixedWidth(99)
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info, 0, Qt.AlignmentFlag.AlignTop)

        btn_copy = QPushButton("Copiar", widget)
        btn_copy.setIcon(create_icon("copy", themes.active()["accent"]))
        btn_copy.setObjectName("HistoryAction")
        btn_copy.clicked.connect(
            lambda _, text=item["text"], button=btn_copy: self._copy_text(text, button)
        )

        actions = QPushButton(create_icon("more", themes.active()["muted"]), "", widget)
        actions.setObjectName("HistoryAction")
        actions.setFixedWidth(32)
        actions.setToolTip("Mais ações")
        actions.setAccessibleName("Mais ações da transcrição")
        menu = QMenu(actions)
        menu.addAction("Editar…", lambda: self._edit_item(item))
        menu.addAction("Exportar texto…", lambda: self._export_item(item))
        menu.addSeparator()
        menu.addAction("Excluir", lambda: self._delete_item(item))
        actions.setMenu(menu)

        # Content Text
        lbl_text = QLabel(item.get("text", ""), widget)
        lbl_text.setTextFormat(Qt.TextFormat.PlainText)
        lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        lbl_text.setWordWrap(True)
        lbl_text.setObjectName("Transcript")

        layout.addWidget(lbl_text, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(btn_copy, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(actions, 0, Qt.AlignmentFlag.AlignTop)

        return widget

    def _show_feedback(self, message):
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(bool(message))

    def _copy_text(self, text, button):
        if TextInjector.copy_to_clipboard(text):
            button.setText("Copiado")
            self._show_feedback("Texto copiado para a área de transferência.")
        else:
            self._show_feedback("Não foi possível copiar. Selecione o texto e tente Ctrl+C.")

    def _edit_item(self, item):
        text, accepted = QInputDialog.getMultiLineText(
            self, "Editar transcrição", "Texto", item["text"]
        )
        if not accepted:
            return
        if not text.strip():
            self._show_feedback("Digite algum texto antes de salvar.")
            return
        try:
            updated = self.db.update_transcription(item["id"], text)
        except DatabaseError as error:
            QMessageBox.warning(self, "Falha ao salvar", str(error))
            return
        self._show_feedback(
            "Transcrição atualizada." if updated else "A transcrição não está mais no histórico."
        )
        self.refresh_history()

    def _export_item(self, item):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar transcrição", "transcricao.txt", "Texto (*.txt)"
        )
        if not path:
            return
        try:
            Path(path).write_text(item["text"], encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, "Falha ao exportar", str(error))
        else:
            self._show_feedback("Transcrição exportada.")

    def _delete_item(self, item):
        if self.db.delete_transcription(item["id"]):
            self._deleted_item = item
            self._show_feedback("Transcrição excluída. Você pode desfazer a última exclusão.")
            self.undo_button.show()
            self.refresh_history()

    def _undo_delete(self):
        if self._deleted_item:
            self.db.restore_transcription(self._deleted_item)
            self._deleted_item = None
            self.undo_button.hide()
            self._show_feedback("Transcrição restaurada.")
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
            self._deleted_item = None
            self.undo_button.hide()
            self._show_feedback("Histórico limpo.")
            self.refresh_history()

    def _apply_model_profile(self):
        profile = self.combo_profile.currentData()
        if profile is None:
            return
        device, model = profile
        self.combo_device.setCurrentIndex(self.combo_device.findData(device))
        self.combo_model.setCurrentIndex(self.combo_model.findData(model))

    def _sync_model_profile(self):
        active = (self.combo_device.currentData(), self.combo_model.currentData())
        for index in range(1, self.combo_profile.count()):
            if self.combo_profile.itemData(index) == active:
                break
        else:
            index = 0
        previous = self.combo_profile.blockSignals(True)
        self.combo_profile.setCurrentIndex(index)
        self.combo_profile.blockSignals(previous)

    def _check_microphone(self):
        try:
            with sd.InputStream(
                device=self.combo_microphone.currentData() or None,
                channels=1,
                samplerate=16000,
                dtype="float32",
            ):
                pass
        except (sd.PortAudioError, ValueError) as error:
            self.microphone_feedback.setText(f"Não foi possível abrir o microfone. {error}")
        else:
            self.microphone_feedback.setText("Microfone disponível para gravar.")

    def _save_settings(self):
        language = self.combo_language.currentData()
        mode = self.combo_mode.currentData()
        device = self.combo_device.currentData()
        model = self.combo_model.currentData()
        vram_policy = self.combo_vram.currentData()
        position = self.combo_position.currentData()
        clipboard = "true" if self.chk_clipboard.isChecked() else "false"
        sounds = "true" if self.chk_sounds.isChecked() else "false"

        self.db.set_setting("language", language)
        self.db.set_setting("microphone", self.combo_microphone.currentData() or "")
        self.db.set_setting("hotwords", self.hotwords_input.text().strip())
        self.db.set_setting("hotkey_mode", mode)
        self.db.set_setting("device", device)
        self.db.set_setting("model_size", model)
        self.db.set_setting("vram_offload_policy", vram_policy)
        self.db.set_setting("pill_position", position)
        self.db.set_setting("copy_to_clipboard", clipboard)
        self.db.set_setting("sound_effects", sounds)
        self.db.set_setting("review_before_copy", str(self.chk_review.isChecked()).lower())
        self.db.set_setting("save_history", str(self.chk_history.isChecked()).lower())

        self.save_feedback.setText("Configurações salvas.")
        self.settings_changed.emit()
