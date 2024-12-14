import requests
import json

urls=["https://www.winamax.fr/paris-sportifs/sports/5","https://www.winamax.fr/paris-sportifs/sports/1"]

def get_page(urls,i):
    url = urls[i]
    response = requests.get(
        url,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        })
    html = response.text
    return html

def get_json(urls,i):
    html = get_page(urls,i)
    split1 = html.split("var PRELOADED_STATE = ")[1]
    split2 = split1.split(";</script>")[0]
    return json.loads(split2)

def get_games_tennis(urls):
    games = []
    json_data = get_json(urls,0)

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
            'odds1': odds[0],
            'odds2': odds[1]
        })

    return games

def get_games_football(urls):
    games = []
    json_data = get_json(urls,1)

    for match_id, match_info in json_data.get('matches', {}).items():
        # Vérifiez si c'est un match de foot (sportId == 1)
        if match_info.get('sportId') != 1:
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
        if len(bet) == 2:
            # Extraire les cotes associées
            odds = [
                json_data['odds'].get(str(bet[0]), 'Unknown'),
                json_data['odds'].get(str(bet[1]), 'Unknown')
            ]
            games.append({
                'player1': player1,
                'player2': player2,
                'odds1': odds[0],
                'odds2': odds[1],
            })
        elif len(bet) == 3:
            # Extraire les cotes associées
            odds = [
                json_data['odds'].get(str(bet[0]), 'Unknown'),
                json_data['odds'].get(str(bet[1]), 'Unknown'),
                json_data['odds'].get(str(bet[2]), 'Unknown')
            ]

            # Ajouter le match et les cotes à la liste des jeux
            games.append({
                'player1': player1,
                'player2': player2,
                'odds1': odds[0],
                'odds2': odds[1],
                'odds3': odds[2]
            })

    return games




tennis_games = get_games_tennis(urls)
foot_games=get_games_football(urls)

# Sauvegarder dans un nouveau fichier JSON
with open('win_matches_foot.json', 'w', encoding='utf-8') as json_file:
    json.dump(foot_games, json_file, indent=4, ensure_ascii=False)

with open('win_matches_tennis.json', 'w', encoding='utf-8') as json_file:
    json.dump(tennis_games, json_file, indent=4, ensure_ascii=False)

print("Données extraites et sauvegardées dans matches2.json")