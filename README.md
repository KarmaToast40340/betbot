# 🎲 PokerBench Training - Guide Complet

Ce projet utilise le dataset **PokerBench** de Hugging Face pour entraîner une IA capable de prédire les meilleures décisions au poker (No Limit Texas Hold'em).

## 📊 Dataset PokerBench

Le dataset contient :
- **Pre-Flop**: 60,000 exemples d'entraînement + 1,000 exemples de test
- **Post-Flop**: 500,000 exemples d'entraînement + 10,000 exemples de test
- Format JSON avec `instruction` (scénario) et `output` (décision optimale)

### Structure des données

**Format JSON :**
```json
{
  "instruction": "You are a specialist in playing 6-handed No Limit Texas Holdem. The following will be a game scenario...",
  "output": "check"
}
```

**Décisions possibles :** check, fold, call, bet/raise (avec montants spécifiques)

## 🚀 Démarrage Rapide

### 1. Installation des dépendances

```bash
cd /home/karma/Documents/Pers/betbot
pip install -r requirements.txt
```

### 2. Entraîner le modèle

```bash
python main.py
```

Le script va :
1. ✅ Charger le dataset PokerBench
2. 📊 Explorer et afficher les statistiques
3. 🔄 Préparer les données pour l'entraînement
4. 📥 Charger un modèle pré-entraîné (distilgpt2 par défaut)
5. 🚀 Entraîner le modèle
6. 💾 Sauvegarder le modèle optimisé

### 3. Utiliser le modèle pour des prédictions

```bash
python main.py predict "You are playing UTG with KdKc at a 6-handed table..." "./poker_model_output/final_model"
```

## ⚙️ Configuration Personnalisée

Dans `main.py`, modifiez le dictionnaire `CONFIG` :

```python
CONFIG = {
    "dataset_name": "RZ412/PokerBench",
    "model_name": "distilgpt2",        # Autres options: "gpt2", "EleutherAI/gpt-neo-125m"
    "max_seq_length": 512,              # Longueur max des séquences
    "batch_size": 8,                    # Augmentez pour GPUs plus puissantes
    "learning_rate": 2e-5,
    "num_epochs": 3,                    # Nombre d'itérations
    "output_dir": "./poker_model_output",
}
```

## 🎯 Modèles Recommandés

| Modèle | Taille | Vitesse | Qualité | GPU Recommandée |
|--------|--------|---------|---------|-----------------|
| distilgpt2 | 82M | ⚡⚡⚡ | ⭐⭐ | CPU/GTX 1050 |
| gpt2 | 124M | ⚡⚡ | ⭐⭐⭐ | GTX 1080 / RTX 2060 |
| EleutherAI/gpt-neo-125m | 125M | ⚡⚡ | ⭐⭐ | CPU/GTX 1050 |
| EleutherAI/gpt-neo-1.3B | 1.3B | ⚡ | ⭐⭐⭐⭐ | RTX 3080+ |

## 💡 Cas d'Usage Avancés

### 1. Entraîner sur le dataset Pre-Flop uniquement

Modifiez `load_poker_dataset()` pour filtrer le dataset :

```python
def load_poker_dataset() -> Dict:
    ds = load_dataset("RZ412/PokerBench", split="preflop_train")
    return {"train": ds}
```

### 2. Fine-tuner sur des données spécifiques

```python
from datasets import Dataset

# Charger vos propres données
custom_data = [
    {"instruction": "...", "output": "call"},
    {"instruction": "...", "output": "fold"},
]
custom_dataset = Dataset.from_dict({
    "instruction": [ex["instruction"] for ex in custom_data],
    "output": [ex["output"] for ex in custom_data],
})
```

### 3. Optimiser pour l'inférence rapide

Utilisez la quantification :

```python
from transformers import AutoModelForCausalLM
import torch

model = AutoModelForCausalLM.from_pretrained("model_path")
# Quantifier en 8-bit pour réduire la mémoire
model_quantized = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
```

### 4. Évaluation du modèle

```python
def evaluate_model(trainer, test_dataset):
    results = trainer.evaluate(eval_dataset=test_dataset)
    print(f"Perplexity: {results['eval_loss']:.4f}")
    return results
```

## 📈 Monitoring et Logs

Les logs d'entraînement sont sauvegardés dans `./poker_model_output/` :
- `training_args.bin` : Arguments d'entraînement
- `events.out.tfevents.*` : Logs TensorBoard
- `checkpoint-*/` : Points de contrôle

Visualiser les logs TensorBoard :
```bash
tensorboard --logdir ./poker_model_output
```

## 🔧 Dépannage

### Erreur "CUDA out of memory"
- Réduisez `batch_size` (ex: 4 au lieu de 8)
- Réduisez `max_seq_length` (ex: 256)
- Utilisez un modèle plus petit

### Pas d'amélioration en entraînement
- Augmentez `num_epochs`
- Diminuez `learning_rate`
- Utilisez un modèle plus grand

### Dataset trop volumineux
Utilisez le streaming :
```python
ds = load_dataset("RZ412/PokerBench", streaming=True)
```

## 📚 Ressources

- **Dataset**: https://huggingface.co/datasets/RZ412/PokerBench
- **Paper**: https://huggingface.co/papers/2501.08328
- **Code Source**: https://github.com/pokerllm/pokerbench
- **Documentation Transformers**: https://huggingface.co/docs/transformers

## ✅ Checklist d'Entraînement

- [ ] Installer les dépendances
- [ ] Vérifier l'accès au dataset depuis Hugging Face
- [ ] Configurer les paramètres d'entraînement
- [ ] Lancer l'entraînement
- [ ] Monitorer les logs
- [ ] Sauvegarder le modèle final
- [ ] Tester les prédictions
- [ ] Évaluer les performances

## Prochaines Étapes

1. **A posteriori l'entraînement** : Évaluez précision sur le test set
2. **Déploiement** : Créez une API FastAPI pour servir le modèle
3. **Fine-tuning** : Entraînez sur vos propres parties de poker
4. **Ensemble** : Combinez plusieurs modèles pour de meilleures décisions
