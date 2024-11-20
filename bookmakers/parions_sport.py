import requests
from bs4 import BeautifulSoup
import json

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


def get_html(i):
    urls=["https://www.enligne.parionssport.fdj.fr/paris-tennis","https://www.enligne.parionssport.fdj.fr/paris-football"]
    html = get_page(urls,i)
    split1 = html.split('<body class="psel">')[1]
    split2 = split1.split('<p>Sur notre site')[0]
    return split2

def get_games_tennis():

    with open("parions_sport_data.html", "w", encoding="utf-8") as file:
        data = get_html(0)
        file.write(data)

    # Ouvrir et lire le fichier HTML
    with open("parions_sport_data.html", 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Initialiser BeautifulSoup pour parser le HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Beautifier le HTML
    pretty_html = soup.prettify()

    # Sauvegarder le HTML "beautifié" dans un nouveau fichier pour inspection
    with open("parions_sport_data.html", 'w', encoding='utf-8') as file:
        file.write(pretty_html)

    # Ouvrir et lire le fichier HTML
    with open("parions_sport_data.html", 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Initialiser BeautifulSoup pour parser le HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Créer une liste pour stocker les données extraites

    matches = []

    # Extraire les matchs
    for event in soup.find_all('psel-event-main'):
        # Extraire les noms des joueurs
        players = event.find_all('p', class_='psel-market__label')
        if len(players) == 2:
            player1 = players[0]['title']
            player2 = players[1]['title']

            # Extraire les cotes
            odds = event.find_all('span', class_='psel-outcome__data')
            if len(odds) == 2:
                odds1 = odds[0].text.strip()
                odds2 = odds[1].text.strip()

                # Extraire la date
                date = event.find('time', class_='psel-timer').text.strip()

                # Ajouter les informations dans la liste des matchs
                matches.append({
                    'player1': player1,
                    'player2': player2,
                    'odds1': odds1,
                    'odds2': odds2,
                    'date': date
                })
    return matches

def get_games_football():
    with open("parions_sport_data1.html", "w", encoding="utf-8") as file:
        data = get_html(1)
        file.write(data)

    # Ouvrir et lire le fichier HTML
    with open("parions_sport_data1.html", 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Initialiser BeautifulSoup pour parser le HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Beautifier le HTML
    pretty_html = soup.prettify()

    # Sauvegarder le HTML "beautifié" dans un nouveau fichier pour inspection
    with open("parions_sport_data1.html", 'w', encoding='utf-8') as file:
        file.write(pretty_html)

    # Ouvrir et lire le fichier HTML
    with open("parions_sport_data1.html", 'r', encoding='utf-8') as file:
        html_content = file.read()

    # Initialiser BeautifulSoup pour parser le HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Créer une liste pour stocker les données extraites

    matches = []

    # Extraire les matchs
    # Recherche chaque section de match
    for match in soup.find_all('psel-row-col'):
        odds = {}
        
        # Récupère les équipes et les cotes correspondantes
        teams_and_draw = match.find_all('p', class_='psel-market__label')
        odds_values = match.find_all('span', class_='psel-outcome__data')

        if len(teams_and_draw) == 3 and len(odds_values) == 3:
            odds['team1'] = {
                'name': teams_and_draw[0].get_text(strip=True),
                'odd': odds_values[0].get_text(strip=True)
            }
            odds['draw'] = {
                'name': teams_and_draw[1].get_text(strip=True),
                'odd': odds_values[1].get_text(strip=True)
            }
            odds['team2'] = {
                'name': teams_and_draw[2].get_text(strip=True),
                'odd': odds_values[2].get_text(strip=True)
            }
            matches.append(odds)
    
    return matches


def transform_matches(data):
    transformed_data = []
    for match in data:
        transformed_data.append({
            "player1": match["team1"]["name"],
            "player2": match["team2"]["name"],
            "odds1": match["team1"]["odd"].replace(",", "."),
            "odds2": match["draw"]["odd"].replace(",", "."),
            "odds3": match["team2"]["odd"].replace(",", "."),
            
        })
    return transformed_data

# Convertir la liste en JSON
json_data_tennis = json.dumps(get_games_tennis(), indent=4, ensure_ascii=False)
json_data_football = json.dumps(transform_matches(get_games_football()), indent=4, ensure_ascii=False)

# Sauvegarder dans un fichier JSON
with open('pp_matches_foot.json', 'w', encoding='utf-8') as json_file:
    json_file.write(json_data_football)

print("Données extraites et sauvegardées dans matches.json")