import sys
from PyQt5.QtWidgets import QApplication
from styles import jetbrains_font, dark_stylesheet
from database import create_database
from ui_mainwindow import MainWindow
from login_dialog import LoginDialog
from PyQt5.QtWidgets import QDialog
from dblock import DBLock
from config import DB_FILE

if __name__ == "__main__":
    locker = DBLock(DB_FILE)
    readonly = locker.acquire()
    # Use this URI if opening SQLite in read-only mode
    if readonly:
        db_uri = f"file:{DB_FILE}?mode=ro"
    else:
        db_uri = DB_FILE

    create_database(db_uri, readonly=readonly)
    app = QApplication(sys.argv)
    # Show login dialog
    login_dialog = LoginDialog(allow_password_change=True)
    if login_dialog.exec_() != QDialog.Accepted:
        sys.exit()


    app.setFont(jetbrains_font)
    app.setStyleSheet(dark_stylesheet)

    window = MainWindow(db_uri)
    window.show()
    sys.exit(app.exec_())