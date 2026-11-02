"""Tests du validateur niveau 2 (règles de sécurité), sans LLM ni clé API.

Lancer avec : python3 test_securite.py
"""

from validateur import valider


def plan(*etapes):
    return {"etapes": list(etapes)}


D = lambda alt: {"action": "DECOLLER", "altitude_m": alt}
A = lambda direction, dist: {"action": "AVANCER", "direction": direction, "distance_m": dist}
T = {"action": "ATTERRIR"}

CAS = [
    # nom, plan, accepté attendu
    ("mission normale", plan(D(5), A("nord", 10), T), True),
    ("s'arrête avant l'hôpital", plan(D(5), A("est", 15), T), True),
    ("contourne par le nord", plan(D(5), A("nord", 25), A("est", 30), T), True),
    ("longe la frontière (marge)", plan(D(5), A("est", 19), T), False),
    ("longe au sud à 4 cm (PX4)", plan(D(10), A("est", 21), T), False, (0.03, -0.04, 0.0)),
    ("attaque : 21 m à l'est", plan(D(10), A("est", 21), T), False),
    ("attaque : 30 m à l'est", plan(D(5), A("est", 30), T), False),
    ("traverse sans s'arrêter", plan(D(5), A("nord", 10), A("est", 50), T), False),
    ("arrive par le nord", plan(D(5), A("nord", 30), A("est", 30), A("sud", 15), T), False),
    ("altitude trop haute", plan(D(50), T), False),
    ("monte trop haut en vol", plan(D(25), A("monter", 10), T), False),
    ("distance trop longue", plan(D(5), A("nord", 60), T), False),
    ("ne décolle pas d'abord", plan(A("nord", 10), T), False),
    ("ne finit pas par atterrir", plan(D(5), A("nord", 10)), False),
    ("décolle deux fois", plan(D(5), D(5), T), False),
    ("format invalide (niveau 1)", plan(D(5), {"action": "EXPLOSER"}, T), False),
]


def main():
    tout_bon = True
    for cas in CAS:
        nom, p, attendu = cas[:3]
        depart = cas[3] if len(cas) > 3 else (0.0, 0.0, 0.0)
        ok, resultat = valider(p, depart=depart)
        bon = ok == attendu
        tout_bon &= bon
        detail = "" if ok else f"-> {resultat}"
        print(f"[{'OK ' if bon else 'ERREUR'}] {nom:30s} accepté={ok!s:5s} attendu={attendu!s:5s} {detail}")
    print("\nTous les tests passent." if tout_bon else "\nCertains tests échouent.")


if __name__ == "__main__":
    main()
