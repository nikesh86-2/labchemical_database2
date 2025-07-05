import sys
import os
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import urllib.parse
import webbrowser
import easyocr
from PIL import Image, ImageEnhance
import pubchempy as pcp
import numpy as np
import re
import torch
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QMessageBox,
    QFileDialog, QDialog, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt

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


# Path to local SQLite database file
DB_FILE = "chemical_inventory.db"

# OCR engine setup (EasyOCR for English, using GPU if available)
reader = easyocr.Reader(['en'], gpu=False)

def extract_text_from_image(image_path):
    """
       Enhance image contrast using multiple contrast values and extract text using OCR.
       Returns the most complete result found.
       """
    image = Image.open(image_path)
    best_text = ""
    best_score = 0

    # Try multiple contrast enhancements to maximize OCR accuracy
    for contrast in [0.8, 1.0, 1.5, 2.0]:
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(contrast)

        img_np = np.array(enhanced_image)

        # Run OCR
        text_results = reader.readtext(img_np)
        full_text = " ".join([result[1] for result in text_results])

        # Keep the best (longest) result
        if len(full_text) > best_score:
            best_score = len(full_text)
            best_text = full_text

    return best_text

#=========================#
# PUBCHEM DATA ENRICHMENT
#=========================#

def enrich_with_pubchem(data):
    """
    Use PubChem API to fetch additional chemical data using CAS number.
    Adds: IUPAC name, common name, molecular formula, safety info URL.
    """
    cas = data.get("cas_number")
    if not cas:
       return data

    try:
        compounds = pcp.get_compounds(cas, 'name')
        if compounds:
            comp = compounds[0]  # Use first result

            data["iupac_name"] = comp.iupac_name
            data["common_name"] = comp.synonyms[0] if comp.synonyms else None
            data["formula"] = comp.molecular_formula
            data["safety_info_url"] = f"https://pubchem.ncbi.nlm.nih.gov/compound/{comp.cid}"
    except Exception as e:
        print(f"PubChem lookup failed for CAS {cas}: {e}")
    return data


def parse_chemical_info(text):
    """
    Extract relevant fields like CAS number and catalog number from raw text.
    Enhances the parsed data using PubChem.
    """
    data = {
        "name": None,
        "cas_number": None,
        "formula": None,
        "common_name": None,
        "iupac_name": None,
        "manufacturer": None,
        "catalog_number": None
    }

    # Extract CAS number (e.g., 50-00-0)
    cas_match = re.search(r'\b(\d{2,7}-\d{2}-\d)\b', text)
    if cas_match:
        data["cas_number"] = cas_match.group(1)

    # Extract catalog number if available
    catalog_match = re.search(r"Catalog\s*(?:No\.|Number)[:\s]*([\w-]+)", text, re.IGNORECASE)
    if catalog_match:
        data["catalog_number"] = catalog_match.group(1).strip()

    return enrich_with_pubchem(data)


