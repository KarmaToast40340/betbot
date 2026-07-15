import os

import numpy as np
import mss
import mss.tools

from config import CHECK_BUTTON_ROI, TURN_BUTTON_DEBUG_PATH

# Default thresholds for classifying the Check button's average color as
# "red" (hero's turn) vs "bluish" (not hero's turn). These are a starting
# guess, not calibrated against the real game — if detection misfires,
# sample the actual RGB values (ScreenScraper/misc/mouse_coords.py now
# prints the color under the cursor) in both states and adjust here, or
# override via the BETBOT_TURN_MIN_RED / BETBOT_TURN_RED_MARGIN env vars.
MIN_RED = float(os.environ.get("BETBOT_TURN_MIN_RED", "110"))
RED_MARGIN = float(os.environ.get("BETBOT_TURN_RED_MARGIN", "25"))
# Set BETBOT_TURN_DEBUG=1 to also print the sampled RGB every tick — off by
# default to avoid spamming logs once this is working.
DEBUG = os.environ.get("BETBOT_TURN_DEBUG", "0") == "1"


def sample_button_color(monitor=None):
    monitor = monitor or CHECK_BUTTON_ROI
    with mss.mss(display=":0.0") as sct:
        shot = sct.grab(monitor)
        # Always saved (cheap, tiny crop) so the ROI position can be
        # eyeballed directly — data/input/capture_zone.png has no visibility
        # into this separate zone otherwise.
        mss.tools.to_png(shot.rgb, shot.size, output=str(TURN_BUTTON_DEBUG_PATH))
        arr = np.array(shot)  # BGRA, shape (h, w, 4)
    b, g, r = arr[:, :, 0].mean(), arr[:, :, 1].mean(), arr[:, :, 2].mean()
    if DEBUG:
        print(f"[turn_detector] sampled RGB=({r:.0f},{g:.0f},{b:.0f})")
    return float(r), float(g), float(b)


def is_hero_turn(rgb=None):
    if rgb is None:
        rgb = sample_button_color()
    r, g, b = rgb
    return r >= MIN_RED and (r - b) >= RED_MARGIN
