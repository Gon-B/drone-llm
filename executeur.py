"""Exécuteur : seul module qui parle au drone.

Il reçoit un plan (déjà vérifié), exécute les étapes une par une
en attendant la fin de chacune, et fait atterrir le drone en cas d'erreur.
Il ne prend aucune décision : il obéit au plan.
"""

from drone import ErreurDrone, formater


def decrire(etape):
    """Texte lisible d'une étape, pour l'affichage.

    Sert aussi à afficher le plan brut du LLM AVANT validation : il peut donc
    manquer des champs ou en contenir d'étranges. On n'accède à rien sans filet.
    """
    if not isinstance(etape, dict):
        return f"?? {etape!r}"

    def nombre(cle):
        v = etape.get(cle, "?")
        return f"{v:g}" if isinstance(v, (int, float)) else str(v)

    action = etape.get("action", "??")
    if action == "DECOLLER":
        return f"DECOLLER à {nombre('altitude_m')} m"
    if action == "AVANCER":
        return f"AVANCER de {nombre('distance_m')} m vers {etape.get('direction', '?')}"
    if action == "ATTERRIR":
        return "ATTERRIR"
    return f"?? {etape!r}"


async def executer(plan, drone):
    """Exécute le plan sur le drone et renvoie un compte-rendu (dict)."""
    etapes = plan["etapes"]

    for numero, etape in enumerate(etapes, start=1):
        print(f"\n[exécuteur] Étape {numero}/{len(etapes)} : {decrire(etape)}")
        try:
            action = etape["action"]
            if action == "DECOLLER":
                await drone.decoller(etape["altitude_m"])
            elif action == "AVANCER":
                await drone.avancer(etape["direction"], etape["distance_m"])
            elif action == "ATTERRIR":
                await drone.atterrir()
            else:
                # Normalement impossible : le validateur a déjà vérifié le format.
                raise ErreurDrone(f"action inconnue : {action}")

        except ErreurDrone as erreur:
            print(f"[exécuteur] ÉCHEC à l'étape {numero} : {erreur}")
            await atterrissage_urgence(drone)
            return {
                "statut": "ECHEC",
                "etape": numero,
                "raison": str(erreur),
                "position_finale": drone.position,
            }

    print(f"\n[exécuteur] Mission terminée, position finale {formater(drone.position)}")
    return {"statut": "SUCCES", "position_finale": drone.position}


async def atterrissage_urgence(drone):
    """Un drone ne doit jamais rester en l'air sans consigne."""
    if drone.en_vol:
        print("[exécuteur] Atterrissage d'urgence.")
        await drone.atterrir()
