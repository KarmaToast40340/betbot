from pathlib import Path

from paddleocr import PaddleOCRVL

from config import SERVER_URL
from parser import parse_poker_ocr_text

pipeline = PaddleOCRVL(
    vl_rec_backend="vllm-server",
    vl_rec_server_url=SERVER_URL,
    use_ocr_for_image_block=True,
    format_block_content=True,
)


def extract_text_from_result(res):
    if hasattr(res, "to_json"):
        return str(res.to_json())
    return str(res)


def run_ocr_and_parse(image_path, output_dir):
    output = pipeline.predict(str(image_path))
    texts = []
    parsed_results = []

    for i, res in enumerate(output):
        json_path = output_dir / f"ocr_vl_{i:03d}.json"
        md_path = output_dir / f"ocr_vl_{i:03d}.md"

        if hasattr(res, "save_to_json"):
            res.save_to_json(save_path=str(json_path))

        if hasattr(res, "save_to_markdown"):
            res.save_to_markdown(save_path=str(md_path))

        result_text = extract_text_from_result(res)
        texts.append(result_text)
        parsed_results.append(parse_poker_ocr_text(result_text, Path(image_path)))

    return "\n\n".join(texts), parsed_results