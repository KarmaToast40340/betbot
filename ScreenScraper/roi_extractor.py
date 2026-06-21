import os
from pathlib import Path

import cv2
from paddleocr import PaddleOCRVL


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
INPUT_PATH = DATA_DIR / "input" / "capture_zone.png"
OUTPUT_DIR = DATA_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SERVER_URL = os.environ.get(
    "PADDLEOCR_VL_SERVER_URL",
    "http://host.docker.internal:8118/v1"
)

pipeline = PaddleOCRVL(
    vl_rec_backend="vllm-server",
    vl_rec_server_url=SERVER_URL,
)


def traiter_et_analyser(image_path: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Image introuvable : {image_path}")
        return

    print(f"Projet      : {PROJECT_ROOT}")
    print(f"Image input : {INPUT_PATH}")
    print(f"Output dir  : {OUTPUT_DIR}")
    print(f"Server URL  : {SERVER_URL}")

    output = pipeline.predict(str(image_path))

    txt_lines = []

    for i, res in enumerate(output):
        print(f"\n=== Résultat {i} ===")

        json_path = OUTPUT_DIR / f"ocr_vl_{i:03d}.json"
        md_path = OUTPUT_DIR / f"ocr_vl_{i:03d}.md"

        if hasattr(res, "save_to_json"):
            res.save_to_json(save_path=str(json_path))
            print(f"JSON écrit     : {json_path}")
            txt_lines.append(f"JSON: {json_path}")

        if hasattr(res, "save_to_markdown"):
            res.save_to_markdown(save_path=str(md_path))
            print(f"Markdown écrit : {md_path}")
            txt_lines.append(f"Markdown: {md_path}")

        if hasattr(res, "to_json"):
            result_text = str(res.to_json())
        else:
            result_text = str(res)

        print(result_text)
        txt_lines.append(result_text)
        txt_lines.append("")

    txt_path = OUTPUT_DIR / "ocr_vl_result.txt"
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")
    print(f"\nTXT écrit : {txt_path}")


if __name__ == "__main__":
    traiter_et_analyser(INPUT_PATH)