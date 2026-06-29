from pathlib import Path

import cv2
import mss
import mss.tools

from config import INPUT_PATH, MONITOR


def capture_region_to_png(path: Path = INPUT_PATH):
    with mss.mss(display=":0.0") as sct:
        screenshot = sct.grab(MONITOR)
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(path))
    return cv2.imread(str(path))
