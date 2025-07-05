import os
import re
import sqlite3
import cv2
from PIL import Image
import pytesseract
import requests
import time

DB_PATH = "lab_inventory.db"
CHEMSPIDER_API_KEY = "xduPDRiOrYasBMYJbmIEf4d9i90J2B3G2585r1tk"  # <-- Put your ChemSpider API key here

# ---------- DB Setup ----------

def create_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cas_number TEXT,
            formula TEXT,
            inchikey TEXT,
            hazards TEXT,
            location TEXT,
            quantity INTEGER,
            safety_info_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ---------- Image + OCR ----------

def extract_text(image_path):
    try:
        img = Image.open(image_path).convert("RGB")
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        return text
    except Exception as e:
        print(f"Error reading image {image_path}: {e}")
        return ""

def extract_cas_number(text):
    text = text.replace('_', '-').replace('.', '-').replace(' ', '-')
    cas_regex = r'(?i)cas\s*#?\s*(\d{1,7}[-–—]\d{1,2}[-–—]\d)'
    matches = re.findall(cas_regex, text)
    if matches:
        return matches[0]
    cas_regex_simple = r'\b\d{1,7}[-–—]\d{1,2}[-–—]\d\b'
    match = re.findall(cas_regex_simple, text)
    if matches:
        return match[0]
    return None

def extract_name(text):
    lines = text.strip().splitlines()
    for line in lines:
        if len(line.strip()) > 3:
            return line.strip()
    return None

# ---------- ChemSpider Lookup ----------

BASE_CS_URL = "https://api.rsc.org/compounds/v1"

def get_chemspider_id(inchikey=None, name=None, cas=None):
    headers = {
        'apikey': CHEMSPIDER_API_KEY,
        'Content-Type': 'application/json'
    }

    # Priority: InChIKey > CAS > Name
    if inchikey:
        data = {"inchikey": inchikey}
        endpoint = "/filter/inchikey"
    elif cas:
        data = {"rn": cas}
        endpoint = "/filter/rn"
    elif name:
        data = {"name": name}
        endpoint = "/filter/name"
    else:
        return None

    response = requests.post(BASE_CS_URL + endpoint, headers=headers, json=data)
    if response.status_code != 200:
        return None

    query_id = response.json().get("queryId")
    if not query_id:
        return None

    # Poll until complete
    for _ in range(10):
        status = requests.get(f"{BASE_CS_URL}/filter/{query_id}/status", headers=headers).json()
        if status["status"] == "Complete":
            break
        time.sleep(1)

    results = requests.get(f"{BASE_CS_URL}/filter/{query_id}/results", headers=headers).json()
    csids = results.get("results", [])
    return csids[0] if csids else None

def get_chemical_details(csid):
    headers = {'apikey': CHEMSPIDER_API_KEY}
    url = f"{BASE_CS_URL}/records/{csid}/details"
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        props = {p["name"]: p["value"] for p in data.get("properties", [])}
        return {
            "name": data.get("commonName") or data.get("preferredIUPACName"),
            "formula": props.get("Molecular Formula"),
            "inchikey": props.get("InChIKey"),
            "hazards": "\n".join(
                f"{k}: {v}" for k, v in props.items()
                if any(x in k.lower() for x in ["hazard", "safety", "risk"])
            ),
            "safety_url": data.get("externalDataSources", [{}])[0].get("externalUrl")
        }
    except Exception as e:
        print(f"⚠️ ChemSpider detail lookup failed for CSID {csid}: {e}")
        return {}

# ---------- Save to DB ----------

def save_to_database(info):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO Chemicals (name, cas_number, formula, inchikey, hazards, location, quantity, safety_info_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.commit()
    conn.close()

# ---------- Batch Processor ----------

def process_image(image_path, location):
    print(f"\n📷 Processing {os.path.basename(image_path)}...")

    text = extract_text(image_path)
    cas = extract_cas_number(text)
    name = extract_name(text)

    csid = get_chemspider_id(cas=cas) or get_chemspider_id(name=name)
    if not csid:
        print("❌ ChemSpider ID not found.")
        return

    chem_info = get_chemical_details(csid)
    if not chem_info:
        print("❌ Chemical info lookup failed.")
        return

    info = {
        "name": chem_info.get("name") or name,
        "cas_number": cas,
        "formula": chem_info.get("formula"),
        "inchikey": chem_info.get("inchikey"),
        "hazards": chem_info.get("hazards"),
        "safety_info_url": chem_info.get("safety_url"),
        "location": location,
        "quantity": 1,
    }

    save_to_database(info)
    print(f"✅ Saved {info['name']} to database.")

def process_folder_batch(base_folder):
    for root, _, files in os.walk(base_folder):
        location = os.path.basename(root)
        images = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        for image_file in images:
            img_processed = preprocess_grayscale_contrast(image_file, location, alpha=2.0, beta=10)
            process_image(os.path.join(root, image_file), location)

def preprocess_grayscale_contrast(image_path, alpha, beta):
    """
    alpha: contrast control (1.0-3.0)
    beta: brightness control (0-100)
    """
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    return adjusted


# ---------- Main ----------

if __name__ == "__main__":
    create_database()
    base_folder = input("Enter path to folder containing location subfolders: ").strip()
    process_folder_batch(base_folder)








def process_image(image_path):
    print(f"\nProcessing {os.path.basename(image_path)}...")
    img_processed = preprocess_grayscale_contrast(image_path, alpha=2.0, beta=10)
    text = pytesseract.image_to_string(img_processed, config='--oem 3 --psm 6')
    print(text)
    cas = extract_cas_number(text)
    if not cas:
        print(f"  CAS number not found, skipping.")
        return False

    print(f"  Found CAS: {cas}")

