import mss
import mss.tools

# Vos coordonnées
x1, y1 = 3745, 215
x2, y2 = 3970, 821

# Définition de la région
monitor = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

with mss.mss() as sct:
    # Capture de la zone
    screenshot = sct.grab(monitor)
    
    # Sauvegarde
    mss.tools.to_png(screenshot.rgb, screenshot.size, output="data/input/capture_zone.png")

print("Capture effectuée avec succès sous Xorg !")