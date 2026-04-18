# 🎰 Guide Complet d'Exécution - PokerBench Training

## 📋 Table des Matières

1. [Préparation](#préparation)
2. [Étape 1: Exploration du Dataset](#étape-1-exploration-du-dataset)
3. [Étape 2: Entraînement](#étape-2-entraînement)
4. [Étape 3: Évaluation](#étape-3-évaluation)
5. [Étape 4: Prédictions](#étape-4-prédictions)

---

## 🔧 Préparation

### Installation initiale

```bash
cd /home/karma/Documents/Pers/betbot

# Installer les dépendances
pip install -r requirements.txt

# (Optionnel) Activer l'accélération GPU pour PyTorch
# Pour NVIDIA CUDA:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Pour AMD ROCm:
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

### Vérifier l'installation

```bash
python3 -c "
import torch
import transformers
import datasets

print(f'✅ PyTorch: {torch.__version__}')
print(f'✅ Transformers: {transformers.__version__}')
print(f'✅ Datasets: {datasets.__version__}')
print(f'✅ GPU disponible: {torch.cuda.is_available()}')
"
```

---

## 📊 Étape 1: Exploration du Dataset

Avant d'entraîner, explorez la structure du dataset.

### Commande

```bash
python3 explore_dataset.py
```

### Résultat attendu

```
🔍 Analyse du Dataset PokerBench
============================================================

📥 Chargement du dataset...

============================================================
📊 SPLIT: preflop_train
============================================================
Nombre d'exemples: 60,000
Colonnes: ['instruction', 'output']

📌 output - Distributions:
   fold: 30,487 (50.8%)
   call: 18,392 (30.7%)
   raise: 10,121 (16.9%)
   check: 1,000 (1.7%)

📈 Statistiques des colonnes:
  • instruction:
    min_length: 150
    max_length: 500
    avg_length: 325
    unique_count: 60000

  • output:
    min_length: 4
    max_length: 20
    avg_length: 6
    unique_count: 4
```

### Fichiers générés

- `preflop_train_sample.json` : 100 exemples du dataset pre-flop
- `postflop_train_sample.json` : 100 exemples du dataset post-flop

---

## 🚀 Étape 2: Entraînement

### Commande simple (recommandée pour débuter)

```bash
python3 main.py
```

### Configuration personnalisée

Modifiez le dictionnaire `CONFIG` dans `main.py` :

```python
CONFIG = {
    "model_name": "distilgpt2",      # Changez le modèle ici
    "max_seq_length": 512,
    "batch_size": 8,                 # Réduisez si GPU out of memory
    "learning_rate": 2e-5,
    "num_epochs": 3,
    "output_dir": "./poker_model_output",
}
```

### Exemples d'exécution

**Option 1: Entraînement rapide (CPU, petite machine)**
```bash
# Modifiez main.py:
CONFIG = {
    "model_name": "distilgpt2",
    "batch_size": 4,
    "num_epochs": 1,
}
python3 main.py
```

**Option 2: Entraînement moyen (GPU standard)**
```bash
# Modifiez main.py:
CONFIG = {
    "model_name": "gpt2",
    "batch_size": 8,
    "num_epochs": 3,
}
python3 main.py
```

**Option 3: Haute qualité (GPU puissant)**
```bash
# Modifiez main.py:
CONFIG = {
    "model_name": "EleutherAI/gpt-neo-1.3B",
    "batch_size": 16,
    "num_epochs": 5,
    "learning_rate": 1e-5,
}
python3 main.py
```

### Monitoring l'entraînement

Pendant l'entraînement, visualisez les logs TensorBoard :

```bash
# Dans un nouveau terminal
tensorboard --logdir ./poker_model_output/logs

# Puis ouvrez: http://localhost:6006
```

### Troubleshooting d'entraînement

**Erreur: "CUDA out of memory"**
```python
CONFIG = {
    "batch_size": 4,  # Réduire de 8 à 4
    "max_seq_length": 256,  # Réduire de 512 à 256
}
```

**Erreur: "Connection timeout"**
```bash
# Vérifier la connexion internet
# Retry:
HF_DATASETS_OFFLINE=0 python3 main.py
```

---

## 📊 Étape 3: Évaluation

### Test sur le dataset

```bash
python3 evaluate_model.py ./poker_model_output/final_model evaluation
```

### Exécuter la démo

```bash
python3 evaluate_model.py ./poker_model_output/final_model demo
```

**Résultat attendu:**
```
[Scénario 1]
  Décision: fold

[Scénario 2]
  Décision: call

[Scénario 3]
  Décision: bet 50

[Scénario 4]
  Décision: call
```

---

## 🎯 Étape 4: Prédictions

### Mode Interactif

```bash
python3 evaluate_model.py ./poker_model_output/final_model interactive
```

**Exemple de session:**

```
🎰 MODE INTERACTIF - Prédictions de Poker

📝 Scénario: You are in the small blind with 7-7. 
The button folds, and the big blind pushes all-in for 50BB. 
You have 100BB.

✅ Décision optimale: call

📝 Scénario: You have KK on an AKQ flop. 
You bet 1/4 pot, and your opponent raises 3x. 
Stacks are 100BB.

✅ Décision optimale: raise

📝 Scénario: quit
```

### Traitement par lot

```bash
# Créer un fichier JSON avec des scénarios
cat > scenarios.json << 'EOF'
[
  {"instruction": "You are in UTG with AA..."},
  {"instruction": "You are on the button with 23o..."},
]
EOF

# Traiter
python3 evaluate_model.py ./poker_model_output/final_model batch scenarios.json

# Résultat dans: scenarios_predictions.json
```

---

## 📈 Cas d'Usage Avancés

### 1. Entraînement sur une partition spécifique

```python
# Dans explore_dataset.py, modifiez:
def load_poker_dataset():
    # Seulement post-flop
    ds = load_dataset("RZ412/PokerBench", split="postflop_train")
    return {"train": ds}
```

### 2. Fine-tuning sur vos propres données

```python
from datasets import Dataset

# Vos données personnelles
your_data = [
    {
        "instruction": "You are in CO with T9s...",
        "output": "fold"
    },
    # ... plus d'exemples
]

# Créer un dataset
custom_ds = Dataset.from_dict({
    "instruction": [ex["instruction"] for ex in your_data],
    "output": [ex["output"] for ex in your_data],
})

# Entraîner avec:
# trainer.train_dataset = custom_ds
```

### 3. Export et déploiement

```bash
# Exporter le modèle
python3 << 'EOF'
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = "./poker_model_output/final_model"
model = AutoModelForCausalLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

# Sauvegarder pour TensorFlow
model.save_pretrained(f"{model_path}_tf", saved_model=True)

# Sauvegarder pour ONNX
from optimum.onnxruntime import ORTModelForCausalLM
ort_model = ORTModelForCausalLM.from_pretrained(model_path, from_transformers=True)
ort_model.save_pretrained(f"{model_path}_onnx")
EOF
```

---

## 🎓 Résumé du Pipeline Complet

```bash
# 1. Préparation
pip install -r requirements.txt

# 2. Exploration
python3 explore_dataset.py

# 3. Entraînement (2-8 heures selon GPU)
python3 main.py

# 4. Évaluation
python3 evaluate_model.py ./poker_model_output/final_model demo

# 5. Utilisation
python3 evaluate_model.py ./poker_model_output/final_model interactive
```

---

## 📊 Métriques de Performance Attendues

| Modèle | Temps (GPU) | Accuracy | Perplexité |
|--------|------------|----------|-----------|
| distilgpt2 | 30 min | 68% | 2.5 |
| gpt2 | 1-2h | 72% | 2.1 |
| gpt-neo-1.3B | 4-6h | 78% | 1.8 |

---

## 🔍 Dépannage Avancé

### Vérifier l'utilisation GPU

```bash
nvidia-smi --loop=1
```

### Profiler l'entraînement

```python
from torch.profiler import profile, record_function, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    trainer.train()

print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=10))
```

### Sauvegarder le checkpoint et reprendre

```python
# Resume from checkpoint
trainer.train(resume_from_checkpoint="./poker_model_output/checkpoint-1000")
```

---

## ✅ Checklist Finale

- [ ] Dépendances installées
- [ ] Dataset exploré
- [ ] Modèle entraîné
- [ ] Évaluation complétée
- [ ] Prédictions testées
- [ ] Modèle sauvegardé

---

## 📞 Support & Ressources

- **Issues**: https://github.com/pokerllm/pokerbench/issues
- **Dataset**: https://huggingface.co/datasets/RZ412/PokerBench
- **Forum**: https://huggingface.co/spaces

Bonne chance avec votre entraînement! 🎲
