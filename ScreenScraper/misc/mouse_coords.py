import time
import pyautogui

print("Suivi souris en direct. Ctrl+C pour quitter.")

try:
    while True:
        x, y = pyautogui.position()
        print(f"\rX: {x:4d}  Y: {y:4d}", end="", flush=True)
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nArrêt.")