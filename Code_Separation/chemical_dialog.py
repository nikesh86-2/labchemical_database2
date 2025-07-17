from PyQt5.QtWidgets import QDialog, QMessageBox, QLabel, QLineEdit, QPushButton, QFormLayout, QDialogButtonBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from styles import jetbrains_font
import webbrowser
import urllib.parse
import os
from ocr_utils import enrich_with_pubchem

   # ====================CHEMICAL INFO DIALOG BOX=====================#
class ChemicalEntryDialog(QDialog):
    def __init__(self, info=None, image_path=None):
        super().__init__()
        self.setFont(jetbrains_font)
        self.setWindowTitle("Enter Chemical Information")
        layout = QFormLayout()

        # === THUMBNAIL PREVIEW ===
        # Show thumbnail if image path is provided
        if image_path and os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    image_label = QLabel()
                    image_label.setPixmap(pixmap)
                    image_label.setAlignment(Qt.AlignCenter)
                    layout.addRow("Image Preview:", image_label)
                else:
                    print(f"Warning: Failed to load pixmap from {image_path}")
            except Exception as e:
                print(f"Error loading thumbnail: {e}")

        self.name_edit = QLineEdit(info.get("name", "") if info else "")
        self.cas_edit = QLineEdit(info.get("cas_number", "") if info else "")
        self.formula_edit = QLineEdit(info.get("formula", "") if info else "")
        self.common_name_edit = QLineEdit(info.get("common_name", "") if info else "")
        self.iupac_name_edit = QLineEdit(info.get("iupac_name", "") if info else "")
        self.location_edit = QLineEdit(info.get("location", "") if info else "")
        self.quantity_edit = QLineEdit(str(info.get("quantity", 1)) if info else "1")
        self.manufacturer_edit = QLineEdit(info.get("manufacturer", "") if info else "")
        self.catalog_number_edit = QLineEdit(info.get("catalog_number", "") if info else "")
        self.fetch_pubchem_btn = QPushButton("Fetch from PubChem")
        self.fetch_pubchem_btn.clicked.connect(self.fetch_pubchem_data)
        self.safety_info_url_edit = QLineEdit(info.get("safety_info_url", "") if info else "")

        layout.addRow("Name:", self.name_edit)
        layout.addRow("CAS Number:", self.cas_edit)
        layout.addWidget(self.fetch_pubchem_btn)
        layout.addRow("Formula:", self.formula_edit)
        layout.addRow("Common Name:", self.common_name_edit)
        layout.addRow("IUPAC Name:", self.iupac_name_edit)
        layout.addRow("Location:", self.location_edit)
        layout.addRow("Quantity:", self.quantity_edit)
        layout.addRow("Manufacturer:", self.manufacturer_edit)
        layout.addRow("Catalog Number:", self.catalog_number_edit)
        layout.addRow("Safety Info URL:", self.safety_info_url_edit)

        # === SAFETY INFO LINK (OPTIONAL) ===
        if info and info.get("safety_info_url"):
            self.safety_info_url = info["safety_info_url"]
            link_label = QLabel(f'<a href="{self.safety_info_url}">View Safety Info</a>')
            link_label.setOpenExternalLinks(True)
            layout.addRow("Safety Info:", link_label)
        else:
            self.safety_info_url = None

        # GOOGLE SEARCH BUTTON
        self.search_button = QPushButton("Search Online")
        self.search_button.clicked.connect(self.open_google_search)
        layout.addWidget(self.search_button)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def fetch_pubchem_data(self):
            cas = self.cas_edit.text().strip()
       #     print(cas)
            if not cas:
                QMessageBox.warning(self, "No CAS Number", "Please enter a CAS number to fetch data.")
                return

            try:
            
                data = enrich_with_pubchem({"cas_number": cas})
                if not data or not any(data.get(k) for k in ("iupac_name", "common_name", "formula")):
                    # Nothing useful found – fallback to Google
                    QMessageBox.information(
                        self,
                        "No PubChem Data",
                        f"No PubChem data found for CAS {cas}. A Google search will now open."
                    )
                    query = f"{cas}"
                    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                    webbrowser.open(url)
                    return

                # Update fields with returned data
                self.name_edit.setText(data.get("name", ""))
                self.formula_edit.setText(data.get("formula", ""))
                self.common_name_edit.setText(data.get("common_name", ""))
                self.iupac_name_edit.setText(data.get("iupac_name", ""))
                self.safety_info_url_edit.setText(data.get("safety_info_url", ""))
               # self.manufacturer_edit.setText(data.get("manufacturer", ""))
               # self.catalog_number_edit.setText(data.get("catalog_number", ""))
               # self.product_url_edit.setText(data.get("product_url", ""))

                # success message
                QMessageBox.information(self, "Success", "Data fetched from PubChem and fields updated.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error fetching data: {e}")

    def open_google_search(self):
        manufacturer = self.manufacturer_edit.text().strip()
        catalog_number = self.catalog_number_edit.text().strip()
        print(f"Manufacturer: {manufacturer}, Catalog Number: {catalog_number}")  # Debug
        if manufacturer and catalog_number:
            query = f"{manufacturer} {catalog_number}"
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
        else:
            QMessageBox.warning(self, "Missing Info", "Please enter both manufacturer and catalog number.")

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
            "safety_info_url": self.safety_info_url_edit.text().strip(),
            "product_url": getattr(self, "product_url", None)
        }
