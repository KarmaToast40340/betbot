FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLAGS_use_mkldnn=0 \
    FLAGS_enable_onednn_fusion=0

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /workspace/requirements.txt
RUN pip install --upgrade pip && pip install -r /workspace/requirements.txt

RUN python -m pip install -U "paddleocr[doc-parser]" safetensors

RUN python - <<'PY'
from pathlib import Path
base = Path("/usr/local/lib/python3.11/site-packages/paddlex/inference/pipelines/components/retriever/base.py")
txt = base.read_text()
txt = txt.replace(
    "from langchain.docstore.document import Document",
    "from langchain_core.documents import Document"
)
txt = txt.replace(
    "from langchain.text_splitter import RecursiveCharacterTextSplitter",
    "from langchain_text_splitters.character import RecursiveCharacterTextSplitter"
)
base.write_text(txt)
print(f"Patched: {base}")
PY

COPY . /workspace

CMD ["python", "/workspace/ScreenScraper/roi_extractor.py"]