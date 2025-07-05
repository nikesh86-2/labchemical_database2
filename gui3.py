import sys
import os
import sqlite3
import webbrowser
import urllib.parse
import re
from PIL import Image, ImageEnhance, ImageFilter
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout,
                             QPushButton, QWidget, QTableWidget, QTableWidgetItem,
                             QHBoxLayout, QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import easyocr
import pubchempy as pcp
import numpy as np

#====STYLE SHEET====#

# JetBrains Mono font setup
jetbrains_font = QFont("JetBrains Mono", 10)
if jetbrains_font.family() != "JetBrains Mono":
    jetbrains_font = QFont("Monospace", 10)

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

#===Environment setup===#
DB_FILE = "chemical_inventory.db" # db file name
reader = easyocr.Reader(['en'], gpu=True) #optical character recognition system

#====DB creation ====#
def create_database():
    """
    Create a SQLite database and a 'chemicals' table if it doesn't already exist.
    Stores the chemical database
    """
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
            manufacturer TEXT,
            catalog_number TEXT,
            product_url TEXT
        )
    ''')
    conn.commit()
    conn.close()
#==============================#

#====EXTRACTION SNIPPET====#
def extract_text_from_image(image_path):
    """
enhance image using alpha and beta (contrast + brightness)
and use that to extract text block
    """
    image = Image.open(image_path)
    best_text = ""
    best_score = 0
    for contrast in [0.8, 1.0, 1.5, 2.0]:
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(contrast)

        # Convert PIL image to numpy array (RGB to BGR for OpenCV if needed)
        img_np = np.array(enhanced_image)
        # EasyOCR expects RGB or grayscale, so no need to convert color order

        text_results = reader.readtext(img_np)
        full_text = " ".join([result[1] for result in text_results])
        if len(full_text) > best_score:
            best_score = len(full_text)
            best_text = full_text
    return best_text

def enrich_with_pubchem(data):
    """
use pubchempy to extract data from available cas number
    """
    cas = data.get("cas_number")
    if not cas:
       return data
    try:
        compounds = pcp.get_compounds(cas, 'name')
        if compounds:
            comp = compounds[0] # take first entry from cas list

            data["iupac_name"] = comp.iupac_name
            data["common_name"] = comp.synonyms[0] if comp.synonyms else None
            data["formula"] = comp.molecular_formula
            data["safety_info_url"] = f"https://pubchem.ncbi.nlm.nih.gov/compound/{comp.cid}"
    except Exception as e:
        print(f"PubChem lookup failed for CAS {cas}: {e}")
    return data

def parse_chemical_info(text):
    data = {
        "name": None,
        "cas_number": None,
        "formula": None,
        "common_name": None,
        "iupac_name": None,
        "manufacturer": None,
        "catalog_number": None
    }

    # Try to extract CAS Number
    cas_match = re.search(r'\b(\d{2,7}-\d{2}-\d)\b', text)
    if cas_match:
        data["cas_number"] = cas_match.group(1)

    # # Try to find formula-like strings (e.g., C6H12O6)
    # formula_match = re.search(r'\b([A-Z][a-z]?[0-9]{0,3})+\b', text)
    # if formula_match:
    #     data["formula"] = formula_match.group(0)
    #
    # # Try to find a chemical name (best guess: longest capitalized word)
    # potential_names = re.findall(r'\b[A-Z][a-zA-Z0-9\-]{2,}\b', text)
    # if potential_names:
    #     data["name"] = max(potential_names, key=len)
    #
    # # Manufacturer
    # manufacturer_match = re.search(r"Manufacturer[:\s]*([\w\s&,-]+)", text, re.IGNORECASE)
    # if manufacturer_match:
    #     data["manufacturer"] = manufacturer_match.group(1).strip()
    #
    # Catalog Number
    catalog_match = re.search(r"Catalog\s*(?:No\.|Number)[:\s]*([\w-]+)", text, re.IGNORECASE)
    if catalog_match:
        data["catalog_number"] = catalog_match.group(1).strip()

    return enrich_with_pubchem(data)

# ========== MAIN APPLICATION WINDOW ==========
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Inventory")
        self.resize(1000, 600)

        # Table for chemical display
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self.handle_cell_change)

        # Buttons
        self.process_folder_btn = QPushButton("Process Image Folder")
        self.process_folder_btn.clicked.connect(self.process_image_folder)

        self.search_button = QPushButton("Search Reagent Online")
        self.search_button.clicked.connect(self.open_google_search_dialog)

        self.add_manual_button = QPushButton("Add Compound Manually")
        self.add_manual_button.clicked.connect(self.add_manual_entry)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)

        self.refresh_button = QPushButton("Refresh Table")
        self.refresh_button.clicked.connect(self.load_data)

        self.use_bottle_button = QPushButton("Use Bottle")
        self.use_bottle_button.clicked.connect(self.use_bottle)


        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.process_folder_btn)
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.add_manual_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.use_bottle_button)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Load data
        self.load_data()

#snippet for reducing quantity.
    def use_bottle(self):

            selected_items = self.table.selectedItems()
            if not selected_items: # error handling for no item selected
                QMessageBox.warning(self, "No Selection", "Please select a chemical to mark as used.")
                return

            row = selected_items[0].row()
            compound_id = int(self.table.item(row, 0).text())
            quantity_item = self.table.item(row, 7)
            current_quantity = int(quantity_item.text())

            if current_quantity <= 0: # error handling for no bottles left already
                QMessageBox.information(self, "Already Empty", "This chemical has no remaining quantity.")
                return

            new_quantity = current_quantity - 1 # reduce by 1

            conn = sqlite3.connect(DB_FILE) # update the database
            cursor = conn.cursor()
            cursor.execute("UPDATE Chemicals SET quantity = ? WHERE id = ?", (new_quantity, compound_id))
            conn.commit()
            conn.close()

            self.load_data()

            if new_quantity == 0:
                QMessageBox.critical(self, "Reorder Alert", "Quantity is now 0. Please reorder this chemical.")
# thinking about adding email facility

    def load_data(self):
#reload data in visible spreadsheet
        self.table.blockSignals(True) # prevent recursive triggers when inline editing
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, cas_number, formula, common_name, iupac_name, location, quantity, manufacturer, catalog_number FROM Chemicals")
        rows = cursor.fetchall()
        conn.close()

        headers = ["ID", "Name", "CAS Number", "Formula", "Common Name", "IUPAC Name", "Location", "Quantity", "Manufacturer", "Catalog Number"]
        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_idx, col_idx, item)
                if col_idx == 0:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # ID is read-only
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.table.blockSignals(False) # prevent recursive triggers when inline editing

#====INLINE CHEMICAL EDITING ====#
    def handle_cell_change(self, item):
                    row = item.row()
                    col = item.column()
                    row_id_item = self.table.item(row, 0)  # Hidden ID column

                    if not row_id_item:
                        return

                    row_id = int(row_id_item.text())

                    # Map column index to database field name
                    column_map = {
                        1: "name",
                        2: "cas_number",
                        3: "formula",
                        4: "common_name",
                        5: "iupac_name",
                        6: "location",
                        7: "quantity",
                        8: "safety_info_url",
                        9: "manufacturer",
                        10: "catalog_number",
                        11: "product_url"
                    }

                    if col not in column_map:
                        return

                    field = column_map[col]
                    new_value = item.text()

                    # Cast quantity to int if necessary
                    if field == "quantity":
                        try:
                            new_value = int(new_value)
                        except ValueError:
                            QMessageBox.warning(self, "Invalid Input", "Quantity must be an integer.")
                            self.load_data()
                            return

                    # Update database
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute(f"UPDATE Chemicals SET {field} = ? WHERE id = ?", (new_value, row_id))
                    conn.commit()
                    conn.close()
#======================================#

#========FOLDER SELECTION============#
    def process_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Images")
        if not folder:
            return
        supported_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
        for file in os.listdir(folder):
            if file.lower().endswith(supported_exts):
                full_path = os.path.join(folder, file)
                text = extract_text_from_image(full_path)
                parsed_info = parse_chemical_info(text)

                folder_name = os.path.basename(folder)
                if not parsed_info.get("location"):
                    parsed_info["location"] = folder_name

                dialog = ChemicalEntryDialog(parsed_info)
                if dialog.exec_() == QDialog.Accepted:
                    info = dialog.get_data()
                    save_to_database(info)
        self.load_data()

    # ======================================#

#==================google search=================#

    def open_google_search_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Search Reagent")

        layout = QFormLayout(dialog)
        manufacturer_input = QLineEdit()
        catalog_input = QLineEdit()
        layout.addRow("Manufacturer:", manufacturer_input)
        layout.addRow("Catalog Number:", catalog_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def search_and_open_dialog():
            manufacturer = manufacturer_input.text().strip()
            catalog = catalog_input.text().strip()
            if manufacturer and catalog:
                query = f"{manufacturer} {catalog}"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)

                info = {
                    "manufacturer": manufacturer,
                    "catalog_number": catalog,
                    "location": "",
                    "quantity": 1,
                    "name": "",
                    "cas_number": "",
                    "formula": "",
                    "common_name": "",
                    "iupac_name": "",
                    "product_url": None,
                    "safety_info_url": None
                }

                chem_dialog = ChemicalEntryDialog(info)
                if chem_dialog.exec_() == QDialog.Accepted:
                    final_info = chem_dialog.get_data()
                    save_to_database(final_info)
                    self.load_data()

            dialog.accept()

        buttons.accepted.connect(search_and_open_dialog)
        buttons.rejected.connect(dialog.reject)
        dialog.exec_()

    # ======================================#

    # ==================MANUAL ENTRY FOR CHEMICALS=================#
    def add_manual_entry(self):
        dialog = ChemicalEntryDialog()
        if dialog.exec_() == QDialog.Accepted:
            info = dialog.get_data()
            save_to_database(info)
            self.load_data()

    # ======================================#

    # ==================MANUAL ENTRY FOR CHEMICALS=================#
    def delete_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No selection", "Please select a row to delete.")
            return
        row = selected_items[0].row()
        compound_id = int(self.table.item(row, 0).text())

        confirm = QMessageBox.question(self, "Confirm Delete", f"Delete compound ID {compound_id}?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Chemicals WHERE id = ?", (compound_id,))
            conn.commit()
            conn.close()
            self.load_data()
            # ======================================#

    # ==================INLINE EDIT ENTRY FOR CHEMICALS=================#
    def edit_selected_chemical(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        # Assuming ID is stored in column 0 (hidden or visible)
        row = selected_items[0].row()
        row_id = int(self.table.item(row, 0).text())

        # Gather current info from the row to pass to dialog
        info = {
            "name": self.table.item(row, 1).text(),
            "cas_number": self.table.item(row, 2).text(),
            "formula": self.table.item(row, 3).text(),
            "common_name": self.table.item(row, 4).text(),
            "iupac_name": self.table.item(row, 5).text(),
            "location": self.table.item(row, 6).text(),
            "quantity": int(self.table.item(row, 7).text()),
            "manufacturer": self.table.item(row, 9).text(),
            "catalog_number": self.table.item(row, 10).text(),
            # Include any other fields as needed
        }

        dialog = ChemicalEntryDialog(info)
        if dialog.exec_() == QDialog.Accepted:
            updated_info = dialog.get_data()
            self.update_database_row(row_id, updated_info)
            self.load_data()  # refresh table display

            # ======================================#

    # ==================STORE EDITTED ENTRY FOR CHEMICALS=================#
    def update_database_row(self, row_id, info):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Chemicals SET
                name = ?,
                cas_number = ?,
                formula = ?,
                common_name = ?,
                iupac_name = ?,
                location = ?,
                quantity = ?,
                safety_info_url = ?,
                manufacturer = ?,
                catalog_number = ?,
                product_url = ?
            WHERE id = ?
        ''', (
            info.get("name"),
            info.get("cas_number"),
            info.get("formula"),
            info.get("common_name"),
            info.get("iupac_name"),
            info.get("location"),
            info.get("quantity", 1),
            info.get("safety_info_url"),
            info.get("manufacturer"),
            info.get("catalog_number"),
            info.get("product_url"),
            row_id
        ))
        conn.commit()
        conn.close()
   # ======================================#

   # ====================CHEMICAL INFO DIALOG BOX=====================#
