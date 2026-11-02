"""Drones : le faux drone (tests sans simulateur) et le drone PX4 (MAVSDK).

Les deux offrent exactement la même interface, l'exécuteur ne voit pas la différence :
    - attributs  : position (x, y, z) en mètres, en_vol (bool)
    - méthodes   : connecter(), decoller(altitude_m), avancer(direction, distance_m), atterrir()

Repère du projet : origine = point de départ, x vers l'est, y vers le nord, z vers le haut.
PX4 utilise le repère NED (Nord, Est, Bas) : la conversion se fait ici, et seulement ici.
"""

import asyncio
import math
import time
import warnings

# La bibliothèque mavsdk (API gRPC classique) affiche un avertissement de renommage
# à l'import : sans conséquence pour nous, on le masque pour garder un terminal lisible.
warnings.filterwarnings("ignore", category=FutureWarning, message=".*mavsdk.*")

# Pour chaque direction : de combien bouge (x, y, z) pour 1 mètre parcouru.
DIRECTIONS = {
    "nord": (0, 1, 0),
    "sud": (0, -1, 0),
    "est": (1, 0, 0),
    "ouest": (-1, 0, 0),
    "monter": (0, 0, 1),
    "descendre": (0, 0, -1),
}


class ErreurDrone(Exception):
    """Ordre physiquement impossible (ou panne du drone)."""


def formater(position):
    """(30.0, 10.0, 5.0) -> '(30, 10, 5)'"""
    return "(" + ", ".join(f"{valeur:g}" for valeur in position) + ")"


class FauxDrone:
    """Fait semblant de voler : garde la position en mémoire et l'affiche."""

    DUREE_MOUVEMENT_S = 1.0  # durée fixe de chaque mouvement
    NB_AFFICHAGES = 4  # positions intermédiaires affichées pendant un mouvement

    def __init__(self):
        self.position = (0.0, 0.0, 0.0)
        self.en_vol = False

    async def connecter(self):
        print("[drone] Faux drone prêt, posé en (0, 0, 0)")

    async def decoller(self, altitude_m):
        if self.en_vol:
            raise ErreurDrone("le drone est déjà en vol")
        if altitude_m <= 0:
            raise ErreurDrone("l'altitude de décollage doit être positive")
        print(f"[drone] Décollage vers {altitude_m:g} m...")
        x, y, _ = self.position
        await self._deplacer_vers((x, y, altitude_m))
        self.en_vol = True

    async def avancer(self, direction, distance_m):
        if not self.en_vol:
            raise ErreurDrone("impossible d'avancer : le drone est au sol")
        if direction not in DIRECTIONS:
            raise ErreurDrone(f"direction inconnue : {direction}")
        dx, dy, dz = DIRECTIONS[direction]
        x, y, z = self.position
        cible = (x + dx * distance_m, y + dy * distance_m, z + dz * distance_m)
        if cible[2] <= 0:
            raise ErreurDrone("descendre jusqu'au sol est impossible, il faut ATTERRIR")
        print(f"[drone] Déplacement de {distance_m:g} m vers {direction}...")
        await self._deplacer_vers(cible)

    async def atterrir(self):
        if not self.en_vol:
            raise ErreurDrone("le drone est déjà au sol")
        print("[drone] Atterrissage...")
        x, y, _ = self.position
        await self._deplacer_vers((x, y, 0.0))
        self.en_vol = False
        print("[drone] Posé.")

    async def _deplacer_vers(self, cible):
        """Avance progressivement vers la cible en affichant la position."""
        depart = self.position
        for i in range(1, self.NB_AFFICHAGES + 1):
            await asyncio.sleep(self.DUREE_MOUVEMENT_S / self.NB_AFFICHAGES)
            avancement = i / self.NB_AFFICHAGES  # 0.25, 0.5, 0.75, 1.0
            self.position = tuple(
                round(d + (c - d) * avancement, 2) for d, c in zip(depart, cible)
            )
            print(f"         position {formater(self.position)}")


# =============================================================================
# Drone PX4 via MAVSDK (simulateur Gazebo à Cergy, ou vrai drone plus tard)
# =============================================================================


def vers_ned(position):
    """Repère projet (x est, y nord, z haut) -> NED PX4 (nord, est, bas)."""
    x, y, z = position
    return (y, x, -z)


def depuis_ned(nord, est, bas):
    """NED PX4 -> repère projet."""
    return (est, nord, -bas)


