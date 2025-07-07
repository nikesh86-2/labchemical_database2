import os
import json
import hashlib
from PyQt5.QtWidgets import QDialog, QLineEdit, QLabel, QPushButton, QVBoxLayout, QMessageBox

PASSWORD_FILE = "login_credentials.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_credentials():
    if not os.path.exists(PASSWORD_FILE):
        return {"username": "admin", "password": hash_password("chem123")}
    with open(PASSWORD_FILE, "r") as f:
        return json.load(f)

def save_credentials(username, password_hash):
    with open(PASSWORD_FILE, "w") as f:
        json.dump({"username": username, "password": password_hash}, f)

class LoginDialog(QDialog):
    def __init__(self, allow_password_change=False):
        super().__init__()
        self.setWindowTitle("Admin Login")
        self.authenticated = False
        self.allow_password_change = allow_password_change
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self.check_credentials)

        self.status_label = QLabel("")

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(login_button)

        if self.allow_password_change:
            change_button = QPushButton("Change Password")
            change_button.clicked.connect(self.change_password)
            layout.addWidget(change_button)

        layout.addWidget(self.status_label)
        self.setLayout(layout)

    def check_credentials(self):
        creds = load_credentials()
        if self.username_input.text() == creds["username"] and \
           hash_password(self.password_input.text()) == creds["password"]:
            self.authenticated = True
            self.accept()
        else:
            self.status_label.setText("Invalid credentials.")

    def change_password(self):
        creds = load_credentials()
        current = self.password_input.text()
        if hash_password(current) != creds["password"]:
            QMessageBox.warning(self, "Error", "Current password is incorrect.")
            return

        new_password, ok = QInputDialog.getText(self, "Change Password", "Enter new password:")
        if ok and new_password:
            save_credentials(creds["username"], hash_password(new_password))
            QMessageBox.information(self, "Success", "Password changed.")