class ChemicalEntryDialog(QDialog):
    def __init__(self, info=None):
        super().__init__()
        self.setFont(jetbrains_font)
        self.setWindowTitle("Enter Chemical Information")
        layout = QFormLayout()

        self.name_edit = QLineEdit(info.get("name", "") if info else "")
        self.cas_edit = QLineEdit(info.get("cas_number", "") if info else "")
        self.formula_edit = QLineEdit(info.get("formula", "") if info else "")
        self.common_name_edit = QLineEdit(info.get("common_name", "") if info else "")
        self.iupac_name_edit = QLineEdit(info.get("iupac_name", "") if info else "")
        self.location_edit = QLineEdit(info.get("location", "") if info else "")
        self.quantity_edit = QLineEdit(str(info.get("quantity", 1)) if info else "1")
        self.manufacturer_edit = QLineEdit(info.get("manufacturer", "") if info else "")
        self.catalog_number_edit = QLineEdit(info.get("catalog_number", "") if info else "")

        layout.addRow("Name:", self.name_edit)
        layout.addRow("CAS Number:", self.cas_edit)
        layout.addRow("Formula:", self.formula_edit)
        layout.addRow("Common Name:", self.common_name_edit)
        layout.addRow("IUPAC Name:", self.iupac_name_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow("Quantity:", self.quantity_edit)
        layout.addRow("Manufacturer:", self.manufacturer_edit)
        layout.addRow("Catalog Number:", self.catalog_number_edit)


        # GOOGLE SEARCH BUTTON
        self.search_button = QPushButton("Search Online")
        self.search_button.clicked.connect(self.open_google_search)
        layout.addWidget(self.search_button)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def open_google_search(self):
            manufacturer = self.manufacturer_edit.text().strip()
            catalog_number = self.catalog_number_edit.text().strip()
            if manufacturer and catalog_number:
                query = f"{manufacturer} {catalog_number}"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "cas_number": self.cas_edit.text().strip(),
            "formula": self.formula_edit.text().strip(),
            "common_name": self.common_name_edit.text().strip(),
            "iupac_name": self.iupac_name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "quantity": int(self.quantity_edit.text().strip() or "1"),
            "manufacturer": self.manufacturer_edit.text().strip(),
            "catalog_number": self.catalog_number_edit.text().strip(),
            "product_url": None,
            "safety_info_url": None
        }

