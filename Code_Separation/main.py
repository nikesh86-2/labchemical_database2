import sys
from PyQt5.QtWidgets import QApplication
from styles import jetbrains_font, dark_stylesheet
from database import create_database
from ui_mainwindow import MainWindow

if __name__ == "__main__":
    create_database()
    app = QApplication(sys.argv)
    app.setFont(jetbrains_font)
    app.setStyleSheet(dark_stylesheet)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())