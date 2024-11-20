import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import linregress

# Exemple de données
Uc = np.array([5,4,3,2,1,0,-1,-2,-3,-4,-5])  # en mol/L par exemple
fw = np.array([18.6,16.9,15.2,13.6,11.9,10,8.2,6.5,4.8,3.1,1.4])  # intensité en unités arbitraires

# Régression linéaire pour obtenir la courbe d'étalonnage
slope, intercept, r_value, p_value, std_err = linregress(Uc, fw)

# Calcul de la droite de régression
regression_line = slope * Uc + intercept

# Tracé du graphe
plt.figure(figsize=(8, 6))
plt.scatter(Uc, fw, color='blue', label='Données expérimentales')
plt.plot(Uc, regression_line, color='red', label=f'régression linéaire : fw = {slope:.2f}Uc + {intercept:.2f}')
plt.ylabel("fw (kHz)")
plt.xlabel("Uc (V)")
plt.title("Courbe d'étalonnage")
plt.legend()
plt.grid(True)
plt.show()