class Px4Drone:
    """Pilote un drone PX4 (simulé ou réel) avec MAVSDK-Python.

    Décollage et atterrissage : mode Action de PX4.
    Déplacements : mode Offboard, en envoyant une position cible NED.
    """

    ADRESSE_DEFAUT = "udpin://0.0.0.0:14540"  # port sur lequel PX4 SITL émet du MAVLink
    TOLERANCE_M = 0.3  # on considère la cible atteinte à 30 cm près...
    VITESSE_ARRET_MS = 0.3  # ...et quand le drone est presque immobile (sinon il dépasse)
    DELAI_MAX_S = 120  # au-delà, on considère le mouvement en échec
    PERIODE_AFFICHAGE_S = 1.0

    def __init__(self, adresse=ADRESSE_DEFAUT):
        # Import ici : le faux drone doit marcher même si mavsdk n'est pas installé.
        from mavsdk import System

        self.adresse = adresse
        self.drone = System()
        self.position = (0.0, 0.0, 0.0)
        self.en_vol = False

    # --- lecture de la télémétrie ---------------------------------------------

    async def _lire_position(self):
        """Met à jour self.position et renvoie (position, vitesse en m/s)."""
        async for pv in self.drone.telemetry.position_velocity_ned():
            p, v = pv.position, pv.velocity
            self.position = tuple(round(x, 2) for x in depuis_ned(p.north_m, p.east_m, p.down_m))
            vitesse = math.sqrt(v.north_m_s**2 + v.east_m_s**2 + v.down_m_s**2)
            return self.position, vitesse

    async def _attendre_cible(self, cible, description):
        """Attend que le drone soit à TOLERANCE_M de la cible ET presque immobile."""
        debut = time.monotonic()
        dernier_affichage = 0.0
        while True:
            pos, vitesse = await self._lire_position()
            distance = math.dist(pos, cible)
            if time.monotonic() - dernier_affichage >= self.PERIODE_AFFICHAGE_S:
                print(f"         position {formater(pos)}")
                dernier_affichage = time.monotonic()
            if distance <= self.TOLERANCE_M and vitesse <= self.VITESSE_ARRET_MS:
                print(f"         position {formater(pos)}  (cible atteinte)")
                return
            if time.monotonic() - debut > self.DELAI_MAX_S:
                raise ErreurDrone(f"{description} : cible non atteinte après {self.DELAI_MAX_S} s")
            await asyncio.sleep(0.2)

    # --- interface commune -----------------------------------------------------

    async def connecter(self):
        print(f"[drone] Connexion à PX4 sur {self.adresse}...")
        await self.drone.connect(system_address=self.adresse)
        async for etat in self.drone.core.connection_state():
            if etat.is_connected:
                break
        print("[drone] Connecté. Attente du GPS et de la position de départ...")
        async for sante in self.drone.telemetry.health():
            if sante.is_global_position_ok and sante.is_home_position_ok:
                break
        await self._lire_position()
        async for en_air in self.drone.telemetry.in_air():
            self.en_vol = en_air
            break
        print(f"[drone] PX4 prêt, position {formater(self.position)}")

    async def decoller(self, altitude_m):
        if self.en_vol:
            raise ErreurDrone("le drone est déjà en vol")
        if altitude_m <= 0:
            raise ErreurDrone("l'altitude de décollage doit être positive")
        print(f"[drone] Armement et décollage vers {altitude_m:g} m...")
        (x, y, _), _ = await self._lire_position()
        await self.drone.action.arm()
        await self.drone.action.takeoff()
        self.en_vol = True
        # PX4 décolle à son altitude par défaut (~2,5 m). On attend d'être en vol
        # stabilisé, puis on rejoint l'altitude demandée en Offboard, comme pour
        # un déplacement : c'est plus fiable que le paramètre d'altitude de décollage.
        await self._attendre_vol_stabilise()
        await self._aller_en_offboard((x, y, float(altitude_m)), "décollage")

    async def _attendre_vol_stabilise(self):
        """Attend que le drone ait quitté le sol et soit presque immobile (fin du takeoff)."""
        debut = time.monotonic()
        while True:
            (_, _, z), vitesse = await self._lire_position()
            if z > 1.0 and vitesse <= self.VITESSE_ARRET_MS:
                return
            if time.monotonic() - debut > self.DELAI_MAX_S:
                raise ErreurDrone("décollage : le drone ne s'est pas stabilisé en vol")
            await asyncio.sleep(0.2)

    async def _aller_en_offboard(self, cible, description):
        """Envoie le drone vers `cible` (repère projet) en mode Offboard et attend l'arrivée."""
        from mavsdk.offboard import OffboardError, PositionNedYaw

        nord, est, bas = vers_ned(cible)
        consigne = PositionNedYaw(nord, est, bas, 0.0)  # cap 0 = face au nord
        # Offboard exige une consigne AVANT de démarrer le mode.
        await self.drone.offboard.set_position_ned(consigne)
        try:
            await self.drone.offboard.start()
        except OffboardError as erreur:
            raise ErreurDrone(f"PX4 refuse le mode Offboard : {erreur._result.result}")
        try:
            await self._attendre_cible(cible, description)
        finally:
            # On sort d'Offboard entre deux ordres : PX4 passe en maintien de position.
            await self.drone.offboard.stop()

    async def avancer(self, direction, distance_m):
        if not self.en_vol:
            raise ErreurDrone("impossible d'avancer : le drone est au sol")
        if direction not in DIRECTIONS:
            raise ErreurDrone(f"direction inconnue : {direction}")
        dx, dy, dz = DIRECTIONS[direction]
        (x, y, z), _ = await self._lire_position()
        cible = (x + dx * distance_m, y + dy * distance_m, z + dz * distance_m)
        if cible[2] <= 0:
            raise ErreurDrone("descendre jusqu'au sol est impossible, il faut ATTERRIR")
        print(f"[drone] Déplacement de {distance_m:g} m vers {direction}...")
        await self._aller_en_offboard(cible, f"déplacement vers {direction}")

    async def atterrir(self):
        if not self.en_vol:
            raise ErreurDrone("le drone est déjà au sol")
        print("[drone] Atterrissage...")
        await self.drone.action.land()
        async for en_air in self.drone.telemetry.in_air():
            if not en_air:
                break
        self.en_vol = False
        await self._lire_position()
        print(f"[drone] Posé en {formater(self.position)}.")
