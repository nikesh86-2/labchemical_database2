import os
import re
import sqlite3
import cv2
import requests
import easyocr

# === CONFIG ===
DB_FILE = "chemical_inventory.db"

# === EasyOCR Reader ===
reader = easyocr.Reader(['en'], gpu=True)

# === DATABASE ===
def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            iupac_name TEXT,
            cas_number TEXT,
            formula TEXT,
            inchikey TEXT,
            location TEXT,
            quantity INTEGER DEFAULT 1,
            safety_info_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

# === IMAGE PREPROCESSING ===
def preprocess_grayscale_contrast(image_path, alpha=2.0, beta=10):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    return adjusted

# === CAS Extraction ===
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

# === OCR CAS + Name Fallback ===
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
                print(f"✅ Found CAS {cas} with alpha={alpha}, beta={beta}")
                return cas
    print("❌ No valid CAS found with tested alpha/beta values.")
    return None

def detect_name_from_text(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        if re.match(r'^\d{2,7}-\d{2}-\d$', line):
            continue
        if any(c.isalpha() for c in line) and len(line.split()) < 4:
            return line
    return lines[0] if lines else "Unknown"

# === PubChem Lookup ===
def fetch_pubchem_data(cas=None, name=None):
    query = cas or name
    if not query:
        return {}

    fields = "Title,IUPACName,MolecularFormula,InChIKey"
    url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/xref/RN/{cas}/property/{fields}/JSON"
           if cas else
           f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/{fields}/JSON")

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        props = res.json()['PropertyTable']['Properties'][0]
        return {
            "name": props.get("Title"),             # Common name
            "iupac_name": props.get("IUPACName"),   # IUPAC
            "formula": props.get("MolecularFormula"),
            "inchikey": props.get("InChIKey"),
            "safety_info_url": f"https://pubchem.ncbi.nlm.nih.gov/#query={query}"
        }
    except Exception as e:
        print(f"⚠️ PubChem lookup failed for {query}: {e}")
        return {}

# === DB Save ===
def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print(f"💾 Saving info to DB: {info}")
    try:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals WHERE cas_number = ? OR (cas_number IS NULL AND name = ?)
        ''', (info.get("cas_number"), info.get("name")))
        row = cursor.fetchone()

        if row:
            new_quantity = row[1] + info.get('quantity', 1)
            cursor.execute('''
                UPDATE Chemicals
                SET quantity = ?, location = ?
                WHERE id = ?
            ''', (new_quantity, info.get('location'), row[0]))
            print(f"🔄 Updated existing chemical with id {row[0]}")
        else:
            cursor.execute('''
                INSERT INTO Chemicals (name, iupac_name, cas_number, formula, inchikey, location, quantity, safety_info_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                info.get("name"),
                info.get("iupac_name"),
                info.get("cas_number"),
                info.get("formula"),
                info.get("inchikey"),
                info.get("location"),
                info.get("quantity", 1),
                info.get("safety_info_url")
            ))
            print("➕ Inserted new chemical record.")
        conn.commit()
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
    finally:
        conn.close()

# === Manual Entry ===
def manual_entry(fallback_name):
    print(f"\n⚠️ No CAS or name reliably detected for '{fallback_name}'.")
    name = input(f"Enter chemical/product name [{fallback_name}]: ").strip() or fallback_name
    return {
        "name": name,
        "iupac_name": None,
        "cas_number": None,
        "formula": None,
        "inchikey": None,
        "location": None,
        "quantity": 1,
        "safety_info_url": None
    }

# === PROCESS IMAGE ===
def process_image(image_path, location):
    print(f"\n🔍 Processing {os.path.basename(image_path)}...")
    fallback_name = os.path.splitext(os.path.basename(image_path))[0]
    cas = extract_cas_number_from_image(image_path)

    name_candidate = fallback_name
    if not cas:
        img = preprocess_grayscale_contrast(image_path)
        texts = reader.readtext(img, detail=0, paragraph=True)
        ocr_text = "\n".join(texts)
        name_candidate = detect_name_from_text(ocr_text)
        print(f"🔎 Possible chemical name: {name_candidate}")

    chemical_info = {
        "cas_number": cas,
        "location": location,
        "quantity": 1,
        "name": name_candidate,
        "iupac_name": None,
        "formula": None,
        "inchikey": None,
        "safety_info_url": None
    }

    enriched = fetch_pubchem_data(cas=cas, name=name_candidate)
    if enriched:
        if "name" in enriched and enriched["name"]:
            chemical_info["name"] = enriched["name"]
        if "iupac_name" in enriched:
            chemical_info["iupac_name"] = enriched["iupac_name"]
        if "formula" in enriched:
            chemical_info["formula"] = enriched["formula"]
        if "inchikey" in enriched:
            chemical_info["inchikey"] = enriched["inchikey"]
        if "safety_info_url" in enriched:
            chemical_info["safety_info_url"] = enriched["safety_info_url"]

    def is_name_invalid(name):
        if not name:
            return True
        name = name.strip().lower()
        return (
            name in ["substance", "chemical", "product", "unknown", ""] or
            len(name) < 3 or
            not any(c.isalpha() for c in name)
        )

    if not cas or is_name_invalid(chemical_info.get("name")):
        print("⚠️ Falling back to manual entry due to missing or unreliable CAS/name.")
        chemical_info = manual_entry(fallback_name)
        chemical_info["location"] = location

    save_to_database(chemical_info)
    print("✅ Done.")

# === FOLDER WALK ===
def process_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        location = os.path.basename(root)
        for fname in files:
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                fpath = os.path.join(root, fname)
                process_image(fpath, location)

# === MAIN ===
if __name__ == "__main__":
    create_database()
    folder = input("Enter path to root folder of chemical images: ").strip()
    if os.path.isdir(folder):
        process_folder(folder)
    else:
        print("❌ Folder not found.")
