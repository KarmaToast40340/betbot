import logging
import os
from pathlib import Path

from paddleocr import PaddleOCRVL


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("BetbotPaddleOCR")


class ROIExtractor:
    def __init__(self):
        self.input_dir = Path(os.getenv("BETBOT_INPUT_DIR", "./data/input"))
        self.output_dir = Path(os.getenv("BETBOT_OUTPUT_DIR", "./data/output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.pipeline = PaddleOCRVL(
            pipeline_version="v1.6",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_layout_detection=True,
            layout_shape_mode="auto",
        )

    def parse(self, input_path: str | Path):
        input_path = str(input_path)
        logger.info("Analyse PaddleOCR-VL: %s", input_path)

        results = self.pipeline.predict(input=input_path)

        saved = []
        for res in results:
            res.print()
            res.save_to_json(save_path=self.output_dir)
            res.save_to_markdown(save_path=self.output_dir)
            saved.append(res)

        logger.info("Analyse terminée. Résultats enregistrés dans %s", self.output_dir)
        return saved

    def parse_default_inputs(self):
        if not self.input_dir.exists():
            raise FileNotFoundError(f"Dossier d'entrée introuvable: {self.input_dir}")

        logger.info("Scan du dossier d'entrée: %s", self.input_dir)
        return self.parse(self.input_dir)


if __name__ == "__main__":
    extractor = ROIExtractor()
    extractor.parse_default_inputs()