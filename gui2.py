import sys
import os
import re
import sqlite3
import pubchempy as pcp
import easyocr
import cv2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QDialog, QLabel, QLineEdit,
    QHBoxLayout, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt

# === CONFIG ===
DB_FILE = "chemical_inventory.db"

# === EasyOCR Reader ===
reader = easyocr.Reader(['en'], gpu=True)

# === DATABASE SETUP ===
def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cas_number TEXT,
            formula TEXT,
            common_name TEXT,
            iupac_name TEXT,
            location TEXT,
            quantity INTEGER DEFAULT 1,
            safety_info_url TEXT,
            inchikey TEXT
        )
    ''')
    conn.commit()
    conn.close()

# === IMAGE PROCESSING (simplified) ===
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


# === PubChem Lookup ===


def fetch_pubchem_data(cas=None, name=None, formula=None):
    query = cas or name or formula
    if not query:
        return {}

    try:
        compound = None
        if cas:
            results = pcp.get_compounds(cas, 'name')
        else:
            results = pcp.get_compounds(query, 'name')

        if not results:
            return {}

        compound = results[0]

        synonyms = compound.synonyms or []
        iupac_name = compound.iupac_name or ""
        common_name = next((s for s in synonyms if s.lower() != iupac_name.lower()), synonyms[0] if synonyms else "")

        return {
            "iupac_name": iupac_name,
            "common_name": common_name,
            "formula": compound.molecular_formula,
            "inchikey": compound.inchikey,
            "safety_info_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{compound.cid}"
        }

    except Exception as e:
        print(f"⚠️ pubchempy lookup failed for {query}: {e}")
        return {}

# === SAVE TO DB ===
def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cas = info.get('cas_number')
    name = info.get('name', '').strip().lower()
    formula = info.get('formula', '').strip().lower()

    # Try match by CAS, or fallback match by name+formula if CAS is missing
    if cas:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals WHERE cas_number = ?
        ''', (cas,))
    else:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE cas_number IS NULL AND LOWER(name) = ? AND LOWER(formula) = ?
        ''', (name, formula))

    row = cursor.fetchone()
    if row:
        new_quantity = row[1] + info.get('quantity', 1)
        cursor.execute('''
            UPDATE Chemicals
            SET quantity = ?, location = ?
            WHERE id = ?
        ''', (new_quantity, info.get('location'), row[0]))
    else:
        cursor.execute('''
            INSERT INTO Chemicals (
                name, cas_number, formula, common_name, iupac_name,
                location, quantity, safety_info_url, inchikey
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            info.get("name"),
            info.get("cas_number"),
            info.get("formula"),
            info.get("common_name"),
            info.get("iupac_name"),
            info.get("location"),
            info.get("quantity", 1),
            info.get("safety_info_url"),
            info.get("inchikey")
        ))

    conn.commit()
    conn.close()

