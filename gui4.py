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
from PyQt5.QtGui import QFontfrom PyQt5.QtGui import QFont
import easyocr
import pubchempy as pcp
import numpy as np
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSignal, QObject, QTimer

class WorkerSignals(QObject):
    finished = pyqtSignal(dict)  # Emit parsed info when done

class ImageWorker(QRunnable):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.signals = WorkerSignals()

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
#=========================#
# IMPORTS AND SETUP
#=========================#

# Path to local SQLite database file
DB_FILE = "chemical_inventory.db"

# OCR engine setup (EasyOCR for English, using GPU if available)
reader = easyocr.Reader(['en'], gpu=True)

#=========================#
# DATABASE CREATION
#=========================#

def create_database():
    """
    Create a SQLite database with a 'Chemicals' table if it doesn't exist.
    Stores metadata about chemical reagents.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Table schema with all expected chemical fields
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

#=========================#
# OCR IMAGE TEXT EXTRACTION
#=========================#

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

#=========================#
# PARSE TEXT TO CHEMICAL FIELDS
#=========================#

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

#=========================#
# MAIN WINDOW CLASS
#=========================#

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chemical Inventory")
        self.resize(1000, 600)

        # Setup table view for inventory
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self.handle_cell_change)

        # Buttons and actions
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

        # Arrange buttons in a row
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.process_folder_btn)
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.add_manual_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.use_bottle_button)

        # Combine table and buttons
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.load_data()

    #=========================#
    # Reduce quantity by 1
    def use_bottle(self):
        """
        Decrease chemical quantity by 1 and update database.
        Alert if quantity reaches zero.
        """
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

    #=========================#
    def load_data(self):
        """
        Load chemical records from DB into the GUI table.
        """
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
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # Make ID read-only
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.table.blockSignals(False)

    #=========================#
    def handle_cell_change(self, item):
        """
        Update database when any editable cell is modified inline.
        """
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
            8: "safety_info_url",
            9: "manufacturer",
            10: "catalog_number",
            11: "product_url"
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

    #=========================#
    def process_image_folder(self):
        """
        Select folder, scan all images, parse chemical text, confirm data entry via dialog.
        """
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Images")
        if not folder:
            return
        for root, dirs, files in os.walk(folder):
            for file in files:
                supported_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff')
                if file.lower().endswith(supported_exts):
                    full_path = os.path.join(root, file)
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

    #=========================#
    def open_google_search_dialog(self):
        """
        Prompt user for manufacturer + catalog number, perform Google search, allow data entry.
        """
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

# Opens a dialog to manually add a chemical entry
    def add_manual_entry(self):
        dialog = ChemicalEntryDialog()
        if dialog.exec_() == QDialog.Accepted:
            info = dialog.get_data()         # Extract the data from the form
            save_to_database(info)           # Save it to the database
            self.load_data()                 # Refresh table to show new entry

# Deletes the currently selected chemical from the table and database
    def delete_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No selection", "Please select a row to delete.")
            return

        row = selected_items[0].row()
        compound_id = int(self.table.item(row, 0).text())  # ID in column 0

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
            self.load_data()  # Refresh table

# Opens a dialog to edit selected chemical information
    def edit_compound(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No selection", "Please select a row to edit.")
            return

        row = selected_items[0].row()
        row_id = int(self.table.item(row, 0).text())

        # Collect existing info from the selected row
        info = {
            "name": self.table.item(row, 1).text(),
            "cas_number": self.table.item(row, 2).text(),
            "formula": self.table.item(row, 3).text(),
            "common_name": self.table.item(row, 4).text(),
            "iupac_name": self.table.item(row, 5).text(),
            "location": self.table.item(row, 6).text(),
            "quantity": int(self.table.item(row, 7).text()),
            "manufacturer": self.table.item(row, 8).text(),
            "catalog_number": self.table.item(row, 9).text(),
        }

        dialog = ChemicalEntryDialog(info)
        if dialog.exec_() == QDialog.Accepted:
            updated_info = dialog.get_data()
            self.update_database_row(row_id, updated_info)  # Assumes row_id is defined above
            self.load_data()

    # Updates a row in the Chemicals table with new values
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

class ChemicalEntryDialog(QDialog):
    def __init__(self, info=None):
        super().__init__()
        self.setFont(jetbrains_font)
        self.setWindowTitle("Enter Chemical Information")
        layout = QFormLayout()

        # Fields populated with existing data (if editing) or left empty
        self.name_edit = QLineEdit(info.get("name", "") if info else "")
        self.cas_edit = QLineEdit(info.get("cas_number", "") if info else "")
        self.formula_edit = QLineEdit(info.get("formula", "") if info else "")
        self.common_name_edit = QLineEdit(info.get("common_name", "") if info else "")
        self.iupac_name_edit = QLineEdit(info.get("iupac_name", "") if info else "")
        self.location_edit = QLineEdit(info.get("location", "") if info else "")
        self.quantity_edit = QLineEdit(str(info.get("quantity", 1)) if info else "1")
        self.manufacturer_edit = QLineEdit(info.get("manufacturer", "") if info else "")
        self.catalog_number_edit = QLineEdit(info.get("catalog_number", "") if info else "")

        # Add all fields to the form
        layout.addRow("Name:", self.name_edit)
        layout.addRow("CAS Number:", self.cas_edit)
        layout.addRow("Formula:", self.formula_edit)
        layout.addRow("Common Name:", self.common_name_edit)
        layout.addRow("IUPAC Name:", self.iupac_name_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow("Quantity:", self.quantity_edit)
        layout.addRow("Manufacturer:", self.manufacturer_edit)
        layout.addRow("Catalog Number:", self.catalog_number_edit)

        # Google search button (to help identify or verify the compound)
        self.search_button = QPushButton("Search Online")
        self.search_button.clicked.connect(self.open_google_search)
        layout.addWidget(self.search_button)

        # OK / Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    # Launch a Google search with manufacturer and catalog number
    def open_google_search(self):
        manufacturer = self.manufacturer_edit.text().strip()
        catalog_number = self.catalog_number_edit.text().strip()
        if manufacturer and catalog_number:
            query = f"{manufacturer} {catalog_number}"
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)

    # Return entered data as a dictionary
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

    # Extract text from image and process it as a chemical record
def process_image_file(image_path):
        print(f"Processing: {image_path}")
        text = extract_text_from_image(image_path)
        parsed_info = parse_chemical_info(text)

        folder_name = os.path.basename(os.path.dirname(image_path))
        if not parsed_info.get("location"):
            parsed_info["location"] = folder_name  # Use folder name as fallback location

        # Launch dialog to review/edit before saving
        dialog = ChemicalEntryDialog(parsed_info)
        if dialog.exec_() == QDialog.Accepted:
            info = dialog.get_data()
            save_to_database(info)


if __name__ == "__main__":
    create_database()  # Ensure the database and table exist
    app = QApplication(sys.argv)

    app.setFont(jetbrains_font)
    app.setStyleSheet(dark_stylesheet)  # Apply custom styling

    window = MainWindow()  # Instantiate main window
    window.show()

    sys.exit(app.exec_())  # Start event loop
