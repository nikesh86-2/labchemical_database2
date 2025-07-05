import os
import re
import sqlite3
import cv2
import requests
import easyocr  # new import

# === CONFIG ===
CHEMSPIDER_API_KEY = "xduPDRiOrYasBMYJbmIEf4d9i90J2B3G2585r1tk"   # Replace with your API key

# === EasyOCR Reader (GPU enabled) ===
reader = easyocr.Reader(['en'], gpu=True)  # Enable GPU for speed

# === DATABASE ===
DB_FILE = "chemical_inventory.db"  # This should be outside the function, at the top of your file

def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cas_number TEXT,
            formula TEXT,
            location TEXT,
            quantity INTEGER DEFAULT 1,
            safety_info_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

#=== IMAGE PREPROCESSING ===
def preprocess_grayscale_contrast(image_path, alpha=2.0, beta=10):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    return adjusted

# === CAS Extraction from text ===
def extract_cas_number(text):
    # Normalize separators and characters
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

# === Extract CAS number from image by scanning alpha/beta with EasyOCR ===
def extract_cas_number_from_image(image_path):
    alpha_values = [1.5, 2.0, 2.5]
    beta_values = [0, 10, 20]

    for alpha in alpha_values:
        for beta in beta_values:
            img = preprocess_grayscale_contrast(image_path, alpha=alpha, beta=beta)
            # EasyOCR returns list of text blocks detected; join into paragraph
            texts = reader.readtext(img, detail=0, paragraph=True)
            text = "\n".join(texts)
            cas = extract_cas_number(text)
            if cas:
                print(f"✅ Found CAS {cas} with alpha={alpha}, beta={beta}")
                return cas
                print("❌ No valid CAS found with tested alpha/beta values.")
            return None

# === PubChem Lookup ===
def fetch_pubchem_data(cas=None, name=None, formula=None):
    query = cas or name or formula
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
            "name": props.get("IUPACName"),
            "formula": props.get("MolecularFormula"),
            "inchikey": props.get("InChIKey"),
            "safety_info_url": f"https://pubchem.ncbi.nlm.nih.gov/#query={query}"
        }
    except Exception as e:
        print(f"⚠️ PubChem lookup failed for {query}: {e}")
        return {}

