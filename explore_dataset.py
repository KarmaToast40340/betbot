"""
Script d'exploration du dataset PokerBench
Analysez la structure du dataset avant l'entraînement
"""

from datasets import load_dataset
import pandas as pd
from collections import Counter
import json


def analyze_pokerbench():
    """Analyse complète du dataset PokerBench."""
    
    print("🔍 Analyse du Dataset PokerBench")
    print("=" * 60)
    
    # Charger le dataset
    print("\n📥 Chargement du dataset...")
    ds = load_dataset("RZ412/PokerBench")
    
    # Analyser chaque split
    for split_name in ds.keys():
        print(f"\n{'='*60}")
        print(f"📊 SPLIT: {split_name}")
        print(f"{'='*60}")
        
        split_data = ds[split_name]
        print(f"Nombre d'exemples: {len(split_data):,}")
        print(f"Colonnes: {split_data.column_names}")
        
        # Statistiques sur les colonnes
        stats = {}
        
        for col in split_data.column_names:
            examples = split_data[col]
            
            if isinstance(examples[0], str):
                # Colonne texte
                lengths = [len(ex) for ex in examples]
                stats[col] = {
                    "type": "text",
                    "min_length": min(lengths),
                    "max_length": max(lengths),
                    "avg_length": sum(lengths) / len(lengths),
                    "unique_count": len(set(examples)),
                }
                
                # Pour output, analyser les décisions
                if col in ["output", "correct_decision"]:
                    decision_counts = Counter(examples)
                    print(f"\n  📌 {col} - Distributions:")
                    for decision, count in decision_counts.most_common(10):
                        pct = (count / len(examples)) * 100
                        print(f"     {decision}: {count:,} ({pct:.1f}%)")
            
            elif isinstance(examples[0], (int, float)):
                # Colonne numérique
                stats[col] = {
                    "type": "numeric",
                    "min": min(examples),
                    "max": max(examples),
                    "avg": sum(examples) / len(examples),
                }
            
            else:
                stats[col] = {"type": str(type(examples[0]))}
        
        # Afficher les statistiques
        print(f"\n📈 Statistiques des colonnes:")
        for col, col_stats in stats.items():
            print(f"\n  • {col}:")
            for key, value in col_stats.items():
                if key != "type":
                    if isinstance(value, float):
                        print(f"    {key}: {value:.2f}")
                    else:
                        print(f"    {key}: {value:,}")
        
        # Exemples
        print(f"\n📝 Exemples (premiers 3):")
        for i in range(min(3, len(split_data))):
            print(f"\n  Exemple {i+1}:")
            example = split_data[i]
            for key, value in example.items():
                if isinstance(value, str) and len(value) > 100:
                    print(f"    {key}: {value[:100]}...")
                else:
                    print(f"    {key}: {value}")


def compare_preflop_postflop():
    """Compare les datasets pre-flop et post-flop."""
    
    print("\n\n🎰 Comparaison Pre-Flop vs Post-Flop")
    print("=" * 60)
    
    ds = load_dataset("RZ412/PokerBench")
    
    splits_info = {}
    for split_name in ds.keys():
        size = len(ds[split_name])
        cols = ds[split_name].column_names
        splits_info[split_name] = {"size": size, "columns": cols}
    
    # Créer un tableau de comparaison
    comparison_data = []
    for split_name, info in splits_info.items():
        if "preflop" in split_name:
            stage = "Pre-Flop"
        elif "postflop" in split_name:
            stage = "Post-Flop"
        else:
            stage = "Unknown"
        
        split_type = "Train" if "train" in split_name else "Test"
        
        comparison_data.append({
            "Stage": stage,
            "Type": split_type,
            "Exemples": f"{info['size']:,}",
            "Colonnes": len(info["columns"])
        })
    
    df = pd.DataFrame(comparison_data)
    print("\n" + df.to_string(index=False))


def dataset_insights():
    """Fournit des insights utiles pour l'entraînement."""
    
    print("\n\n💡 Insights pour l'Entraînement")
    print("=" * 60)
    
    ds = load_dataset("RZ412/PokerBench")
    
    insights = []
    
    # Calculer la taille totale du dataset
    total_examples = sum(len(ds[split]) for split in ds.keys())
    print(f"\n✓ Total d'exemples d'entraînement: {total_examples:,}")
    print("  → Pour un bon fine-tuning LLM : 10k-100k exemples (✓ Ok)")
    
    # Analyser les tokens
    print(f"\n✓ Structure des données:")
    for split in ds.keys():
        if "train" in split:
            sample = ds[split][0]
            if "instruction" in sample and "output" in sample:
                avg_tokens = len(sample["instruction"].split()) + len(sample["output"].split())
                print(f"  {split}: ~{avg_tokens} tokens par exemple")
    
    # Recommandations
    print(f"\n📋 Recommandations:")
    print("  1. Batch size: 8-16 (ajustez selon votre GPU)")
    print("  2. Learning rate: 2e-5 pour fine-tuning, 5e-5 pour entraînement")
    print("  3. Epochs: 3-5 (le dataset est suffisamment grand)")
    print("  4. Max seq length: 512 tokens")
    print("  5. Modèles recommandés:")
    print("     - distilgpt2 (82M) : CPU/GPU faible")
    print("     - gpt2 (124M) : GPU standard")
    print("     - TinyLlama (1.1B) : GPU moyen")
    print("     - LLaMA-2 (7B+) : GPU puissant (A100, H100, etc.)")


def export_dataset_sample():
    """Exporte un petit échantillon du dataset pour inspection."""
    
    print("\n\n💾 Export d'un échantillon...")
    
    ds = load_dataset("RZ412/PokerBench")
    
    # Exporter un petit échantillon en JSON
    sample_size = 100
    for split in ["preflop_train", "postflop_train"]:
        if split in ds and len(ds[split]) > 0:
            sample = ds[split].select(range(min(sample_size, len(ds[split]))))
            
            # Convertir en liste de dictionnaires
            sample_data = [sample[i] for i in range(len(sample))]
            
            filename = f"{split}_sample.json"
            with open(filename, "w") as f:
                json.dump(sample_data, f, indent=2)
            
            print(f"✓ {filename} créé ({len(sample_data)} exemples)")


if __name__ == "__main__":
    try:
        analyze_pokerbench()
        compare_preflop_postflop()
        dataset_insights()
        export_dataset_sample()
        
        print("\n\n✅ Analyse terminée!")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        print("\nAssurez-vous que:")
        print("- Vous avez internet (pour télécharger le dataset)")
        print("- Les packages sont installés: pip install -r requirements.txt")
