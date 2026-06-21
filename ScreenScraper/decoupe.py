import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_onednn_fusion"] = "0"

import cv2
import numpy as np
from paddleocr import PaddleOCR
import re

# IMPORTANT: On utilise det_model_dir et rec_model_dir pour éviter 
# que PaddleX ne télécharge ses modèles complexes.
# On force un modèle OCR classique (v4) qui est beaucoup plus stable.
ocr = PaddleOCR(lang='en')

def traiter_et_analyser(image_path):
    img = cv2.imread(image_path)
    if img is None: return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Masque de découpe (votre méthode)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 15, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    row_sums = np.sum(dilated, axis=1)
    
    threshold_empty = np.max(row_sums) * 0.1
    blocks = []
    start = None
    for i, val in enumerate(row_sums):
        if val > threshold_empty and start is None: start = i
        elif val <= threshold_empty and start is not None:
            if (i - start) > 5: blocks.append((start, i))
            start = None

    for i, (y1, y2) in enumerate(blocks):
        roi = img[max(0, y1-2):min(img.shape[0], y2+2), :]
        
        # CHANGEMENT ICI: Utiliser ocr.ocr() au lieu de ocr.predict()
        # ocr.ocr() appelle le moteur léger classique
        result = ocr.predict(roi)
        
        if result and result[0]:
            # Accès aux résultats pour PaddleOCR classique
            line_text = " ".join([line[1][0] for line in result[0]])
            print(f"Ligne {i}: {line_text}")
            
            if "Bets" in line_text or "Calls" in line_text:
                montant = re.search(r'(\d+)\s+BB', line_text)
                if montant:
                    print(f" -> Action détectée : {montant.group(1)} BB")

traiter_et_analyser("data/input/capture_zone.png")