from PIL import Image, ImageEnhance
import easyocr
import pubchempy as pcp
import numpy as np
import re
import webbrowser
import urllib.parse


reader = easyocr.Reader(['en'], gpu=True)  # optical character recognition system

# compiled patterns for reuse
CAS_PATTERN = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")
CATALOG_PATTERN = re.compile(
    r"\b(?:Catalog|Catalogue|Cat(?:\.|alog(?:ue)?)?)?\s*(?:No\.?|Number)?\s*[:#]?\s*([A-Z]?\d{4,}[A-Z]?)\b",
    re.IGNORECASE
)


# ====EXTRACTION SNIPPET====#
def extract_text_from_image(image_path):
    """
    enhance image using alpha and beta (contrast + brightness)
    and use that to extract text block
    """
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"Could not open image {image_path}: {e}")
        return ""

    best_text = ""
    best_score = 0
    for contrast in [0.8, 1.0, 1.5, 2.0]:
        enhancer = ImageEnhance.Contrast(image)
        enhanced_image = enhancer.enhance(contrast)

        # Convert PIL image to numpy array (RGB to BGR for OpenCV if needed)
        img_np = np.array(enhanced_image)
        # EasyOCR expects RGB or grayscale, so no need to convert color order
        try:
            text_results = reader.readtext(img_np)
        except Exception as e:
            print(f"OCR error for {image_path} at contrast {contrast}: {e}")
            continue

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
            data["name"] = comp.iupac_name or (comp.synonyms[0] if comp.synonyms else "")
            data["iupac_name"] = comp.iupac_name
          #  print("IUPAC Name:", comp.iupac_name)
            data["common_name"] = comp.synonyms[0] if comp.synonyms else None
            data["formula"] = comp.molecular_formula
            data["safety_info_url"] = f"https://pubchem.ncbi.nlm.nih.gov/compound/{comp.cid}"
            #print(f"CID: {comp.cid}")
    except Exception as e:
        print(f"PubChem lookup failed for CAS {cas}: {e}")
    return data

def parse_chemical_info(text, open_browser=False):
    """Extract basic fields from a block of OCR text.

    The optional ``open_browser`` flag controls whether a Google search is
    launched when no CAS number was found.  The GUI code passes ``False`` so
    that callers can handle navigation themselves.
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

    # Try to extract CAS Number
    cas_match = CAS_PATTERN.search(text)
    if cas_match:
        data["cas_number"] = cas_match.group(1)

    # Catalog Number
    catalog_match = CATALOG_PATTERN.search(text)
    if catalog_match:
        data["catalog_number"] = catalog_match.group(1).strip()

    if open_browser and not data.get("cas_number") and data.get("catalog_number"):
        url = f"https://www.google.com/search?q={urllib.parse.quote(str(data['catalog_number']))}"
        webbrowser.open(url)

    return enrich_with_pubchem(data)