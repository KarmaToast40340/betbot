# BetBot OCR / vLLM Debug README

This document summarizes the two main issues encountered on the BetBot project: access to X11 from the `screenscraper` container and the `max_tokens=4096` error sent to vLLM by PaddleOCR-VL.

## X11 issue

The typical symptom was: `Authorization required, but no authorization protocol specified` followed by `mss.exception.ScreenShotError: Unable to open display: b':0.0'`. This indicates a problem with X11 authentication or DISPLAY configuration.

### Cause

The Docker container had access to the `/tmp/.X11-unix` socket, but not to the X11 authentication cookie, or `DISPLAY` / `XAUTHORITY` were not passed correctly. This is common in Linux environments where GUI applications are launched inside containers.

### Fix applied

In `docker-compose.yml`, the `screenscraper` section must include:

```yaml
screenscraper:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: betbot-screenscraper
  working_dir: /workspace
  network_mode: host
  volumes:
    - ./:/workspace
    - /tmp/.X11-unix:/tmp/.X11-unix:rw
    - ${XAUTHORITY:-$HOME/.Xauthority}:/root/.Xauthority:ro
  environment:
    DISPLAY: ":0"
    XAUTHORITY: "/root/.Xauthority"
    PYTHONUNBUFFERED: "1"
    BETBOT_INPUT_DIR: "/workspace/data/input"
    BETBOT_OUTPUT_DIR: "/workspace/data/output"
    FLAGS_use_mkldnn: "0"
    FLAGS_enable_onednn_fusion: "0"
    PADDLEOCR_VL_SERVER_URL: "http://127.0.0.1:8118/v1"
  command: python /workspace/ScreenScraper/main.py
  restart: "no"
  depends_on:
    - paddleocr-vlm-server
```

Mounting the X11 socket, the `.Xauthority` file, and explicitly exporting `DISPLAY` is the standard setup for GUI/X11 applications inside Docker.[1][6]

### Useful host-side commands

Before restarting, allow X11 access:

```bash
xhost +si:localuser:root
```

Or in a broader form:

```bash
xhost +local:
```

These commands grant local processes access to the X server, including Docker containers, which often resolves the X11 authorization error.[7][8]

### Verification

After restarting:

```bash
sudo docker exec -it betbot-screenscraper bash -lc 'echo $DISPLAY; echo $XAUTHORITY; ls -l /root/.Xauthority; xrandr'
```

If `xrandr` works inside the container, the X11 display access is usually restored.[1][6]

## vLLM / max_tokens issue

The symptom was a 400 error from the vLLM backend: `max_tokens or max_completion_tokens is too large: 4096`, with a message indicating that the model has a `maximum context length` of 2048.

### Cause

The problem was not directly due to the vLLM YAML configuration (`max-model-len`, `gpu-memory-utilization`, etc.), but to a default value in PaddleX. The local code contained `vlm_kwargs["max_new_tokens"] = 4096`.

### Why 4096 was a problem

In vLLM, the rule is: `input tokens + generated tokens <= max_model_len`. So with `max_model_len=2048`, a request asking for `max_tokens=4096` is always invalid. Even if `max_model_len` is increased, the request remains invalid if the sum exceeds the context window.

### Relevant lines found

Searching the local venv showed the following key locations:

```text
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/models/doc_vlm/predictor.py:514:            request_kwargs[max_tokens_name] = max_new_tokens
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/models/doc_vlm/predictor.py:516:            request_kwargs[max_tokens_name] = PADDLEOCR_VL_MAX_NEW_TOKENS
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/pipelines/paddleocr_vl/pipeline.py:505:            vlm_kwargs["max_new_tokens"] = 4096
```

These lines show that `pipeline.py` sets 4096, and then `predictor.py` sends that value to the OpenAI-compatible vLLM backend.[9][10]

### Fix applied

Local patch of the file:

```bash
python - <<'PY'
from pathlib import Path

p = Path("/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/pipelines/paddleocr_vl/pipeline.py")
txt = p.read_text(encoding="utf-8")
txt = txt.replace('vlm_kwargs["max_new_tokens"] = 4096', 'vlm_kwargs["max_new_tokens"] = 256')
p.write_text(txt, encoding="utf-8")
print("ok")
PY
```

This forces a shorter generation aligned with poker OCR usage instead of asking the model to generate the whole context window.[9][10]

### Verification after the patch

```bash
grep -n "max_new_tokens" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/pipelines/paddleocr_vl/pipeline.py
```

The expected output should be:

```python
vlm_kwargs["max_new_tokens"] = 256
```

A smaller value such as 256 or 512 is far more suitable for OCR extraction than 4096.[9][10]

## Tested vLLM configuration

Server-side configuration used during debugging:

```yaml
gpu-memory-utilization: 0.6
max-model-len: 2048
max-num-batched-tokens: 1024
max-num-seqs: 1
```

This reduces memory pressure and KV cache usage, but it does not by itself solve a `max_tokens=4096` request sent by the PaddleOCR-VL client.[12][13]

## Takeaways

- The X11 issue is a socket/authentication problem and is fixed via `DISPLAY`, `XAUTHORITY`, `.Xauthority` mounting, and `xhost`.[4][1]
- The `max_tokens=4096` problem comes from a local PaddleX bug, not directly from `max-model-len` in the vLLM config.[9][10]
- Increasing `max_model_len` alone is not enough; `max_new_tokens` must also be corrected because vLLM always validates that `input + output` fits inside the total context window.[9][11]

## Quick commands

Find the Python paths:

```bash
python - <<'PY'
import sys, os, paddleocr, paddlex
print(sys.version)
print("paddleocr =", os.path.dirname(paddleocr.__file__))
print("paddlex   =", os.path.dirname(paddlex.__file__))
PY
```

Search for the bad value:

```bash
grep -Rni "max_tokens" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddleocr /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex
grep -Rni "4096" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddleocr /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex
```

Restart Docker:

```bash
sudo -E docker compose down
sudo -E docker compose up --build -d
```

Test X11 inside the container:

```bash
sudo docker exec -it betbot-screenscraper bash -lc 'echo $DISPLAY; echo $XAUTHORITY; ls -l /root/.Xauthority; xrandr'
```

```
# 1. Stop everything cleanly (in case old containers are still running with stale code)
sudo docker compose --profile serve down

# 2. Restart everything in the background: paddleocr-vlm-server + screenscraper + agent-serve
sudo docker compose --profile serve up -d

# 3. Check that all 3 are running (not "Exited")
sudo docker compose --profile serve ps

# 4. In a dedicated terminal, follow only the predictions
sudo docker compose --profile serve logs -f agent-serve
```

```
sudo docker compose --profile serve exec agent-serve touch /workspace/data/output/start_serving.flag
```

