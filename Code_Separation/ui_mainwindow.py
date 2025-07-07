from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QVBoxLayout,
                             QPushButton, QWidget, QTableWidget, QTableWidgetItem,
                             QHBoxLayout, QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QMessageBox)
from PyQt5.QtCore import Qt
import sqlite3
from database import save_to_database
from ocr_utils import extract_text_from_image, parse_chemical_info
from chemical_dialog import ChemicalEntryDialog
from config import DB_FILE
import os
import webbrowser
import urllib.parse

# ========== MAIN APPLICATION WINDOW ==========
class MainWindow(QMainWindow):
    def __init__(self,db_uri):
        super().__init__()
        self.db_uri = db_uri
        self.setWindowTitle("Chemical Inventory")
        self.resize(1000, 600)

        # Table for chemical display
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemChanged.connect(self.handle_cell_change)

        #search function
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chemicals by name, CAS, catalog...")

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_database)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Buttons
        self.process_folder_btn = QPushButton("Process Image Folder")
        self.process_folder_btn.clicked.connect(self.process_image_folder)

        self.online_search_button = QPushButton("Search Reagent Online")
        self.online_search_button.clicked.connect(self.open_google_search_dialog)

        self.add_manual_button = QPushButton("Add Compound Manually")
        self.add_manual_button.clicked.connect(self.add_manual_entry)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)

        self.refresh_button = QPushButton("Refresh Table")
        self.refresh_button.clicked.connect(self.load_data)

        self.use_bottle_button = QPushButton("Use Bottle")
        self.use_bottle_button.clicked.connect(self.use_bottle)

        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.process_folder_btn)
        button_layout.addWidget(self.online_search_button)
        button_layout.addWidget(self.add_manual_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.use_bottle_button)
        button_layout.addWidget(self.exit_button)

        layout = QVBoxLayout()
        layout.addLayout(search_layout)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Load data
        self.load_data()

    def search_database(self):
            query_text = self.search_input.text().strip()
            conn = sqlite3.connect(self.db_uri, uri=True)
            cursor = conn.cursor()

            if query_text:
                # Search by name, common_name, cas_number, catalog_number (case-insensitive)
                cursor.execute('''
                    SELECT * FROM Chemicals
                    WHERE
                        LOWER(name) LIKE ? OR
                        LOWER(common_name) LIKE ? OR
                        LOWER(cas_number) LIKE ? OR
                        LOWER(catalog_number) LIKE ?
                    ORDER BY name
                ''', (f'%{query_text.lower()}%',) * 4)
            else:
                # If no search, just show all
                cursor.execute('SELECT * FROM Chemicals ORDER BY name')

            results = cursor.fetchall()
            conn.close()

            self.load_data_into_table(results)

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

            conn = sqlite3.connect(self.db_uri, uri=True) # update the database
            cursor = conn.cursor()
            cursor.execute("UPDATE Chemicals SET quantity = ? WHERE id = ?", (new_quantity, compound_id))
            conn.commit()
            conn.close()

            self.load_data()

            if new_quantity == 0:
                QMessageBox.critical(self, "Reorder Alert", "Quantity is now 0. Please reorder this chemical.")
# thinking about adding email facility

    def load_data(self):
        conn = sqlite3.connect(self.db_uri, uri=True)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, cas_number, formula, common_name, iupac_name,
                   location, quantity, safety_info_url, manufacturer, catalog_number
            FROM Chemicals
        """)
        rows = cursor.fetchall()
        conn.close()
        self.load_data_into_table(rows)

    def load_data_into_table(self, rows):
        headers = ["ID", "Name", "CAS Number", "Formula", "Common Name", "IUPAC Name", "Location", "Quantity",
                   "Safety Info URL", "Manufacturer", "Catalog Number"]
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_idx, col_idx, item)
                if col_idx == 0:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.table.blockSignals(False)

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
                    conn = sqlite3.connect(self.db_uri, uri=True)
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

                dialog = ChemicalEntryDialog(parsed_info, image_path=full_path)
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
                    "product_url": "",
                    "safety_info_url": ""
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
            conn = sqlite3.connect(self.db_uri, uri=True)
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
        conn = sqlite3.connect(self.db_uri, uri=True)
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