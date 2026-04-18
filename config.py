"""
Configuration du Projet PokerBench
Personnalisez les paramètres d'entraînement ici
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TrainingConfig:
    """Configuration d'entraînement."""
    
    # Modèle
    model_name: str = "distilgpt2"
    dataset_name: str = "RZ412/PokerBench"
    
    # Hyperparamètres
    batch_size: int = 8
    learning_rate: float = 2e-5
    num_epochs: int = 3
    max_seq_length: int = 512
    
    # Optimisation
    gradient_accumulation_steps: int = 1
    warmup_steps: int = 500
    weight_decay: float = 0.01
    
    # Évaluation
    evaluation_steps: int = 500
    save_steps: int = 500
    save_total_limit: int = 2
    
    # Infrastructure
    output_dir: str = "./poker_model_output"
    logging_dir: str = "./poker_model_output/logs"
    logging_steps: int = 100
    device: str = "cuda"  # ou "cpu"
    
    # Contrôle qualité
    use_fp16: bool = False  # Activation si GPU supporté
    gradient_checkpointing: bool = False  # Pour économiser la mémoire


@dataclass
class InferenceConfig:
    """Configuration d'inférence."""
    
    # Génération
    max_new_tokens: int = 100
    num_beams: int = 5
    temperature: float = 0.7
    top_p: float = 0.9
    no_repeat_ngram_size: int = 2
    
    # Performance
    device: str = "cuda"  # ou "cpu"
    batch_inference: bool = True


# Configurations prédéfinies
CONFIGS = {
    "quick": TrainingConfig(
        model_name="distilgpt2",
        batch_size=8,
        num_epochs=1,
        evaluation_steps=100,
    ),
    "standard": TrainingConfig(
        model_name="gpt2",
        batch_size=8,
        num_epochs=3,
        learning_rate=2e-5,
    ),
    "high-quality": TrainingConfig(
        model_name="EleutherAI/gpt-neo-1.3B",
        batch_size=4,
        num_epochs=5,
        learning_rate=1e-5,
        gradient_accumulation_steps=2,
    ),
    "large-gpu": TrainingConfig(
        model_name="gpt2-large",
        batch_size=16,
        num_epochs=3,
        learning_rate=2e-5,
        use_fp16=True,
    ),
}


def get_config(config_name: str = "standard") -> TrainingConfig:
    """Récupère une configuration prédéfinie."""
    return CONFIGS.get(config_name, CONFIGS["standard"])


def get_inference_config() -> InferenceConfig:
    """Récupère la configuration d'inférence."""
    return InferenceConfig()


class ConfigManager:
    """Gestionnaire de configuration avec sauvegarde/chargement."""
    
    @staticmethod
    def save_config(config: TrainingConfig, filepath: str):
        """Sauvegarde une configuration."""
        import json
        config_dict = {
            "model_name": config.model_name,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "num_epochs": config.num_epochs,
            "max_seq_length": config.max_seq_length,
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(config_dict, f, indent=2)
    
    @staticmethod
    def load_config(filepath: str) -> TrainingConfig:
        """Charge une configuration."""
        import json
        with open(filepath, "r") as f:
            config_dict = json.load(f)
        return TrainingConfig(**config_dict)


# Configuration par défaut
DEFAULT_CONFIG = TrainingConfig()
DEFAULT_INFERENCE_CONFIG = InferenceConfig()


if __name__ == "__main__":
    # Affiche les configurations disponibles
    print("📋 Configurations Disponibles:")
    print("=" * 60)
    
    for name, config in CONFIGS.items():
        print(f"\n{name.upper()}")
        print(f"  Modèle: {config.model_name}")
        print(f"  Batch Size: {config.batch_size}")
        print(f"  Learning Rate: {config.learning_rate}")
        print(f"  Epochs: {config.num_epochs}")
    
    print("\n\n💡 Utilisation:")
    print("  from config import get_config")
    print('  config = get_config("standard")')
