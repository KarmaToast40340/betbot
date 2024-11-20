import bookmakers.parions_sport as parions_sport
import bookmakers.winamax as winamax
import log
from difflib import SequenceMatcher

win_urls=["https://www.winamax.fr/paris-sportifs/sports/5","https://www.winamax.fr/paris-sportifs/sports/1"]




def sof(valeur):
    try:
        if isinstance(valeur, (float, int)):
            return float(valeur)
        valeur = valeur.replace(',', '.')
        return float(valeur)
    except (ValueError, TypeError):
        print(f"Erreur de conversion pour la valeur : {valeur}")
        return None

def same(pp, win):
    s = pp
    q = win
    sous_chaine = s.split('.')[-1]
    return sous_chaine in q and s[0] == q[0]

def similarity_tennis(g, oth):
    s = 0
    p1, p2 = g['player1'], g['player2']
    if same(p1, oth['player1']):
        s += 1
    if same(p2, oth['player2']):
        s += 1
    return s

def str_similarity(a, b):
	return SequenceMatcher(None, a, b).ratio()

def find_best_match_football(game, others):
	if (len(others) == 0 or game == None):
		return None
	m = 0
	m_obj = None
	for other in others:
		sim = str_similarity(game['player1'], other['player1']) + str_similarity(game['player2'], other['player2'])
		if (sim > m):
			m = sim
			m_obj = other
	if (str_similarity(game['player1'], m_obj['player1']) < 0.81):
		return None
	if (str_similarity(game['player2'], m_obj['player2']) < 0.81):
		return None
	return m_obj



def find_best_match_tennis(g, others):
    for i in range(len(others)):
        if similarity_tennis(g, others[i]) == 2:
            return others[i]
    return None

win_games_tennis = winamax.get_games_tennis(win_urls)
win_games_football = winamax.get_games_football(win_urls)
pp_games_tennis = parions_sport.get_games_tennis()
pp_games_football = parions_sport.transform_matches(parions_sport.get_games_football())

def arb(a, b):
    return 1 - (1/a + 1/b) * 100
def arb3(a, n, b):
	return (1 - (1/a + 1/n + 1/b)) * 100

def arb_games_tennis(g1, g2):
    a1, a2 = sof(g1['odds1']), sof(g1['odds2'])
    b1, b2 = sof(g2['odds1']), sof(g2['odds2'])
    return float(max(arb(a1, b1), arb(a2, b2)))

def arb_games_football(g1, g2):
    a1, a2, a3 = sof(g1['odds1']), sof(g1['odds2']), sof(g1['odds3'])
    b1, b2, b3 = sof(g2['odds1']), sof(g2['odds2']), sof(g2['odds3'])
    return float(max(arb3(a1, a2, b3), arb3(a1, b2, a3), arb3(a1, b2, b3), arb3(b1, a2, a3), arb3(b1, a2, b3), arb3(b1, b2, a3)))

for g in pp_games_tennis:
    print(g)
    other = find_best_match_tennis(g, win_games_tennis)
    
    if other != None:
        arb_value = arb_games_tennis(g, other)
        
        # Vérifie si l'arbitrage est positif avant de loguer
        if arb_value > 0:
            log.discord(f"Arbitrage trouvé : {g['player1']} vs {g['player2']} ({g['odds1']} vs {g['odds2']})")
        else:
            print("Aucun arbitrage positif trouvé pour ce match. ~ ", arb_value)
    else:
        print("Aucun match correspondant trouvé.")

for g in pp_games_football:
    print(g)
    other = find_best_match_football(g, win_games_football)
    
    if other != None:
        arb_value = arb_games_football(g, other)
        
        # Vérifie si l'arbitrage est positif avant de loguer
        if arb_value > 0:
            log.discord(f"Arbitrage trouvé : {g['player1']} vs {g['player2']} ({g['odds1']} vs {g['odds2']})")
        else:
            print("Aucun arbitrage positif trouvé pour ce match. ~ ", arb_value)
    else:
        print("Aucun match correspondant trouvé.")
