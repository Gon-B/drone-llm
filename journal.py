"""Journal d'audit : une ligne JSON par mission, dans journal.jsonl.

Chaque ligne garde : l'heure, la consigne, ce que le LLM a proposé, la décision
du validateur (et pourquoi), ce qui a été exécuté. Les refus sont notés aussi.

Pourquoi ? Après un incident, pouvoir répondre à : qui a demandé quoi,
qu'a proposé l'IA, pourquoi ça a été accepté ou refusé.
Format JSON Lines : lisible par un programme (statistiques, rejeu), une ligne par
événement, on ajoute à la fin sans jamais réécrire le fichier.
"""

import json
from datetime import datetime
from pathlib import Path

FICHIER = Path(__file__).parent / "journal.jsonl"


def enregistrer(consigne, mode, resume, modele=None):
    """Ajoute une ligne au journal. `resume` est le dict renvoyé par mission()."""
    ligne = {
        "heure": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,  # "V1" ou "V2"
        "modele": modele,
        "consigne": consigne,
        "decision": resume.get("decision"),
        "raison": resume.get("raison"),
        "plan": resume.get("plan"),
        "execution": resume.get("execution"),
    }
    with FICHIER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


def lire():
    """Renvoie toutes les lignes du journal (liste de dicts)."""
    if not FICHIER.exists():
        return []
    with FICHIER.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def resume_statistiques():
    """Petit bilan : nombre de missions par décision."""
    compte = {}
    for ligne in lire():
        compte[ligne["decision"]] = compte.get(ligne["decision"], 0) + 1
    return compte


if __name__ == "__main__":
    # python3 journal.py : affiche le journal de façon lisible
    for ligne in lire():
        print(f"{ligne['heure']}  [{ligne['mode']}]  {ligne['decision']:17s} {ligne['consigne'][:60]}")
        if ligne.get("raison"):
            print(f"{'':22s}raison : {ligne['raison']}")
    print("\nBilan :", resume_statistiques())
