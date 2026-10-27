"""Light and dark QSS themes plus color tokens."""
from __future__ import annotations

LIGHT = {
    "bg": "#F5F5F7",
    "card": "#FFFFFF",
    "card_alt": "#F5F5F7",
    "border": "#E5E5EA",
    "text": "#1C1C1E",
    "muted": "#8E8E93",
    "accent": "#0A84FF",
    "accent_pressed": "#0066CC",
    "success": "#30D158",
    "warning": "#FF9F0A",
    "danger": "#FF3B30",
    "sidebar_bg": "#EDEDF0",
    "sidebar_item": "#2C2C2E",
    "sidebar_selected": "#0A84FF",
    "sidebar_selected_text": "#FFFFFF",
    "hover": "#F0F0F3",
    "input_bg": "#FFFFFF",
    "input_border": "#D1D1D6",
}

DARK = {
    "bg": "#111113",
    "card": "#1C1C1E",
    "card_alt": "#2C2C2E",
    "border": "#2C2C2E",
    "text": "#F5F5F7",
    "muted": "#98989D",
    "accent": "#0A84FF",
    "accent_pressed": "#409CFF",
    "success": "#30D158",
    "warning": "#FF9F0A",
    "danger": "#FF453A",
    "sidebar_bg": "#0A0A0B",
    "sidebar_item": "#F5F5F7",
    "sidebar_selected": "#0A84FF",
    "sidebar_selected_text": "#FFFFFF",
    "hover": "#2C2C2E",
    "input_bg": "#1C1C1E",
    "input_border": "#3A3A3C",
}


def build_stylesheet(theme: dict) -> str:
    return f"""
    QWidget {{
        background-color: {theme['bg']};
        color: {theme['text']};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "SF Pro Display",
                     "Helvetica Neue", Arial, sans-serif;
        font-size: 14px;
    }}
    QFrame[card="true"] {{
        background-color: {theme['card']};
        border: 1px solid {theme['border']};
        border-radius: 14px;
    }}
    QFrame[card="alt"] {{
        background-color: {theme['card_alt']};
        border-radius: 12px;
    }}
    QLabel[title="true"] {{
        font-size: 28px;
        font-weight: 700;
        color: {theme['text']};
    }}
    QLabel[subtitle="true"] {{
        font-size: 15px;
        color: {theme['muted']};
    }}
    QLabel[section="true"] {{
        font-size: 13px;
        font-weight: 600;
        color: {theme['muted']};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    QLabel[bigNumber="true"] {{
        font-size: 34px;
        font-weight: 700;
        color: {theme['text']};
    }}
    QLabel[cardTitle="true"] {{
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel[plateBig="true"] {{
        font-size: 44px;
        font-weight: 700;
        letter-spacing: 2px;
    }}
    QLabel[muted="true"] {{
        color: {theme['muted']};
    }}
    QLabel[success="true"] {{
        color: {theme['success']};
    }}
    QLabel[danger="true"] {{
        color: {theme['danger']};
    }}
    QPushButton {{
        background-color: {theme['accent']};
        color: white;
        border: none;
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {theme['accent_pressed']};
    }}
    QPushButton:disabled {{
        background-color: {theme['border']};
        color: {theme['muted']};
    }}
    QPushButton[secondary="true"] {{
        background-color: {theme['card']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
    }}
    QPushButton[secondary="true"]:hover {{
        background-color: {theme['hover']};
    }}
    QPushButton[ghost="true"] {{
        background-color: transparent;
        color: {theme['accent']};
        padding: 6px 12px;
    }}
    QPushButton[ghost="true"]:hover {{
        background-color: {theme['hover']};
    }}
    QPushButton[danger="true"] {{
        background-color: {theme['danger']};
    }}
    #Sidebar {{
        background-color: {theme['sidebar_bg']};
        border: none;
    }}
    #Sidebar QLabel#brand {{
        font-size: 20px;
        font-weight: 700;
        color: {theme['text']};
        padding-left: 4px;
    }}
    #Sidebar QLabel#subtitle {{
        font-size: 12px;
        color: {theme['muted']};
        padding-left: 4px;
        letter-spacing: 0.5px;
    }}
    #Sidebar QPushButton {{
        background-color: transparent;
        color: {theme['sidebar_item']};
        text-align: left;
        padding: 10px 14px;
        border-radius: 10px;
        font-weight: 500;
    }}
    #Sidebar QPushButton:hover {{
        background-color: {theme['hover']};
    }}
    #Sidebar QPushButton:checked {{
        background-color: {theme['sidebar_selected']};
        color: {theme['sidebar_selected_text']};
        font-weight: 600;
    }}
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {theme['input_bg']};
        border: 1px solid {theme['input_border']};
        border-radius: 8px;
        padding: 8px 10px;
        selection-background-color: {theme['accent']};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {theme['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {theme['card']};
        border: 1px solid {theme['border']};
        selection-background-color: {theme['accent']};
        selection-color: white;
        outline: 0;
    }}
    QProgressBar {{
        background-color: {theme['card_alt']};
        border: none;
        border-radius: 6px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {theme['accent']};
        border-radius: 6px;
    }}
    QListWidget {{
        background-color: transparent;
        border: none;
        outline: 0;
        padding: 4px;
    }}
    QListWidget::item {{
        background-color: {theme['card']};
        border: 1px solid {theme['border']};
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 8px;
    }}
    QListWidget::item:hover {{
        background-color: {theme['hover']};
    }}
    QListWidget::item:selected {{
        border-color: {theme['accent']};
    }}
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px 2px 2px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {theme['border']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: {theme['border']};
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QToolTip {{
        background-color: {theme['card']};
        color: {theme['text']};
        border: 1px solid {theme['border']};
        padding: 6px 8px;
        border-radius: 6px;
    }}
    #Toast {{
        background-color: {theme['text']};
        color: {theme['bg']};
        border-radius: 12px;
        padding: 10px 18px;
        font-weight: 500;
    }}
    """
