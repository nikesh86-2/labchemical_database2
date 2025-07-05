import cv2
import pytesseract
import easyocr

# Initialize EasyOCR once
reader = easyocr.Reader(['en'])

def preprocess_image(image_path):
    # Read and convert to grayscale for consistency
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray

def ocr_pytesseract(image):
    try:
        # Use config for single block of text
        text = pytesseract.image_to_string(image, config='--oem 3 --psm 6')
        return text.strip()
    except Exception as e:
        return f"Error: {e}"

def ocr_easyocr(image_path):
    try:
        results = reader.readtext(image_path)
        # Concatenate all recognized text parts
        text = ' '.join([res[1] for res in results])
        return text.strip()
    except Exception as e:
        return f"Error: {e}"

def compare_ocr(image_path):
    img = preprocess_image(image_path)

    text_tesseract = ocr_pytesseract(img)
    text_easyocr = ocr_easyocr(image_path)

    print(f"\n--- OCR Comparison for {image_path} ---")
    print("\n[pytesseract output]:")
    print(text_tesseract or "[No text detected]")
    print("\n[EasyOCR output]:")
    print(text_easyocr or "[No text detected]")
    print("-" * 50)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr_compare.py image1.jpg [image2.png ...]")
        sys.exit(1)

    for image_file in sys.argv[1:]:
        compare_ocr(image_file)