import requests
import json


def get_page():
    url = "https://www.winamax.fr/paris-sportifs/sports/5"
    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        })
    html = response.text
    return html

def get_json(data):
    # Vérifiez si 'data' est déjà un dictionnaire
    if isinstance(data, dict):
        return data
    # Assurez-vous que 'data' est une chaîne JSON
    elif isinstance(data, str):
        return json.loads(data)
    else:
        raise TypeError("The data must be a string or a dictionary")

def get_games_tennis(data):
    games = []
    json_data = get_json(data)

    for match_id, match_info in json_data.get('matches', {}).items():
        # Vérifiez si c'est un match de tennis (sportId == 5)
        if match_info.get('sportId') != 5:
            continue

        # Extraire les noms des joueurs avec une vérification
        player1 = match_info.get('competitor1Name')
        player2 = match_info.get('competitor2Name')

        # Assurez-vous que les noms ne sont pas None
        player1 = "".join(player1.split()) if player1 else 'Unknown'
        player2 = "".join(player2.split()) if player2 else 'Unknown'

        # Extraire l'ID du pari principal (mainBetId)
        bet_id = match_info.get('mainBetId')

        # Vérifiez si le pari existe
        if not bet_id or str(bet_id) not in json_data.get('bets', {}):
            continue

        bet = json_data['bets'][str(bet_id)].get('outcomes', [])

        # Vérifiez que le pari a exactement deux cotes, ce qui est typique pour un match de tennis
        if len(bet) != 2:
            continue

        # Extraire les cotes associées
        odds = [
            json_data['odds'].get(str(bet[0]), 'Unknown'),
            json_data['odds'].get(str(bet[1]), 'Unknown')
        ]

        # Ajouter le match et les cotes à la liste des jeux
        games.append({
            'player1': player1,
            'player2': player2,
            'odds': odds
        })

    return games

# Exemple d'utilisation avec le fichier JSON
with open('winamax_data.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

tennis_games = get_games_tennis(data)

# Sauvegarder dans un nouveau fichier JSON
with open('matches2.json', 'w', encoding='utf-8') as json_file:
    json.dump(tennis_games, json_file, indent=4, ensure_ascii=False)

print("Données extraites et sauvegardées dans matches2.json")