# --------- Database helper ---------
def init_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cas_number TEXT,
            formula TEXT,
            common_name TEXT,
            iupac_name TEXT,
            location TEXT,
            quantity INTEGER,
            safety_info_url TEXT,
            manufacturer TEXT,
            catalog_number TEXT,
            product_url TEXT
        )
    ''')
    conn.commit()
    conn.close()


# --- Your assumed imports or definitions ---
# jetbrains_font = ...
# dark_stylesheet = ...
# DB_FILE = "chemicals.db"
# create_database(), extract_text_from_image(), parse_chemical_info()

# ------------------ MainWindow --------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Inventory")
        self.resize(1000, 600)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self.handle_cell_change)

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

        self.load_data()

    def use_bottle(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a chemical to mark as used.")
            return

        row = selected_items[0].row()
        compound_id = int(self.table.item(row, 0).text())
        quantity_item = self.table.item(row, 7)
        current_quantity = int(quantity_item.text())

        if current_quantity <= 0:
            QMessageBox.information(self, "Already Empty", "This chemical has no remaining quantity.")
            return

        new_quantity = current_quantity - 1

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE Chemicals SET quantity = ? WHERE id = ?", (new_quantity, compound_id))
        conn.commit()
        conn.close()

        self.load_data()

        if new_quantity == 0:
            QMessageBox.critical(self, "Reorder Alert", "Quantity is now 0. Please reorder this chemical.")

    def load_data(self):
        self.table.blockSignals(True)
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
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # ID read-only
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.table.blockSignals(False)

    def handle_cell_change(self, item):
        row = item.row()
        col = item.column()
        row_id_item = self.table.item(row, 0)
        if not row_id_item:
            return
        row_id = int(row_id_item.text())

        column_map = {
            1: "name",
            2: "cas_number",
            3: "formula",
            4: "common_name",
            5: "iupac_name",
            6: "location",
            7: "quantity",
            8: "manufacturer",
            9: "catalog_number",
        }

        if col not in column_map:
            return

        field = column_map[col]
        new_value = item.text()

        if field == "quantity":
            try:
                new_value = int(new_value)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Quantity must be an integer.")
                self.load_data()
                return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE Chemicals SET {field} = ? WHERE id = ?", (new_value, row_id))
        conn.commit()
        conn.close()

    def process_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Images")
        if not folder:
            return

        asyncio.run(self.process_images_async(folder))

    async def process_images_async(self, folder):
        supported_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
        image_files = []
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(supported_exts):
                    image_files.append(os.path.join(root, file))

        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=4)

        tasks = [
            loop.run_in_executor(executor, partial(self.extract_and_parse, path))
            for path in image_files
        ]

        parsed_results = await asyncio.gather(*tasks)

        for info in parsed_results:
            if info is None:
                continue
            if not info.get("location"):
                info["location"] = os.path.basename(folder)

            dialog = ChemicalEntryDialog(info)
            if dialog.exec_() == QDialog.Accepted:
                final_info = dialog.get_data()
                save_to_database(final_info)

        self.load_data()

    def extract_and_parse(self, image_path):
        print(f"Processing: {image_path}")
        text = extract_text_from_image(image_path)
        torch.cuda.empty_cache()
        if not text.strip():
            return None
        parsed_info = parse_chemical_info(text)
        return parsed_info

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

    def add_manual_entry(self):
        dialog = ChemicalEntryDialog()
        if dialog.exec_() == QDialog.Accepted:
            info = dialog.get_data()
            save_to_database(info)
            self.load_data()

    def delete_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No selection", "Please select a row to delete.")
            return

        row = selected_items[0].row()
        compound_id = int(self.table.item(row, 0).text())

        confirm = QMessageBox.question(
            self, "Confirm Delete", f"Delete compound ID {compound_id}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM Chemicals WHERE id = ?", (compound_id,))
            conn.commit()
            conn.close()
            self.load_data()

# ------------------ ChemicalEntryDialog --------------------

class ChemicalEntryDialog(QDialog):
    def __init__(self, info=None):
        super().__init__()
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_data(self):
        try:
            quantity = int(self.quantity_edit.text())
        except ValueError:
            quantity = 1
        return {
            "name": self.name_edit.text(),
            "cas_number": self.cas_edit.text(),
            "formula": self.formula_edit.text(),
            "common_name": self.common_name_edit.text(),
            "iupac_name": self.iupac_name_edit.text(),
            "location": self.location_edit.text(),
            "quantity": quantity,
            "manufacturer": self.manufacturer_edit.text(),
            "catalog_number": self.catalog_number_edit.text(),
        }

# ------------------ Database and OCR utilities --------------------

def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Check if chemical already exists by name or cas_number or formula (simple logic)
    cursor.execute(
        "SELECT id FROM Chemicals WHERE (name = ? OR cas_number = ? OR formula = ?) LIMIT 1",
        (info.get("name", ""), info.get("cas_number", ""), info.get("formula", ""))
    )
    existing = cursor.fetchone()
    if existing:
        # Update existing
        cursor.execute('''
        UPDATE Chemicals SET
            name = ?, cas_number = ?, formula = ?, common_name = ?, iupac_name = ?,
            location = ?, quantity = ?, manufacturer = ?, catalog_number = ?
        WHERE id = ?
        ''', (
            info.get("name", ""),
            info.get("cas_number", ""),
            info.get("formula", ""),
            info.get("common_name", ""),
            info.get("iupac_name", ""),
            info.get("location", ""),
            info.get("quantity", 1),
            info.get("manufacturer", ""),
            info.get("catalog_number", ""),
            existing[0]
        ))
    else:
        cursor.execute('''
        INSERT INTO Chemicals
            (name, cas_number, formula, common_name, iupac_name, location, quantity, manufacturer, catalog_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            info.get("name", ""),
            info.get("cas_number", ""),
            info.get("formula", ""),
            info.get("common_name", ""),
            info.get("iupac_name", ""),
            info.get("location", ""),
            info.get("quantity", 1),
            info.get("manufacturer", ""),
            info.get("catalog_number", "")
        ))
    conn.commit()
    conn.close()

#------------------

if __name__ == "__main__":
    init_database()

    app = QApplication(sys.argv)
    app.setFont(jetbrains_font)
    app.setStyleSheet(dark_stylesheet)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
