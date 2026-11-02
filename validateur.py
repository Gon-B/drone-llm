"""Validateur : décide si un plan proposé par le LLM peut être exécuté.

Code Python classique, sans IA. Il ne lit jamais la consigne en français,
seulement les valeurs du plan.

Niveau 1 (V1 et V2) : le plan est-il bien écrit ?
    - actions de la liste autorisée uniquement
    - paramètres présents et du bon type (nombres positifs, direction connue)
Niveau 2 (V2)       : le plan est-il autorisé ? (limites, zone interdite) -> étape 5
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, ValidationError

DIRECTIONS = ("nord", "sud", "est", "ouest", "monter", "descendre")


# --- Niveau 1 : le format, décrit avec Pydantic -------------------------------
# Pydantic vérifie automatiquement que chaque étape respecte exactement ce schéma.
# Toute étape inconnue, tout paramètre manquant ou mal typé est refusé.


class Decoller(BaseModel, extra="forbid"):
    action: Literal["DECOLLER"]
    altitude_m: float = Field(gt=0)


class Avancer(BaseModel, extra="forbid"):
    action: Literal["AVANCER"]
    direction: Literal[DIRECTIONS]
    distance_m: float = Field(gt=0)


class Atterrir(BaseModel, extra="forbid"):
    action: Literal["ATTERRIR"]


# Le champ "action" sert de discriminant : Pydantic sait quel modèle appliquer
# à chaque étape, et les messages d'erreur désignent le vrai paramètre fautif.
Etape = Annotated[Union[Decoller, Avancer, Atterrir], Field(discriminator="action")]


class Plan(BaseModel, extra="forbid"):
    etapes: list[Etape] = Field(min_length=1)


def verifier_format(donnees):
    """Niveau 1. Renvoie (True, plan_propre) ou (False, raison).

    `donnees` est ce que le LLM a renvoyé (un dict), considéré comme non fiable.
    `plan_propre` est un dict reconstruit à partir du modèle Pydantic : il ne
    contient que des valeurs vérifiées.
    """
    try:
        plan = Plan.model_validate(donnees)
    except ValidationError as erreur:
        return False, resumer_erreur(erreur)
    return True, plan.model_dump()


# --- Niveau 2 : les règles de sécurité (V2) ----------------------------------
# Écrites par nous, en code. Le LLM ne peut ni les lire ni les modifier.

ALTITUDE_MIN_M = 1
ALTITUDE_MAX_M = 30
DISTANCE_MAX_M = 50
PAS_M = 1.0  # on vérifie un point tous les mètres le long de chaque déplacement

# Zones interdites : (nom, x_min, x_max, y_min, y_max), x vers l'est, y vers le nord.
ZONES_INTERDITES = [
    ("hôpital", 20, 40, 0, 20),
]
# Marge de sécurité autour de chaque zone. La position d'un vrai drone est
# bruitée (quelques cm à quelques m) : sans marge, un trajet qui longe la
# frontière à 4 cm près passe. Découvert en branchant le simulateur PX4.
MARGE_M = 2.0

DEPLACEMENTS = {
    "nord": (0, 1, 0), "sud": (0, -1, 0),
    "est": (1, 0, 0), "ouest": (-1, 0, 0),
    "monter": (0, 0, 1), "descendre": (0, 0, -1),
}


def dans_zone_interdite(x, y):
    """Renvoie le nom de la zone qui contient (x, y), ou None."""
    for nom, x_min, x_max, y_min, y_max in ZONES_INTERDITES:
        if (x_min - MARGE_M <= x <= x_max + MARGE_M
                and y_min - MARGE_M <= y <= y_max + MARGE_M):
            return nom
    return None


def verifier_securite(plan, depart=(0.0, 0.0, 0.0)):
    """Niveau 2. Renvoie (True, None) ou (False, raison).

    Rejoue le plan "sur papier" depuis `depart` et vérifie chaque règle.
    `plan` doit déjà avoir passé verifier_format.
    """
    etapes = plan["etapes"]

    # Règle de logique : décoller d'abord, atterrir à la fin.
    if etapes[0]["action"] != "DECOLLER":
        return False, "le plan doit commencer par DECOLLER"
    if etapes[-1]["action"] != "ATTERRIR":
        return False, "le plan doit finir par ATTERRIR"

    x, y, z = depart
    en_vol = False

    for numero, etape in enumerate(etapes, start=1):
        action = etape["action"]

        if action == "DECOLLER":
            if en_vol:
                return False, f"étape {numero} : DECOLLER alors que le drone est déjà en vol"
            if not ALTITUDE_MIN_M <= etape["altitude_m"] <= ALTITUDE_MAX_M:
                return False, (f"étape {numero} : altitude {etape['altitude_m']:g} m hors limites "
                               f"({ALTITUDE_MIN_M} à {ALTITUDE_MAX_M} m)")
            z = etape["altitude_m"]
            en_vol = True

        elif action == "AVANCER":
            if not en_vol:
                return False, f"étape {numero} : AVANCER alors que le drone est au sol"
            distance = etape["distance_m"]
            if distance > DISTANCE_MAX_M:
                return False, f"étape {numero} : distance {distance:g} m > {DISTANCE_MAX_M} m maximum"
            dx, dy, dz = DEPLACEMENTS[etape["direction"]]

            # On avance mètre par mètre et on vérifie chaque point du trajet,
            # pour détecter une traversée de zone même sans s'y arrêter.
            parcouru = 0.0
            while parcouru < distance:
                pas = min(PAS_M, distance - parcouru)
                x, y, z = x + dx * pas, y + dy * pas, z + dz * pas
                parcouru += pas
                if not ALTITUDE_MIN_M <= z <= ALTITUDE_MAX_M:
                    return False, (f"étape {numero} : altitude {z:g} m hors limites "
                                   f"({ALTITUDE_MIN_M} à {ALTITUDE_MAX_M} m)")
                zone = dans_zone_interdite(x, y)
                if zone:
                    return False, (f"étape {numero} : le trajet entre dans la zone interdite "
                                   f"« {zone} » en ({x:g}, {y:g})")

        elif action == "ATTERRIR":
            if not en_vol:
                return False, f"étape {numero} : ATTERRIR alors que le drone est au sol"
            zone = dans_zone_interdite(x, y)
            if zone:
                return False, f"étape {numero} : atterrissage dans la zone interdite « {zone} »"
            z = 0.0
            en_vol = False

    return True, None


def valider(donnees, depart=(0.0, 0.0, 0.0), securite=True):
    """Point d'entrée unique : niveau 1, puis niveau 2 si `securite` est vrai.

    Renvoie (True, plan_propre) ou (False, raison).
    """
    ok, resultat = verifier_format(donnees)
    if not ok:
        return False, resultat
    plan = resultat
    if securite:
        ok, raison = verifier_securite(plan, depart)
        if not ok:
            return False, raison
    return True, plan


def resumer_erreur(erreur):
    """Transforme l'erreur Pydantic (verbeuse) en une phrase lisible."""
    premiere = erreur.errors()[0]
    # loc ressemble à ('etapes', 1, 'AVANCER', 'direction') : on retire le nom du modèle.
    chemin = ".".join(
        str(p) for p in premiere["loc"] if p not in ("DECOLLER", "AVANCER", "ATTERRIR")
    )
    return f"format invalide ({chemin}) : {premiere['msg']}"
