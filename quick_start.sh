#!/bin/bash

# Script de démarrage rapide pour PokerBench Training
# Exécutez: ./quick_start.sh

echo "🎰 PokerBench AI Poker Decision Training"
echo "========================================"
echo ""

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trouvé. Veuillez installer Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python trouvé: $PYTHON_VERSION"

# Vérifier les dépendances
echo ""
echo "📦 Vérification des dépendances..."

if ! python3 -c "import torch" 2>/dev/null; then
    echo "⚠️  PyTorch non installé"
    echo "   Installation en cours... (cela peut prendre quelques minutes)"
    pip install torch transformers datasets -q
fi

if ! python3 -c "import datasets" 2>/dev/null; then
    echo "⚠️  Datasets non installé"
    echo "   Installation en cours..."
    pip install -r requirements.txt -q
fi

echo "✅ Dépendances OK"

# Menu
echo ""
echo "Que voulez-vous faire?"
echo "1. Explorer le dataset"
echo "2. Entraîner un modèle"
echo "3. Faire des prédictions"
echo "4. Évaluer le modèle"
echo ""

read -p "Sélectionnez une option (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🔍 Exploration du dataset..."
        python3 explore_dataset.py
        ;;
    2)
        echo ""
        echo "🚀 Entraînement du modèle..."
        echo "(Cela peut prendre quelques heures selon votre GPU)"
        echo ""
        python3 main.py
        ;;
    3)
        echo ""
        echo "🎯 Mode prédictions interactif"
        read -p "Path vers le modèle entraîné (./poker_model_output/final_model): " model_path
        model_path=${model_path:=./poker_model_output/final_model}
        python3 evaluate_model.py "$model_path" interactive
        ;;
    4)
        echo ""
        echo "📊 Évaluation du modèle"
        read -p "Path vers le modèle entraîné (./poker_model_output/final_model): " model_path
        model_path=${model_path:=./poker_model_output/final_model}
        python3 evaluate_model.py "$model_path" demo
        ;;
    *)
        echo "Option invalide"
        exit 1
        ;;
esac

echo ""
echo "✅ Terminé!"
