"""Orchestrateur : le programme principal.

Usage :
    python3 main.py                       -> V2 (validateur complet), boucle de consignes
    python3 main.py --v1                  -> V1 : validateur de format seulement (démo de l'attaque)
    python3 main.py "décolle à 5 m ..."   -> une seule consigne
    python3 main.py --confirmer           -> demande "Exécuter ? (o/n)" avant chaque vol
    python3 main.py --regle-prompt        -> expérience : la règle de zone aussi dans le prompt du LLM
    python3 main.py --px4                 -> vrai drone PX4 (simulateur Gazebo) au lieu du faux drone

Enchaîne les briques dans l'ordre :
    consigne -> traducteur (LLM) -> validateur -> exécuteur -> drone
"""

import asyncio
import json
import sys

from drone import FauxDrone, Px4Drone
from executeur import decrire, executer
from journal import enregistrer
from traducteur import MODELE, traduire
from validateur import valider


def afficher_plan(plan):
    for numero, etape in enumerate(plan["etapes"], start=1):
        print(f"   {numero}. {decrire(etape)}")


async def mission(consigne, drone, confirmer, securite, regle_prompt=False):
    """Traite une consigne de bout en bout. Renvoie un résumé (dict).

    securite=False : V1, seul le format est vérifié.
    securite=True  : V2, règles de sécurité (limites, zone interdite) en plus.
    """
    print(f"\n[1] Consigne : {consigne}")

    # --- Traducteur (LLM) : sortie non fiable --------------------------------
    print("[2] Traduction par le LLM...")
    brut = traduire(consigne, regle_prompt)
    if "refus" in brut:
        print(f"    Le LLM refuse : {brut['refus']}")
        return {"decision": "REFUS_LLM", "raison": brut["refus"]}
    print("    Plan proposé :")
    afficher_plan(brut)

    # --- Validateur : seul à pouvoir autoriser ---------------------------------
    niveau = "format + sécurité (V2)" if securite else "format seulement (V1)"
    print(f"[3] Validation : {niveau}")
    ok, resultat = valider(brut, depart=drone.position, securite=securite)
    if not ok:
        print(f"    REFUSÉ : {resultat}")
        return {"decision": "REFUS_VALIDATEUR", "raison": resultat, "plan": brut}
    plan = resultat
    print("    Plan accepté")

    if confirmer and input("    Exécuter ce plan ? (o/n) ").strip().lower() != "o":
        print("    Annulé par l'utilisateur.")
        return {"decision": "ANNULE", "plan": plan}

    # --- Exécuteur : seul à parler au drone -----------------------------------
    print("[4] Exécution")
    compte_rendu = await executer(plan, drone)
    return {"decision": "EXECUTE", "plan": plan, "execution": compte_rendu}


async def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    confirmer = "--confirmer" in sys.argv
    securite = "--v1" not in sys.argv
    regle_prompt = "--regle-prompt" in sys.argv
    px4 = "--px4" in sys.argv
    print("Mode :", "V2, validateur complet" if securite else "V1, validateur de format seulement")
    print("Drone :", "PX4 via MAVSDK" if px4 else "faux drone")

    # Avec PX4 : un seul drone pour toute la session (une seule liaison MAVSDK),
    # sa position est lue dans la télémétrie à chaque mission.
    # Avec le faux drone : un drone neuf par mission, qui repart de l'origine.
    drone_px4 = None
    if px4:
        drone_px4 = Px4Drone()
        await drone_px4.connecter()

    if arguments:
        consignes = [" ".join(arguments)]
    else:
        print("Tape une consigne de vol en français (ou q pour quitter).")
        consignes = None

    while True:
        if consignes is not None:
            if not consignes:
                break
            consigne = consignes.pop(0)
        else:
            consigne = input("\n> ").strip()
            if consigne.lower() in ("q", "quit", "exit"):
                break
            if not consigne:
                continue

        if drone_px4 is not None:
            drone = drone_px4
            await drone._lire_position()  # position réelle avant la mission
        else:
            drone = FauxDrone()
            await drone.connecter()

        resume = await mission(consigne, drone, confirmer, securite, regle_prompt)
        enregistrer(consigne, "V2" if securite else "V1", resume, modele=MODELE)
        print(f"\n[5] Résumé : {json.dumps(resume, ensure_ascii=False)}")
        print("    (enregistré dans journal.jsonl)")

    print("\nAu revoir.")


if __name__ == "__main__":
    asyncio.run(main())
