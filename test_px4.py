"""Test de connexion à PX4 : décollage à 3 m, 5 m vers le nord, atterrissage.

À lancer sur le mini PC, avec le simulateur PX4 + Gazebo déjà démarré :
    python3 test_px4.py
Aucun LLM, aucune clé API : on vérifie seulement la liaison MAVSDK.
"""

import asyncio

from drone import Px4Drone
from executeur import executer

PLAN = {
    "etapes": [
        {"action": "DECOLLER", "altitude_m": 3},
        {"action": "AVANCER", "direction": "nord", "distance_m": 5},
        {"action": "ATTERRIR"},
    ]
}


async def main():
    drone = Px4Drone()
    await drone.connecter()
    resultat = await executer(PLAN, drone)
    print(f"\nCompte-rendu : {resultat}")


if __name__ == "__main__":
    asyncio.run(main())
