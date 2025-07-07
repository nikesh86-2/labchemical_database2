import sqlite3
from config import DB_FILE

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

def normalize(s):
    return s.strip().lower() if s else None

def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Normalize incoming values
    name = normalize(info.get("name"))
    common_name = normalize(info.get("common_name"))
    cas_number = normalize(info.get("cas_number"))
    catalog_number = normalize(info.get("catalog_number"))

    existing = None

    # Priority 1: Match by CAS number
    if cas_number:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(cas_number) = ?
        ''', (cas_number,))
        existing = cursor.fetchone()

    # Priority 2: Match by catalog number
    if not existing and catalog_number:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(catalog_number) = ?
        ''', (catalog_number,))
        existing = cursor.fetchone()

    # Priority 3: Match name when common_name is empty
    if not existing and name:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(name) = ?
            AND (common_name IS NULL OR TRIM(common_name) = '')
        ''', (name,))
        existing = cursor.fetchone()

    # Priority 4: Match common_name when name is empty
    if not existing and common_name:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(common_name) = ?
            AND (name IS NULL OR TRIM(name) = '')
        ''', (common_name,))
        existing = cursor.fetchone()

    # Priority 5: common_name matches existing name, and their common_name is empty
    if not existing and common_name:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(name) = ?
            AND (common_name IS NULL OR TRIM(common_name) = '')
        ''', (common_name,))
        existing = cursor.fetchone()

    # Priority 6: name matches existing common_name, and their name is empty
    if not existing and name:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals
            WHERE LOWER(common_name) = ?
            AND (name IS NULL OR TRIM(name) = '')
        ''', (name,))
        existing = cursor.fetchone()

    # Merge if match found
    if existing:
        existing_id, existing_qty = existing
        new_qty = existing_qty + info.get("quantity", 1)
        cursor.execute('''
            UPDATE Chemicals
            SET quantity = ?
            WHERE id = ?
        ''', (new_qty, existing_id))
    else:
        # Insert new row
        cursor.execute('''
            INSERT INTO Chemicals (
                name, cas_number, formula, common_name, iupac_name, location, quantity,
                safety_info_url, manufacturer, catalog_number, product_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