# === GUI ===
class ChemicalEntryDialog(QDialog):
    def __init__(self, info=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chemical Entry")
        layout = QVBoxLayout()

        def get_field(info, key):
            val = info.get(key, "")
            # Don't use the field if it's identical to CAS or name
            if val == info.get("cas_number") or val == info.get("name"):
                return ""
            return str(val)

        self.name_edit = QLineEdit(info.get("name", "") if info else "")
        self.cas_edit = QLineEdit(info.get("cas_number", "") if info else "")
        self.formula_edit = QLineEdit(get_field(info, "formula"))
        self.common_name_edit = QLineEdit(get_field(info, "common_name"))
        self.iupac_name_edit = QLineEdit(get_field(info, "iupac_name"))
        self.location_edit = QLineEdit(info.get("location", "") if info else "")
        self.quantity_edit = QLineEdit(str(info.get("quantity", 1)) if info else "1")

        layout.addWidget(QLabel("Name (IUPAC or main name):"))
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("CAS Number:"))
        layout.addWidget(self.cas_edit)
        layout.addWidget(QLabel("Formula:"))
        layout.addWidget(self.formula_edit)
        layout.addWidget(QLabel("Common Name:"))
        layout.addWidget(self.common_name_edit)
        layout.addWidget(QLabel("IUPAC Name:"))
        layout.addWidget(self.iupac_name_edit)
        layout.addWidget(QLabel("Location:"))
        layout.addWidget(self.location_edit)
        layout.addWidget(QLabel("Quantity:"))
        layout.addWidget(self.quantity_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_data(self):
        try:
            quantity = int(self.quantity_edit.text().strip())
        except ValueError:
            quantity = 1

        return {
            "name": self.name_edit.text().strip(),
            "cas_number": self.cas_edit.text().strip(),
            "formula": self.formula_edit.text().strip(),
            "common_name": self.common_name_edit.text().strip(),
            "iupac_name": self.iupac_name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "quantity": quantity,
            "safety_info_url": None,
            "inchikey": None
        }

class InventoryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Inventory")
        self.resize(800, 600)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "CAS Number", "Formula", "Common Name", "IUPAC Name", "Location", "Quantity"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.add_btn = QPushButton("Add Chemical")
        self.delete_btn = QPushButton("Delete Chemical")
        self.update_qty_btn = QPushButton("Update Quantity")
        self.load_btn = QPushButton("Reload Inventory")
        self.drag_label = QLabel("Drag and drop a folder or image files here")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.update_qty_btn)
        btn_layout.addWidget(self.load_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.table)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.drag_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.add_btn.clicked.connect(self.add_chemical_manual)
        self.delete_btn.clicked.connect(self.delete_chemical)
        self.update_qty_btn.clicked.connect(self.update_quantity)
        self.load_btn.clicked.connect(self.load_data)

        self.setAcceptDrops(True)

        self.load_data()

    def load_data(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, cas_number, formula, common_name, iupac_name, location, quantity FROM Chemicals')
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if col_idx == 7:  # Quantity column
                    if int(val) == 0:
                        item.setBackground(Qt.red)
                self.table.setItem(row_idx, col_idx, item)

    def add_chemical_manual(self):
        dlg = ChemicalEntryDialog()
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            save_to_database(data)
            self.load_data()

    def delete_chemical(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Select a chemical to delete.")
            return
        row = selected[0].row()
        chem_id = int(self.table.item(row, 0).text())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Chemicals WHERE id = ?', (chem_id,))
        conn.commit()
        conn.close()
        self.load_data()

    def update_quantity(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Warning", "Select a chemical to update quantity.")
            return
        row = selected[0].row()
        chem_id = int(self.table.item(row, 0).text())
        current_qty = int(self.table.item(row, 6).text())

        qty, ok = QInputDialog.getInt(self, "Update Quantity", "Enter new quantity:", value=current_qty, min=0)
        if ok:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('UPDATE Chemicals SET quantity = ? WHERE id = ?', (qty, chem_id))
            conn.commit()
            conn.close()
            if qty == 0:
                QMessageBox.warning(self, "Alert", "Quantity is zero! Consider restocking.")
            self.load_data()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                local_path = url.toLocalFile()
                if os.path.isdir(local_path) or self.is_image_file(local_path):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            local_path = url.toLocalFile()
            if os.path.isdir(local_path):
                self.process_folder(local_path)
            elif self.is_image_file(local_path):
                self.process_single_image(local_path)

    def is_image_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png']

    def process_folder(self, folder_path):
        location = os.path.basename(folder_path)  # Folder name as location
        for fname in os.listdir(folder_path):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath) and self.is_image_file(fpath):
                self.process_single_image(fpath, location)

    def process_single_image(self, image_path, location="Unknown"):
        cas = extract_cas_number_from_image(image_path)
        fallback_name = os.path.splitext(os.path.basename(image_path))[0]

        chemical_info = {
            "cas_number": cas,
            "location": location,
            "quantity": 1,
            "name": None,
            "common_name": None,
            "iupac_name": None,
            "formula": None,
            "inchikey": None,
            "safety_info_url": None
        }

        enriched = {}
        if cas:
            enriched = fetch_pubchem_data(cas=cas)
        else:
            enriched = fetch_pubchem_data(name=fallback_name)

        if enriched:
            chemical_info["iupac_name"] = enriched.get("iupac_name")
            chemical_info["common_name"] = enriched.get("common_name")
            chemical_info["formula"] = enriched.get("formula")
            chemical_info["inchikey"] = enriched.get("inchikey")
            chemical_info["safety_info_url"] = enriched.get("safety_info_url")

        # Assign name by priority
        chemical_info["name"] = (
                chemical_info.get("common_name")
                or chemical_info.get("iupac_name")
                or fallback_name
        )
        print("⚙️ Final chemical info:", chemical_info)

        dlg = ChemicalEntryDialog(chemical_info, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            save_to_database(data)
            self.load_data()

if __name__ == "__main__":
    create_database()
    app = QApplication(sys.argv)
    window = InventoryApp()
    window.show()
    sys.exit(app.exec())
