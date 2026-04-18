"""
PokerBench Dataset Training Script
Ce script charge et entraîne un modèle LLM sur le dataset PokerBench pour 
prédire les décisions optimales au poker.
"""

import os
import json
from typing import Dict, List
from datasets import load_dataset, DatasetDict
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
import torch

# Configuration
CONFIG = {
    "dataset_name": "RZ412/PokerBench",
    "model_name": "distilgpt2",  # Modèle léger pour démarrer
    "max_seq_length": 512,
    "batch_size": 8,
    "learning_rate": 2e-5,
    "num_epochs": 3,
    "output_dir": "./poker_model_output",
}


def load_poker_dataset() -> Dict:
    """Charge le dataset PokerBench de Hugging Face."""
    print("📥 Chargement du dataset PokerBench...")
    ds = load_dataset(CONFIG["dataset_name"])
    print(f"✅ Dataset chargé avec succès")
    print(f"Splits disponibles: {ds.keys()}")
    return ds


def explore_dataset(ds: Dict) -> None:
    """Explore la structure et le contenu du dataset."""
    print("\n📊 Exploration du dataset:")
    
    for split_name, split_data in ds.items():
        print(f"\n--- {split_name} ---")
        print(f"Nombre d'exemples: {len(split_data)}")
        
        if len(split_data) > 0:
            print(f"Colonnes: {split_data.column_names}")
            
            # Affiche un exemple
            example = split_data[0]
            print(f"\nExemple d'entrée:")
            for key, value in example.items():
                if isinstance(value, str):
                    print(f"  {key}: {value[:200]}..." if len(str(value)) > 200 else f"  {key}: {value}")
                else:
                    print(f"  {key}: {value}")


def prepare_dataset_for_training(ds: Dict) -> DatasetDict:
    """Prépare le dataset pour l'entraînement en formatant les exemples."""
    print("\n🔄 Préparation du dataset pour l'entraînement...")
    
    def format_example(example):
        """Formate un exemple dans le format: instruction + output"""
        # Suppose que le dataset a des colonnes 'instruction' et 'output'
        if 'instruction' in example and 'output' in example:
            text = f"{example['instruction']}\n{example['output']}"
        else:
            # Fallback pour d'autres formats
            text = json.dumps(example)
        
        return {"text": text}
    
    # Applique la transformation
    processed_ds = {}
    for split_name, split_data in ds.items():
        if len(split_data) > 0:
            processed_ds[split_name] = split_data.map(
                format_example,
                remove_columns=split_data.column_names
            )
            print(f"✅ {split_name} préparé: {len(processed_ds[split_name])} exemples")
    
    return processed_ds if processed_ds else ds


def tokenize_function(examples: Dict, tokenizer, max_length: int = 512) -> Dict:
    """Tokenize les textes pour l'entraînement."""
    return tokenizer(
        examples["text"] if "text" in examples else list(examples.values())[0],
        padding="max_length",
        truncation=True,
        max_length=max_length,
    )


def setup_training(
    dataset: DatasetDict,
    tokenizer,
    model,
) -> Trainer:
    """Configure le trainer pour l'entraînement."""
    print("\n⚙️ Configuration du trainer...")
    
    # Tokenize le dataset
    tokenized_dataset = dataset.map(
        lambda x: tokenize_function(x, tokenizer, CONFIG["max_seq_length"]),
        batched=True,
        remove_columns=[col for col in dataset["train"].column_names if col != "text"]
        if "train" in dataset else [],
    )
    
    training_args = TrainingArguments(
        output_dir=CONFIG["output_dir"],
        overwrite_output_dir=True,
        num_train_epochs=CONFIG["num_epochs"],
        per_device_train_batch_size=CONFIG["batch_size"],
        per_device_eval_batch_size=CONFIG["batch_size"],
        save_steps=500,
        save_total_limit=2,
        logging_steps=100,
        learning_rate=CONFIG["learning_rate"],
        weight_decay=0.01,
        warmup_steps=500,
        evaluation_strategy="steps",
        eval_steps=500,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )
    
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # Pour la causal language modeling
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset.get("train"),
        eval_dataset=tokenized_dataset.get("test") or tokenized_dataset.get("validation"),
        data_collator=data_collator,
    )
    
    return trainer


def main():
    """Fonction principale pour charger et entraîner le modèle."""
    print("🎲 PokerBench Training Pipeline")
    print("=" * 50)
    
    # 1. Charger le dataset
    dataset = load_poker_dataset()
    
    # 2. Explorer le dataset
    explore_dataset(dataset)
    
    # 3. Préparer le dataset
    processed_dataset = prepare_dataset_for_training(dataset)
    
    # 4. Charger le modèle et le tokenizer
    print(f"\n📦 Chargement du modèle {CONFIG['model_name']}...")
    tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
    model = AutoModelForCausalLM.from_pretrained(CONFIG["model_name"])
    
    # Ajoute pad token si nécessaire
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    print(f"✅ Modèle chargé avec succès")
    
    # 5. Configuration et entraînement
    trainer = setup_training(processed_dataset, tokenizer, model)
    
    # 6. Entraîner le modèle
    print("\n🚀 Démarrage de l'entraînement...")
    trainer.train()
    
    # 7. Sauvegarder le modèle entraîné
    print(f"\n💾 Sauvegarde du modèle entraîné dans {CONFIG['output_dir']}...")
    trainer.save_model(os.path.join(CONFIG["output_dir"], "final_model"))
    tokenizer.save_pretrained(os.path.join(CONFIG["output_dir"], "final_model"))
    
    print("\n✅ Entraînement terminé avec succès!")
    print(f"Modèle sauvegardé dans: {CONFIG['output_dir']}")


def predict_poker_decision(prompt: str, model_path: str) -> str:
    """
    Utilise le modèle entraîné pour prédire une décision au poker.
    
    Args:
        prompt: Description du scénario poker en langage naturel
        model_path: Chemin vers le modèle entraîné
    
    Returns:
        La décision prédite
    """
    print(f"\n🤔 Prédiction pour: {prompt[:100]}...")
    
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)
    
    # Tokenize l'entrée
    inputs = tokenizer(prompt, return_tensors="pt")
    
    # Générer la prédiction
    with torch.no_grad():
        outputs = model.generate(
            inputs["input_ids"],
            max_new_tokens=50,
            num_beams=5,
            temperature=0.7,
            top_p=0.9,
        )
    
    # Décoder
    decision = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return decision


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "predict":
        # Mode prédiction
        if len(sys.argv) < 4:
            print("Usage: python main.py predict '<prompt>' '<model_path>'")
            sys.exit(1)
        
        prompt = sys.argv[2]
        model_path = sys.argv[3]
        result = predict_poker_decision(prompt, model_path)
        print(f"Décision: {result}")
    else:
        # Mode entraînement
        main()
