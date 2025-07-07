from PyQt5.QtGui import QFont

#====STYLE SHEET====#

# JetBrains Mono font setup
jetbrains_font = QFont("JetBrainsMono Nerd Font Mono", 8)
if jetbrains_font.family() != "JetBrainsMono Nerd Font Mono":
    jetbrains_font = QFont("Monospace", 8)

# Dark theme stylesheet
dark_stylesheet = """
QWidget {
    background-color: #2b2b2b;
    color: #a9b7c6;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11pt;
}
QPushButton {
    background-color: #3c3f41;
    color: #a9b7c6;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #4b6eaf;
}
QPushButton:pressed {
    background-color: #2f578b;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #313335;
    border: 1px solid #555555;
    color: #a9b7c6;
    selection-background-color: #214283;
}
QTableWidget {
    background-color: #313335;
    gridline-color: #555555;
    color: #a9b7c6;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11pt;
}
QHeaderView::section {
    background-color: #3c3f41;
    color: #a9b7c6;
    padding: 4px;
    border: 1px solid #555555;
}
QTableWidget::item:selected {
    background-color: #214283;
    color: #ffffff;
}
QDialog {
    background-color: #2b2b2b;
    color: #a9b7c6;
    font-family: 'JetBrains Mono', monospace;
}
QLabel {
    color: #a9b7c6;
}
QMenuBar {
    background-color: #313335;
    color: #a9b7c6;
}
QMenuBar::item:selected {
    background-color: #214283;
}
QMenu {
    background-color: #313335;
    color: #a9b7c6;
}
QMenu::item:selected {
    background-color: #214283;
}
QScrollBar:vertical {
    background: #313335;
    width: 12px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background: #4b6eaf;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
#==================================#
