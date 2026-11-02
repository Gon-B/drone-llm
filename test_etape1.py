"""Étape 1 : tester le faux drone et l'exécuteur avec des plans écrits à la main.

Lancer avec : python3 test_etape1.py
Aucun appel au LLM, aucune clé API nécessaire.
"""

import asyncio

from drone import FauxDrone
from executeur import executer

# Mission normale : décolle à 5 m, avance de 10 m vers le nord, atterris.
PLAN_NORMAL = {
    "etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "AVANCER", "direction": "nord", "distance_m": 10},
        {"action": "ATTERRIR"},
    ]
}

# Impossible : avancer alors que le drone est encore au sol.
PLAN_AU_SOL = {
    "etapes": [
        {"action": "AVANCER", "direction": "est", "distance_m": 10},
        {"action": "ATTERRIR"},
    ]
}

# Impossible en plein vol : descendre sous le sol -> atterrissage d'urgence.
PLAN_SOUS_LE_SOL = {
    "etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "AVANCER", "direction": "est", "distance_m": 10},
        {"action": "AVANCER", "direction": "descendre", "distance_m": 8},
        {"action": "ATTERRIR"},
    ]
}


async def tester(nom, plan):
    print("\n" + "=" * 60)
    print(f"TEST : {nom}")
    print("=" * 60)
    drone = FauxDrone()
    await drone.connecter()
    resultat = await executer(plan, drone)
    print(f"\nCompte-rendu : {resultat}")


async def main():
    await tester("mission normale", PLAN_NORMAL)
    await tester("avancer au sol", PLAN_AU_SOL)
    await tester("descendre sous le sol", PLAN_SOUS_LE_SOL)


if __name__ == "__main__":
    asyncio.run(main())
