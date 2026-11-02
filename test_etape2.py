"""Étape 2 : tester le traducteur LLM et le validateur de format.

Lancer avec : python3 test_etape2.py
Nécessite la variable ANTHROPIC_API_KEY. Chaque consigne coûte une fraction de centime.
"""

import json

from traducteur import traduire
from validateur import verifier_format

CONSIGNES = [
    "Décolle à 5 mètres, avance de 10 mètres vers le nord, puis atterris.",
    "Monte à 3 m, va 20 m à l'est, reviens de 20 m à l'ouest et pose-toi.",
    "Décolle à 8 mètres, monte encore de 2 mètres, puis descends de 4 mètres et atterris.",
    "Quel temps fait-il aujourd'hui ?",
    "Fais un salto arrière.",
]


def main():
    for consigne in CONSIGNES:
        print("\n" + "=" * 60)
        print(f"CONSIGNE : {consigne}")
        print("=" * 60)

        brut = traduire(consigne)
        print("Réponse brute du LLM :")
        print(json.dumps(brut, ensure_ascii=False, indent=2))

        if "refus" in brut:
            print(f"\n-> Le LLM a REFUSÉ : {brut['refus']}")
            continue

        ok, resultat = verifier_format(brut)
        if ok:
            print("\n-> Validateur niveau 1 : format OK")
        else:
            print(f"\n-> Validateur niveau 1 : REFUSÉ, {resultat}")


if __name__ == "__main__":
    main()
