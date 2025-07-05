import sys
import os
import re
import sqlite3
import requests
import cv2
import easyocr
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QFileDialog, QInputDialog, QDialog, QLabel, QLineEdit, QFormLayout, QDialogButtonBox
)

DB_FILE = "chemical_inventory.db"

# === EasyOCR Reader ===
reader = easyocr.Reader(['en'], gpu=True)  # Set gpu=True if you have GPU

# --- OCR & CAS extraction functions ---

def preprocess_grayscale_contrast(image_path, alpha=2.0, beta=10):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    return adjusted

def extract_cas_number(text):
    text = text.replace('.', '-').replace(' ', '').upper()
    pattern = re.compile(r'(?:CAS[:\s#]*)?(\d{2,7}-\d{2}-\d)', re.IGNORECASE)
    cas_candidates = pattern.findall(text)
    for cas_number in cas_candidates:
        if validate_cas_checksum(cas_number):
            return cas_number
    return None

def validate_cas_checksum(cas):
    digits = cas.replace('-', '')
    if len(digits) < 3:
        return False
    try:
        check_digit = int(digits[-1])
    except ValueError:
        return False
    total = 0
    for i, d in enumerate(digits[-2::-1], start=1):
        try:
            total += i * int(d)
        except ValueError:
            return False
    return (total % 10) == check_digit

def extract_cas_number_from_image(image_path):
    alpha_values = [1.5, 2.0, 2.5]
    beta_values = [0, 10, 20]

    for alpha in alpha_values:
        for beta in beta_values:
            img = preprocess_grayscale_contrast(image_path, alpha=alpha, beta=beta)
            texts = reader.readtext(img, detail=0, paragraph=True)
            text = "\n".join(texts)
            cas = extract_cas_number(text)
            if cas:
                return cas
    return None

# --- PubChem fetch ---

def fetch_pubchem_data(cas=None, name=None):
    query = cas or name
    if not query:
        return {}

    fields = "IUPACName,MolecularFormula,InChIKey"
    if cas:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/xref/RN/{cas}/property/{fields}/JSON"
    else:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/{fields}/JSON"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        props = res.json()['PropertyTable']['Properties'][0]
        return {
            "common_name": name or cas,  # fallback to input name or cas
            "iupac_name": props.get("IUPACName"),
            "formula": props.get("MolecularFormula"),
            "inchikey": props.get("InChIKey"),
        }
    except Exception as e:
        print(f"PubChem lookup failed for {query}: {e}")
        return {}

# === Dialog for manual confirmation/edit ===

class ChemicalEntryDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Chemical Info")
        self.data = data

        layout = QFormLayout(self)

        self.common_name_edit = QLineEdit(data.get("common_name", ""))
        self.iupac_name_edit = QLineEdit(data.get("iupac_name", ""))
        self.cas_edit = QLineEdit(data.get("cas_number", ""))
        self.formula_edit = QLineEdit(data.get("formula", ""))
        self.inchikey_edit = QLineEdit(data.get("inchikey", ""))
        self.location_edit = QLineEdit()
        self.quantity_edit = QLineEdit("1")

        layout.addRow("Common Name:", self.common_name_edit)
        layout.addRow("IUPAC Name:", self.iupac_name_edit)
        layout.addRow("CAS Number:", self.cas_edit)
        layout.addRow("Formula:", self.formula_edit)
        layout.addRow("InChIKey:", self.inchikey_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow("Quantity:", self.quantity_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def get_data(self):
        return {
            "common_name": self.common_name_edit.text().strip(),
            "iupac_name": self.iupac_name_edit.text().strip(),
            "cas_number": self.cas_edit.text().strip(),
            "formula": self.formula_edit.text().strip(),
            "inchikey": self.inchikey_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "quantity": int(self.quantity_edit.text().strip() or 1)
        }

# === Main app ===

class InventoryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Inventory")
        self.setGeometry(100, 100, 900, 600)
        self.conn = sqlite3.connect(DB_FILE)
        self.create_table()

        self.table = QTableWidget()
        self.load_data()

        self.add_btn = QPushButton("Add Chemical from Image")
        self.add_btn.clicked.connect(self.add_chemical_from_image)

        self.update_btn = QPushButton("Update Quantity")
        self.update_btn.clicked.connect(self.update_quantity)

        self.delete_btn = QPushButton("Delete Chemical")
        self.delete_btn.clicked.connect(self.delete_chemical)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.add_btn)
        layout.addWidget(self.update_btn)
        layout.addWidget(self.delete_btn)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chemicals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                common_name TEXT NOT NULL,
                iupac_name TEXT,
                cas_number TEXT UNIQUE,
                formula TEXT,
                inchikey TEXT,
                location TEXT,
                quantity INTEGER DEFAULT 1
            )
        ''')
        self.conn.commit()

    def load_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, common_name, cas_number, quantity, location FROM chemicals")
        rows = cursor.fetchall()

        self.table.setRowCount(len(rows))
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Common Name", "CAS Number", "Quantity", "Location"])
        for row_idx, row_data in enumerate(rows):
            for col_idx, col_data in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

    def add_chemical_from_image(self):
        image_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg)")
        if not image_path:
            return

        cas = extract_cas_number_from_image(image_path)
        print(f"Extracted CAS: {cas}")

        fallback_name = os.path.splitext(os.path.basename(image_path))[0]

        if cas:
            info = fetch_pubchem_data(cas=cas)
            info["cas_number"] = cas
            info["common_name"] = info.get("common_name") or fallback_name
        else:
            # Try to fetch by fallback name if no CAS found
            info = fetch_pubchem_data(name=fallback_name)
            info["cas_number"] = None
            info["common_name"] = info.get("common_name") or fallback_name

        dlg = ChemicalEntryDialog(info, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.save_chemical(data)
            self.load_data()

    def save_chemical(self, info):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO chemicals
                (common_name, iupac_name, cas_number, formula, inchikey, location, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                info.get("common_name"),
                info.get("iupac_name"),
                info.get("cas_number"),
                info.get("formula"),
                info.get("inchikey"),
                info.get("location"),
                info.get("quantity", 1)
            ))
            self.conn.commit()
            QMessageBox.information(self, "Success", "Chemical added to inventory.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Duplicate", "Chemical with this CAS number already exists.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save chemical: {e}")

    def update_quantity(self):
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Error", "Select a chemical row to update.")
            return
        chem_id = int(self.table.item(selected, 0).text())

        qty, ok = QInputDialog.getInt(self, "Update Quantity", "New Quantity:", min=0)
        if not ok:
            return

        cursor = self.conn.cursor()
        cursor.execute("UPDATE chemicals SET quantity = ? WHERE id = ?", (qty, chem_id))
        self.conn.commit()

        if qty == 0:
            QMessageBox.information(self, "Alert", "Quantity is zero! Please reorder.")
        self.load_data()

    def delete_chemical(self):
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Error", "Select a chemical row to delete.")
            return
        chem_id = int(self.table.item(selected, 0).text())

        confirm = QMessageBox.question(self, "Confirm Delete", "Are you sure?")
        if confirm == QMessageBox.Yes:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM chemicals WHERE id = ?", (chem_id,))
            self.conn.commit()
            self.load_data()

def main():
    app = QApplication(sys.argv)
    window = InventoryApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
