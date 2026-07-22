DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: 'Segoe UI', 'Inter', Roboto, sans-serif;
}

QWidget#FloatingPill {
    background-color: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 20px;
}

QLabel {
    color: #F8FAFC;
    font-size: 13px;
}

QLabel#StatusText {
    font-weight: 600;
    color: #38BDF8;
}

QPushButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 500;
}


QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0F172A;
}

QPushButton#PrimaryButton {
    background-color: #0284C7;
    border: none;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #0369A1;
}

QPushButton#DangerButton {
    background-color: #991B1B;
    border: none;
}

QPushButton#DangerButton:hover {
    background-color: #7F1D1D;
}

QLineEdit {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #38BDF8;
}

QListWidget {
    background-color: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 6px;
    color: #F8FAFC;
}

QListWidget::item {
    background-color: #1E293B;
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 6px;
}

QListWidget::item:hover {
    background-color: #334155;
}

QComboBox {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
}

QTabWidget::pane {
    border: 1px solid #1E293B;
    border-radius: 8px;
    background-color: #0F172A;
}

QTabBar::tab {
    background-color: #1E293B;
    color: #94A3B8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #0284C7;
    color: #FFFFFF;
    font-weight: 600;
}
"""
