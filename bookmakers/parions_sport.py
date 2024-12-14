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

    # Parcourir les événements de type `psel-event-main`
    for event in soup.find_all('psel-event-main'):
        # Extraire les noms des joueurs
        players = event.find_all('th', class_='psel-market__head')
        if len(players) >= 2:  # Vérifier qu'il y a au moins 2 joueurs
            player1 = players[0].text.strip()
            player2 = players[1].text.strip()

            # Extraire les cotes
            odds = event.find_all('span', class_='psel-outcome__data')
            if len(odds) >= 2:  # Vérifier qu'il y a au moins 2 cotes
                odds1 = odds[0].text.strip()
                odds2 = odds[1].text.strip()

                # Extraire la date
                date_tag = event.find('time', class_='psel-timer')
                date = date_tag.text.strip() if date_tag else "Non spécifiée"

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

    # Rechercher les tables des matchs
    for table in soup.find_all('table', class_='psel-market--row-col'):
        # Extraire les joueurs depuis les en-têtes (thead ou th)
        headers = table.find_all('th')
        if len(headers) >= 2:
            player1 = headers[0].text.strip()
            player2 = headers[2].text.strip()

            # Extraire les cotes
            odds = table.find_all('span', class_='psel-outcome__data')
            if len(odds) >= 3:
                odds1 = odds[0].text.strip()
                odds2 = odds[1].text.strip()
                odds3 = odds[2].text.strip()

                # Extraire la date (si disponible)
                date_tag = table.find_previous('time', class_='psel-timer')
                date = date_tag.text.strip() if date_tag else "Non spécifiée"

                # Ajouter les informations dans la liste
                matches.append({
                    'player1': player1,
                    'player2': player2,
                    'odds1': odds1,
                    'draw': odds2,
                    'odds3': odds3,
                    'date': date
                })
    
    return matches

# Convertir la liste en JSON
json_data_tennis = json.dumps(get_games_tennis(), indent=4, ensure_ascii=False)
json_data_football = json.dumps(get_games_football(), indent=4, ensure_ascii=False)

# Sauvegarder dans un fichier JSON
with open('pp_matches_foot.json', 'w', encoding='utf-8') as json_file:
    json_file.write(json_data_football)

with open('pp_matches_tennis.json', 'w', encoding='utf-8') as json_file:
    json_file.write(json_data_tennis)

print("Données extraites et sauvegardées dans matches.json")