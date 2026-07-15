import pyautogui
import time

print("--- Suivi des coordonnées + couleur sous la souris ---")
print("Placez votre souris sur les points souhaités.")
print("Appuyez sur Ctrl+C dans ce terminal pour arrêter le script.\n")

try:
    while True:
        # Récupère la position actuelle
        x, y = pyautogui.position()
        try:
            r, g, b = pyautogui.pixel(x, y)
            color = f"RGB({r:3},{g:3},{b:3})"
        except Exception:
            color = "RGB(?,?,?)"
        # Affiche les coordonnées + couleur avec un retour chariot pour écraser la ligne précédente
        print(f"X: {x:4} | Y: {y:4} | {color}", end='\r')
        time.sleep(0.5)
except KeyboardInterrupt:
    print("\n--- Arrêt du suivi ---")