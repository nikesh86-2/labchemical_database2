import cv2
import pytesseract

def preprocess_grayscale_contrast(image_path, alpha=1.0, beta=0):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    return adjusted

def try_contrast_brightness_combos(image_path):
    alphas = [1.0, 1.5, 2.0, 2.5, 3.0]       # contrast values
    betas = [-20, -10, 0, 10, 20]            # brightness values

    for alpha in alphas:
        for beta in betas:
            img_processed = preprocess_grayscale_contrast(image_path, alpha=alpha, beta=beta)
            text = pytesseract.image_to_string(img_processed, config='--oem 3 --psm 6', lang='eng')
            print(f"--- alpha={alpha}, beta={beta} ---")
            print(text.strip() or "[No text detected]")
            print("\n" + "-"*40 + "\n")

# Example usage:
image_path = '/home/nike/Downloads/PXL_20250702_122403638.jpg'
try_contrast_brightness_combos(image_path)