import parions_sport
import winamax
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime









with open("parions_sport_data.html", "w", encoding="utf-8") as file:
  data = parions_sport.get_html()
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

# Convertir la liste en JSON
json_data = json.dumps(matches, indent=4, ensure_ascii=False)

# Sauvegarder dans un fichier JSON
with open('matches.json', 'w', encoding='utf-8') as json_file:
    json_file.write(json_data)

print("Données extraites et sauvegardées dans matches.json")