# === ChemSpider Hazard Lookup ===
def get_chemspider_id(inchikey):
    url = "https://api.rsc.org/compounds/v1/filter/inchikey"
    headers = {"apikey": CHEMSPIDER_API_KEY}
    try:
        response = requests.post(url, json={"inchikey": inchikey}, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("queryId")
    except Exception as e:
        print(f"⚠️ ChemSpider ID lookup failed: {e}")
        return None

def get_hazard_info_chemspider(query_id):
    url = f"https://api.rsc.org/compounds/v1/filter/{query_id}/results"
    headers = {"apikey": CHEMSPIDER_API_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        csid = res.json()["results"][0]
        details_url = f"https://api.rsc.org/compounds/v1/records/{csid}/details"
        res2 = requests.get(details_url, headers=headers, timeout=10)
        res2.raise_for_status()
        props = res2.json().get("properties", [])
        hazards = [p["value"] for p in props if "hazard" in p["name"].lower()]
        return "\n".join(hazards) if hazards else "No hazard info found"
    except Exception as e:
        print(f"⚠️ ChemSpider hazard lookup failed: {e}")
        return "Hazard lookup failed"

# === SAVE TO DB ===
def save_to_database(info):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print(f"💾 Saving info to DB: {info}")  # DEBUG print
    try:
        cursor.execute('''
            SELECT id, quantity FROM Chemicals WHERE cas_number = ? OR (cas_number IS NULL AND name = ?)
        ''', (info['cas_number'], info['name']))
        row = cursor.fetchone()

        if row:
            new_quantity = row[1] + info.get('quantity', 1)
            cursor.execute('''
                UPDATE Chemicals
                SET quantity = ?, hazards = ?, location = ?
                WHERE id = ?
            ''', (new_quantity, info.get('hazards'), info.get('location'), row[0]))
            print(f"🔄 Updated existing chemical with id {row[0]}")
        else:
            cursor.execute('''
                INSERT INTO Chemicals (name, cas_number, formula, inchikey, hazards, location, quantity, safety_info_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                info.get("name"),
                info.get("cas_number"),
                info.get("formula"),
                info.get("inchikey"),
                info.get("hazards"),
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


# === PROMPT USER FOR MANUAL ENTRY ===
def manual_entry(fallback_name):
    print(f"\n⚠️ No CAS number found for '{fallback_name}'.")
    name = input(f"Enter chemical/product name [{fallback_name}]: ").strip() or fallback_name
    hazards = input("Enter hazards info (optional): ").strip()

    return {
        "name": name,
        "cas_number": None,
        "formula": None,
        "inchikey": None,
        "hazards": hazards if hazards else None,
        "location": None,
        "quantity": 1,
        "safety_info_url": None
    }

# === PROCESS IMAGE ===
def process_image(image_path, location):
    print(f"🔍 Processing {os.path.basename(image_path)}...")
    cas = extract_cas_number_from_image(image_path)  # use EasyOCR-based scanning

    fallback_name = os.path.splitext(os.path.basename(image_path))[0]

    if cas:
        chemical_info = {
            "cas_number": cas,
            "location": location,
            "quantity": 1,
            "hazards": None,
            "name": fallback_name,
            "formula": None,
            "inchikey": None,
            "safety_info_url": None
        }
        enriched = fetch_pubchem_data(cas=cas)
        if not enriched:
            enriched = fetch_pubchem_data(name=fallback_name)
        chemical_info.update({k: v for k, v in enriched.items() if v})

        inchikey = chemical_info.get("inchikey")
        if inchikey:
            hazards_pubchem = get_pubchem_hazards(inchikey)
            if hazards_pubchem:
                chemical_info["hazards"] = hazards_pubchem
            else:
                filter_id = get_chemspider_id(inchikey)
                if filter_id:
                    chemical_info["hazards"] = get_hazard_info_chemspider(filter_id)
                else:
                    chemical_info["hazards"] = "No hazard info found"
        else:
            chemical_info["hazards"] = "No hazard info found"

    else:
        manual_info = manual_entry(fallback_name)
        manual_info["location"] = location
        chemical_info = manual_info

    save_to_database(chemical_info)
    print("✅ Done.")

# === PUBCHEM HAZARD LOOKUP ===
def get_pubchem_hazards(inchikey):
    if not inchikey:
        return None
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{inchikey}/JSON/"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        hazards_list = []
        sections = data.get("Record", {}).get("Section", [])
        for section in sections:
            if section.get("TOCHeading", "").lower() in ("safety and hazards", "hazards"):
                for subsection in section.get("Section", []):
                    if subsection.get("TOCHeading", "").lower() in ("ghs hazard codes", "hazard statements"):
                        for info in subsection.get("Information", []):
                            if "Value" in info and "StringWithMarkup" in info["Value"]:
                                for item in info["Value"]["StringWithMarkup"]:
                                    hazards_list.append(item.get("String", ""))
                    for subsub in subsection.get("Section", []):
                        for info in subsub.get("Information", []):
                            if "Value" in info and "StringWithMarkup" in info["Value"]:
                                for item in info["Value"]["StringWithMarkup"]:
                                    hazards_list.append(item.get("String", ""))

        if hazards_list:
            return "\n".join(sorted(set(hazards_list)))
        else:
            return None
    except Exception as e:
        print(f"⚠️ PubChem hazard lookup failed for {inchikey}: {e}")
        return None

# === MAIN BATCH RUNNER ===
def process_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        location = os.path.basename(root)
        for fname in files:
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                fpath = os.path.join(root, fname)
                process_image(fpath, location)

if __name__ == "__main__":
    create_database()
    folder = input("Enter path to root folder of chemical images: ").strip()
    if os.path.isdir(folder):
        process_folder(folder)
    else:
        print("❌ Folder not found.")
