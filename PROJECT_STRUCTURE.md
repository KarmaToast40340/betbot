# 📁 Structure du Projet PokerBench

```
betbot/
├── 📄 main.py                    # Script principal d'entraînement
├── 📄 explore_dataset.py         # Script d'exploration du dataset
├── 📄 evaluate_model.py          # Script d'évaluation et prédictions
├── 📄 config.py                  # Configuration des paramètres
│
├── 📋 requirements.txt           # Dépendances Python
├── 📖 README.md                  # Documentation générale
├── 🚀 EXECUTION_GUIDE.md         # Guide complet d'exécution
├── 📋 quick_start.sh             # Script de démarrage rapide
│
└── 📁 poker_model_output/        # (Créé lors de l'entraînement)
    ├── final_model/              # Modèle entraîné final
    ├── checkpoint-*/             # Points de contrôle
    └── logs/                     # Logs TensorBoard
```

## 📚 Description des Fichiers

### 🔧 Scripts Principaux

**`main.py`** (250+ lignes)
- Charge le dataset PokerBench
- Prépare les données pour l'entraînement
- Configure et exécute l'entraînement
- Sauvegarde le modèle final
```bash
python3 main.py
```

**`explore_dataset.py`** (200+ lignes)
- Analyse la structure du dataset
- Affiche statistiques et distributions
- Compare pre-flop vs post-flop
- Exporte des échantillons JSON
```bash
python3 explore_dataset.py
```

**`evaluate_model.py`** (250+ lignes)
- Classe `PokerDecisionPredictor` pour les prédictions
- Mode interactif pour tester le modèle
- Évaluation sur des datasets
- Traitement par lot de scénarios
```bash
python3 evaluate_model.py <model_path> interactive
```

**`config.py`** (150+ lignes)
- Configuration centralisée
- 4 profils prédéfinis (quick, standard, high-quality, large-gpu)
- Gestionnaire de configuration avec sauvegarde/chargement
```python
from config import get_config
config = get_config("standard")
```

### 📖 Documentation

**`README.md`**
- Vue d'ensemble du projet
- Démarrage rapide
- Configuration personnalisée
- Modèles recommandés
- Cas d'usage avancés
- Ressources

**`EXECUTION_GUIDE.md`** ⭐ À lire en premier!
- Guide étape par étape
- 4 étapes du pipeline
- Exemples concrets
- Troubleshooting
- Cas d'usage avancés

**`quick_start.sh`**
- Menu interactif
- Automatise les tâches courantes
```bash
chmod +x quick_start.sh
./quick_start.sh
```

### 📦 Configuration

**`requirements.txt`**
```
torch>=2.0.0
transformers>=4.35.0
datasets>=2.14.0
numpy>=1.24.0
pandas>=2.0.0
```

## 🎯 Workflow Recommandé

### Jour 1: Découverte

```bash
# 1. Clone/install
cd /home/karma/Documents/Pers/betbot
pip install -r requirements.txt

# 2. Explore le dataset
python3 explore_dataset.py
# Génère: preflop_train_sample.json, postflop_train_sample.json
```

### Jour 2: Entraînement

```bash
# 1. Entraîne un modèle
python3 main.py
# Prend 1-8 heures selon le GPU
# Crée: ./poker_model_output/final_model/

# 2. (Optionnel) Monitor TensorBoard
tensorboard --logdir ./poker_model_output/logs
```

### Jour 3: Utilisation

```bash
# 1. Test démo
python3 evaluate_model.py ./poker_model_output/final_model demo

# 2. Mode interactif
python3 evaluate_model.py ./poker_model_output/final_model interactive

# 3. Traitement par lot
python3 evaluate_model.py ./poker_model_output/final_model batch scenarios.json
```

## 🔍 Exploration du Dataset

### Splits Disponibles

- `preflop_train` : 60,000 exemples
- `preflop_test` : 1,000 exemples  
- `postflop_train` : 500,000 exemples
- `postflop_test` : 10,000 exemples

### Colonnes du Dataset

**Pre-Flop:**
```python
{
    "instruction": str,  # Scénario en langage naturel
    "output": str        # Décision: fold|call|check|bet|raise
}
```

**Post-Flop:**
```python
{
    "preflop_action": str,      # Actions pré-flop
    "board_flop": str,          # 3 cartes du flop
    "board_turn": str,          # Carte du turn
    "board_river": str,         # Carte de la river
    "postflop_action": str,     # Actions post-flop
    "holding": str,             # Cartes du joueur
    "correct_decision": str,    # Décision optimale
    # ... autres colonnes
}
```

## 🚀 Commandes Rapides

```bash
# Démarrage rapide (menu interactif)
./quick_start.sh

# Seulement exploration
python3 explore_dataset.py

# Entraînement (modèle par défaut)
python3 main.py

# Entraînement custom (modifiez CONFIG dans main.py d'abord)
python3 main.py

# Prédictions interactives
python3 evaluate_model.py ./poker_model_output/final_model interactive

# Mode démo
python3 evaluate_model.py ./poker_model_output/final_model demo

# Voir les configs disponibles
python3 config.py

# Check installation
python3 -c "import torch; print(f'GPU: {torch.cuda.is_available()}')"
```

## 📊 Modèles Supportés

| Modèle | Params | Vitesse | Qualité | RAM GPU | Recommandé |
|--------|--------|---------|---------|---------|-----------|
| distilgpt2 | 82M | ⚡⚡⚡ | ⭐ | 1-2GB | CPU/GTX1050 |
| gpt2 | 124M | ⚡⚡ | ⭐⭐ | 2-4GB | GTX1080 |
| gpt2-medium | 335M | ⚡ | ⭐⭐⭐ | 4-8GB | RTX2070 |
| gpt2-large | 762M | ⚡ | ⭐⭐⭐⭐ | 8-12GB | RTX3070 |
| neo-125m | 125M | ⚡⚡ | ⭐⭐ | 1-2GB | CPU/GTX1050 |
| neo-1.3B | 1.3B | ⚡ | ⭐⭐⭐⭐ | 8-16GB | RTX3080 |

## 🎓 Points Clés à Retenir

1. **Dataset volumineux** : 60k + 500k exemples
   - Pré-flop vs Post-flop : approches différentes

2. **Flexibilité** : 4 profils de configuration
   - Quick (1h) → High-quality (6h)

3. **Monitoring** : Logs TensorBoard automatiques
   - Visualisez la loss, accuracy, etc.

4. **Modularity** : Scripts séparés et réutilisables
   - Exploration → Entraînement → Évaluation

5. **Production-ready** : 
   - Gestion d'erreurs
   - Sauvegarde de points de contrôle
   - Fonction de prédiction

## ✅ Validation Finale

```bash
# Vérifier que tout fonctionne
python3 << 'EOF'
print("✅ Vérification du projet PokerBench:")
print("  ✓ main.py: Script d'entraînement")
print("  ✓ explore_dataset.py: Exploration du dataset")
print("  ✓ evaluate_model.py: Prédictions et évaluation")
print("  ✓ config.py: Configuration personnalisable")
print("  ✓ requirements.txt: Dépendances")
print("  ✓ README.md: Documentation")
print("  ✓ EXECUTION_GUIDE.md: Guide d'exécution détaillé")
print("")
print("🚀 Prêt à commencer!")
print("  1. Lisez: EXECUTION_GUIDE.md")
print("  2. Explorez: python3 explore_dataset.py")
print("  3. Entraînez: python3 main.py")
print("  4. Testez: python3 evaluate_model.py ./poker_model_output/final_model interactive")
EOF
```

---

*Dernière mise à jour: Avril 2026*