def normalize_name(name):
    return name.strip().lower() if name else ""

# Inserts a new chemical into the database
def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Normalize the names for comparison
    name = normalize_name(info.get("name"))
    common_name = normalize_name(info.get("common_name"))
    iupac_name = normalize_name(info.get("iupac_name"))

    # Check if an entry with the same name already exists
    cursor.execute('''
        SELECT id, quantity FROM Chemicals
        WHERE LOWER(name) = ? OR LOWER(common_name) = ? OR LOWER(iupac_name) = ?
    ''', (name, common_name, iupac_name))

    existing = cursor.fetchone()

    if existing:
        existing_id, existing_qty = existing
        new_qty = existing_qty + info.get("quantity", 1)

        # Update only the quantity for the existing compound
        cursor.execute('''
            UPDATE Chemicals
            SET quantity = ?
            WHERE id = ?
        ''', (new_qty, existing_id))
    else:
        # Insert new entry, using original (non-normalized) info
        cursor.execute('''
            INSERT INTO Chemicals (
                name, cas_number, formula, common_name, iupac_name, location, quantity,
                safety_info_url, manufacturer, catalog_number, product_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            info.get("name"),
            info.get("cas_number"),
            info.get("formula"),
            info.get("common_name"),
            info.get("iupac_name"),
            info.get("location"),
            info.get("quantity", 1),
            info.get("safety_info_url"),
            info.get("manufacturer"),
            info.get("catalog_number"),
            info.get("product_url"),
        ))

    conn.commit()
    conn.close()

def process_image_file(image_path):
    print(f"Processing: {image_path}")
    text = extract_text_from_image(image_path)
    parsed_info = parse_chemical_info(text)

    # Use folder name as default location if location is empty
    folder_name = os.path.basename(os.path.dirname(image_path))
    if not parsed_info.get("location"):
        parsed_info["location"] = folder_name  # auto-fill location

    # Show dialog with editable fields, including location
    dialog = ChemicalEntryDialog(parsed_info)
    if dialog.exec_() == QDialog.Accepted:
        info = dialog.get_data()
        save_to_database(info)


if __name__ == "__main__":
    create_database()
    app = QApplication(sys.argv)

    # Set Style
    app.setFont(jetbrains_font)
    app.setStyleSheet(dark_stylesheet)

    #Create Window
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
