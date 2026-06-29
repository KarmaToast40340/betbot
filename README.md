# README debug BetBot OCR / vLLM

Ce document résume les deux problèmes principaux rencontrés sur le projet BetBot : l'accès X11 depuis le conteneur `screenscraper` et l'erreur `max_tokens=4096` envoyée à vLLM par PaddleOCR-VL.[1][2]

## Problème X11

Le symptôme typique était : `Authorization required, but no authorization protocol specified` suivi de `mss.exception.ScreenShotError: Unable to open display: b':0.0'`. Cela indique un problème d'autorisation X11, pas un problème OCR ni un bug `mss` pur.[3][4]

### Cause

Le conteneur Docker avait accès au socket `/tmp/.X11-unix`, mais pas au cookie d'authentification X11, ou bien `DISPLAY` / `XAUTHORITY` n'étaient pas correctement passés. Les environnements lancés via `sudo` perdent souvent `XAUTHORITY`, ce qui casse l'accès au serveur X.[5][1]

### Correction retenue

Dans `docker-compose.yml`, la section `screenscraper` doit inclure :

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

Le montage du socket X11, du fichier `.Xauthority`, et l'export explicite de `DISPLAY` sont une configuration standard pour faire tourner des applications GUI/X11 dans Docker.[1][6]

### Commandes utiles côté hôte

Avant relance, autoriser l'accès X11 :

```bash
xhost +si:localuser:root
```

Ou en version plus large :

```bash
xhost +local:
```

Ces commandes donnent l'accès au serveur X aux processus locaux, dont le conteneur Docker, ce qui règle souvent l'erreur d'autorisation X11.[7][8]

### Vérification

Après relance :

```bash
sudo docker exec -it betbot-screenscraper bash -lc 'echo $DISPLAY; echo $XAUTHORITY; ls -l /root/.Xauthority; xrandr'
```

Si `xrandr` fonctionne dans le conteneur, l'accès au display X11 est normalement rétabli.[1][6]

## Problème vLLM / max_tokens

Le symptôme était une erreur 400 depuis le backend vLLM : `max_tokens or max_completion_tokens is too large: 4096`, avec un message indiquant que le modèle a un `maximum context length` de 2048 ou 4096 selon la configuration du serveur.[2][9]

### Cause

Le problème ne venait pas directement de la config YAML vLLM (`max-model-len`, `gpu-memory-utilization`, etc.), mais d'une valeur par défaut dans PaddleX. Le code local contenait `vlm_kwargs["max_new_tokens"] = 4096` dans `paddlex/inference/pipelines/paddleocr_vl/pipeline.py`, puis cette valeur était convertie en `max_tokens` ou `max_completion_tokens` avant l'appel au serveur vLLM.[9][10]

### Pourquoi 4096 était un problème

Dans vLLM, la règle est : `tokens d'entrée + tokens générés <= max_model_len`. Donc avec `max_model_len=2048`, une requête qui demande `max_tokens=4096` est toujours invalide. Même avec `max_model_len=4096`, `max_tokens=4096` reste invalide dès qu'il y a le moindre token d'entrée.[9][11]

### Lignes trouvées

Les recherches dans le venv local ont montré les points importants suivants :

```text
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/models/doc_vlm/predictor.py:514:            request_kwargs[max_tokens_name] = max_new_tokens
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/models/doc_vlm/predictor.py:516:            request_kwargs[max_tokens_name] = PADDLEOCR_VL_MAX_NEW_TOKENS
/home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/pipelines/paddleocr_vl/pipeline.py:505:            vlm_kwargs["max_new_tokens"] = 4096
```

Ces lignes montrent que `pipeline.py` fixe 4096, puis `predictor.py` envoie cette valeur au backend OpenAI-compatible de vLLM.[9][10]

### Correction retenue

Patch local du fichier :

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

Cette correction force une génération courte et cohérente avec un usage OCR poker, au lieu de demander toute la fenêtre de contexte en sortie.[9][10]

### Vérification après patch

```bash
grep -n "max_new_tokens" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex/inference/pipelines/paddleocr_vl/pipeline.py
```

La sortie attendue doit montrer :

```python
vlm_kwargs["max_new_tokens"] = 256
```

Une petite valeur comme 256 ou 512 est bien plus adaptée à l'extraction OCR que 4096.[9][10]

## Configuration vLLM testée

Configuration côté serveur utilisée pendant le debug :

```yaml
gpu-memory-utilization: 0.6
max-model-len: 2048
max-num-batched-tokens: 1024
max-num-seqs: 1
```

Cette configuration réduit la pression mémoire et le KV cache, mais elle ne résout pas à elle seule un `max_tokens=4096` envoyé par le client PaddleOCR-VL.[12][13]

## Ce qu'il faut retenir

- Le problème X11 est un problème de socket/cookie/authentification, corrigé via `DISPLAY`, `XAUTHORITY`, montage `.Xauthority` et `xhost`.[4][1]
- Le problème `max_tokens=4096` vient d'un défaut PaddleX local, pas directement de `max-model-len` dans la config vLLM.[9][10]
- Augmenter `max_model_len` sans corriger `max_new_tokens` ne suffit pas, car vLLM vérifie toujours que `input + output` tienne dans la fenêtre totale.[9][11]

## Commandes de rappel

Recherche des chemins Python :

```bash
python - <<'PY'
import sys, os, paddleocr, paddlex
print(sys.version)
print("paddleocr =", os.path.dirname(paddleocr.__file__))
print("paddlex   =", os.path.dirname(paddlex.__file__))
PY
```

Recherche de la valeur fautive :

```bash
grep -Rni "max_tokens" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddleocr /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex
grep -Rni "4096" /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddleocr /home/karma/Documents/betbot/env/lib/python3.12/site-packages/paddlex
```

Relance Docker :

```bash
sudo -E docker compose down
sudo -E docker compose up --build -d
```

Test X11 dans le conteneur :

```bash
sudo docker exec -it betbot-screenscraper bash -lc 'echo $DISPLAY; echo $XAUTHORITY; ls -l /root/.Xauthority; xrandr'
```