"""
Script d'inférence et d'évaluation du modèle PokerBench
Utilisez le modèle entraîné pour prédire des décisions au poker
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Dict, List
import json


class PokerDecisionPredictor:
    """Classe pour faire des prédictions de décisions au poker."""
    
    def __init__(self, model_path: str, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        """
        Initialise le prédicteur.
        
        Args:
            model_path: Chemin vers le modèle entraîné
            device: "cuda" ou "cpu"
        """
        self.device = device
        print(f"📦 Chargement du modèle depuis {model_path}...")
        print(f"   Device: {device}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForCausalLM.from_pretrained(model_path).to(device)
        self.model.eval()
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print("✅ Modèle chargé avec succès!")
    
    def predict(
        self,
        scenario: str,
        max_new_tokens: int = 100,
        num_beams: int = 5,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> Dict:
        """
        Prédit la meilleure décision pour un scénario donné.
        
        Args:
            scenario: Description du scénario poker
            max_new_tokens: Nombre max de tokens à générer
            num_beams: Nombre de beams pour la recherche
            temperature: Température de génération (plus bas = plus déterministe)
            top_p: Nucleus sampling parameter
            
        Returns:
            Dict avec {scenario, decision, confidence}
        """
        print(f"\n🤔 Prédiction...")
        print(f"   Scénario: {scenario[:100]}...")
        
        # Tokenize
        inputs = self.tokenizer(scenario, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Générer
        with torch.no_grad():
            outputs = self.model.generate(
                inputs["input_ids"],
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                temperature=temperature,
                top_p=top_p,
                no_repeat_ngram_size=2,
                early_stopping=True,
                output_scores=True,
                return_dict_in_generate=True,
            )
        
        # Décoder
        full_text = self.tokenizer.decode(outputs.sequences[0], skip_special_tokens=True)
        
        # Extraire la décision (première ligne après le scénario)
        lines = full_text.split('\n')
        decision = lines[-1].strip() if len(lines) > 1 else full_text.strip()
        
        # Normaliser la décision
        decision = self._normalize_decision(decision)
        
        result = {
            "scenario": scenario,
            "decision": decision,
            "full_output": full_text,
        }
        
        print(f"   ✅ Décision: {decision}")
        
        return result
    
    @staticmethod
    def _normalize_decision(text: str) -> str:
        """Normalise la sortie pour extraire juste la décision."""
        # Décisions possibles
        keywords = ["fold", "call", "check", "bet", "raise", "allin", "all-in"]
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword in text_lower:
                # Extraire la décision avec le montant si applicable
                if keyword in ["bet", "raise"]:
                    # Chercher le montant
                    import re
                    match = re.search(r'(bet|raise)\s+(\d+)', text_lower)
                    if match:
                        return f"{match.group(1)} {match.group(2)}"
                    return keyword
                return keyword
        
        return text.strip()


def batch_predict(
    predictor: PokerDecisionPredictor,
    scenarios: List[str]
) -> List[Dict]:
    """Fait des prédictions pour un lot de scénarios."""
    
    print(f"\n📋 Prédictions batch sur {len(scenarios)} scénarios...")
    results = []
    
    for i, scenario in enumerate(scenarios):
        print(f"\n[{i+1}/{len(scenarios)}]")
        result = predictor.predict(scenario)
        results.append(result)
    
    return results


def evaluate_on_test_set(
    predictor: PokerDecisionPredictor,
    test_examples: List[Dict]
) -> Dict:
    """Évalue le modèle sur un ensemble de test."""
    
    print(f"\n📊 Évaluation sur {len(test_examples)} exemples...")
    
    correct = 0
    predictions = []
    
    for i, example in enumerate(test_examples):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(test_examples)}")
        
        scenario = example.get("instruction") or example.get("preflop_action", "")
        expected = example.get("output") or example.get("correct_decision", "")
        
        result = predictor.predict(scenario, max_new_tokens=20)
        predicted = result["decision"]
        
        # Normaliser les décisions pour comparaison
        expected_norm = expected.lower().strip()
        predicted_norm = predicted.lower().strip()
        
        is_correct = expected_norm == predicted_norm
        if is_correct:
            correct += 1
        
        predictions.append({
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct
        })
    
    accuracy = correct / len(test_examples)
    
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": len(test_examples),
        "predictions": predictions
    }


def interactive_mode(predictor: PokerDecisionPredictor):
    """Mode interactif pour des prédictions en temps réel."""
    
    print("\n" + "="*60)
    print("🎰 MODE INTERACTIF - Prédictions de Poker")
    print("="*60)
    print("\nEntrez un scénario de poker (tapez 'quit' pour quitter)")
    print("-" * 60)
    
    while True:
        scenario = input("\n📝 Scénario: ").strip()
        
        if scenario.lower() in ["quit", "exit", "q"]:
            print("👋 Au revoir!")
            break
        
        if not scenario:
            print("❌ Veuillez entrer un scénario")
            continue
        
        result = predictor.predict(scenario)
        print(f"\n✅ Décision optimale: {result['decision']}")
        print(f"\n📋 Réponse complète:\n{result['full_output']}")


def demo_scenarios() -> List[str]:
    """Fournit des scénarios de démonstration."""
    
    return [
        "You are playing at a 6-handed table. You are in the BTN with KK. "
        "The UTG player raises to 2.5BB, and the action folds to you.",
        
        "You are at the BB with 88. The SB limps, and you need to decide. "
        "Stacks are 100BB.",
        
        "You are on the flop with a pair of aces on a board of As2h3d. "
        "You have 50BB remaining. The opponent bets 1/4 pot.",
        
        "You are on the river with a flush. The board is 2d3d5d7dJh. "
        "Your opponent goes all-in for 20BB. Should you call?",
    ]


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Utilisation:")
        print("  python evaluate_model.py <model_path> [mode]")
        print("\nModes:")
        print("  interactive  : Mode interactif")
        print("  demo        : Exécuter des scénarios de démonstration")
        print("  batch       : Traiter un fichier JSON")
        sys.exit(1)
    
    model_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "interactive"
    
    try:
        predictor = PokerDecisionPredictor(model_path)
        
        if mode == "interactive":
            interactive_mode(predictor)
        
        elif mode == "demo":
            print("\n🎪 Mode Démonstration")
            scenarios = demo_scenarios()
            results = batch_predict(predictor, scenarios)
            
            print("\n" + "="*60)
            print("📊 Résumé des Prédictions")
            print("="*60)
            
            for i, result in enumerate(results, 1):
                print(f"\n[Scénario {i}]")
                print(f"  Décision: {result['decision']}")
        
        elif mode == "batch" and len(sys.argv) > 3:
            input_file = sys.argv[3]
            print(f"\n📂 Lecture du fichier: {input_file}")
            
            with open(input_file, "r") as f:
                examples = json.load(f)
            
            results = batch_predict(predictor, [ex.get("instruction", "") for ex in examples])
            
            # Sauvegarder les résultats
            output_file = input_file.replace(".json", "_predictions.json")
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            
            print(f"\n✅ Résultats sauvegardés dans: {output_file}")
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
