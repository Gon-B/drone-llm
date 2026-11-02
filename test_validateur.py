"""Tests du validateur niveau 1, sans LLM ni clé API.

Lancer avec : python3 test_validateur.py
On simule des réponses du LLM, correctes ou piégées, et on vérifie la décision.
"""

from validateur import verifier_format

CAS = [
    ("plan correct", {"etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "AVANCER", "direction": "nord", "distance_m": 10},
        {"action": "ATTERRIR"},
    ]}, True),
    ("action inventée", {"etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "COUPER_MOTEURS"},
    ]}, False),
    ("direction inconnue", {"etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "AVANCER", "direction": "nord-est", "distance_m": 10},
    ]}, False),
    ("distance négative", {"etapes": [
        {"action": "DECOLLER", "altitude_m": 5},
        {"action": "AVANCER", "direction": "nord", "distance_m": -10},
    ]}, False),
    ("paramètre manquant", {"etapes": [
        {"action": "DECOLLER"},
    ]}, False),
    ("paramètre en trop", {"etapes": [
        {"action": "ATTERRIR", "vitesse": 100},
    ]}, False),
    ("distance en texte", {"etapes": [
        {"action": "DECOLLER", "altitude_m": "cinq"},
    ]}, False),
    ("plan vide", {"etapes": []}, False),
    ("pas un plan du tout", {"bonjour": "monde"}, False),
]


def main():
    tout_bon = True
    for nom, donnees, attendu in CAS:
        ok, resultat = verifier_format(donnees)
        statut = "OK " if ok == attendu else "ERREUR"
        if ok != attendu:
            tout_bon = False
        detail = "" if ok else f"-> {resultat}"
        print(f"[{statut}] {nom:22s} accepté={ok!s:5s} attendu={attendu!s:5s} {detail}")
    print("\nTous les tests passent." if tout_bon else "\nCertains tests échouent.")


if __name__ == "__main__":
    main()
