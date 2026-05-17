import random

from polytopia.agents.base import BaseBot
from polytopia.engine.rules import apply_action
from polytopia.interfaces import (
    Action,
    ActionType,
    FogState,
    GameState,
    Position,
    UnitType,
)


class HeuristicBot(BaseBot):
    """HeuristicBot v2: greedy 1-ply con presion ofensiva.

    Cambios principales vs v1:
    - Termino de distancia ofensiva: premia acercar unidades a cities enemigas
      conocidas (visibles o vistas previamente).
    - Bonus directos por ATTACK y CAPTURE para que esas acciones dominen MOVE
      cuando aparecen como legales.
    - Penalty por terminar el turno con unidades fresh (sin moverse ni atacar).
    - Fallback de exploracion cuando no se conoce ninguna city enemiga.
    """

    # === Pesos base ===
    W_CITY = 20.0
    W_UNIT = 5.0
    W_HP = 0.5
    W_STARS = 1.0

    # === Pesos tacticos ===
    W_SHIELDED_ARCHER = 4.0
    W_EXPOSED_ARCHER = 6.0

    # === Pesos de presion ofensiva (nuevos en v2) ===
    # Agregado en v3: W_DISTANCE sube de 0.3 a 0.8 porque fase 1 mostro que
    # el 100% de las perdidas exhiben el patron lost_never_reached_enemy
    # (avg_turn_reached_enemy_radius 12.5 en wins vs 27.0 en losses).
    W_DISTANCE = 0.8              # Premia menor distancia a city enemiga.
    W_CAPTURE_BONUS = 50.0        # Capturar city es excelente, mas que W_CITY.
    W_ATTACK_BONUS = 8.0          # Cualquier ataque que conecte vale puntos.
    W_IDLE_PENALTY = 2.0          # Penaliza END_TURN con unidades fresh.

    # === Fase de juego ===
    LATE_GAME_TURN = 15
    LATE_GAME_STARS_WEIGHT = 0.2

    # === Jitter para desempates ===
    JITTER_MAX = 0.01

    def __init__(self, player_id: int, name: str = "heuristic_v3", seed: int = 42):
        super().__init__(player_id, name)
        self._rng = random.Random(seed)

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        best_action = legal_actions[0]
        best_score = float("-inf")

        for action in legal_actions:
            new_state = apply_action(state, action)
            score = self.evaluate(new_state)

            # Bonus inmediatos por tipo de accion. Esto evita que ATTACK sea
            # descartado cuando el cambio en evaluate() es pequeno, y obliga
            # al bot a salir del spawn penalizando END_TURN con units fresh.
            score += self._action_type_bonus(state, action)

            # Jitter para desempate determinista.
            score += self._rng.uniform(0, self.JITTER_MAX)

            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def evaluate(self, state: GameState) -> float:
        """Evaluacion del estado desde la perspectiva de self.player_id."""
        me = self.player_id
        opp = 1 - me

        # === 1. Economia ===
        stars_diff = state.stars[me] - state.stars[opp]

        cities_me_list = [c for c in state.cities.values() if c.owner == me]
        cities_opp_list = [c for c in state.cities.values() if c.owner == opp]
        cities_diff = len(cities_me_list) - len(cities_opp_list)

        # === 2. Ejercito ===
        units_me = [u for u in state.units.values() if u.owner == me and u.is_alive]
        units_opp = [u for u in state.units.values() if u.owner == opp and u.is_alive]
        units_diff = len(units_me) - len(units_opp)

        hp_me = sum(u.hp for u in units_me)
        hp_opp = sum(u.hp for u in units_opp)
        hp_diff = hp_me - hp_opp

        # === 3. Formaciones Archer ===
        shielded_archers, exposed_archers = self._count_archer_formations(units_me, units_opp)

        # === 4. Presion ofensiva ===
        offensive_score = self._compute_offensive_pressure(state, units_me, cities_opp_list)

        # === 5. Fase de juego ===
        w_stars = (
            self.LATE_GAME_STARS_WEIGHT if state.turn > self.LATE_GAME_TURN
            else self.W_STARS
        )

        # === 6. Score final ===
        return (
            w_stars * stars_diff
            + self.W_CITY * cities_diff
            + self.W_UNIT * units_diff
            + self.W_HP * hp_diff
            + self.W_SHIELDED_ARCHER * shielded_archers
            - self.W_EXPOSED_ARCHER * exposed_archers
            + offensive_score
        )

    # ------------------------------------------------------------------ helpers

    def _action_type_bonus(self, state_before: GameState, action: Action) -> float:
        """Bonus que aplica al SCORE DE LA ACCION, no al estado resultante.

        Razon: algunas acciones son siempre buenas (CAPTURE) o casi siempre buenas
        (ATTACK con dano significativo), aunque el cambio en evaluate sea pequeno.

        Penaliza END_TURN si hay unidades fresh con acciones utiles disponibles.
        """
        me = self.player_id

        if action.action_type == ActionType.CAPTURE:
            return self.W_CAPTURE_BONUS

        if action.action_type == ActionType.ATTACK:
            return self.W_ATTACK_BONUS

        if action.action_type == ActionType.END_TURN:
            # Penalizar terminar turno si quedan unidades fresh.
            fresh_units = sum(
                1 for u in state_before.units.values()
                if u.owner == me and u.is_alive
                and not u.has_moved
                and not u.has_attacked
            )
            return -self.W_IDLE_PENALTY * fresh_units

        return 0.0

    def _compute_offensive_pressure(
        self,
        state: GameState,
        units_me: list,
        cities_opp: list,
    ) -> float:
        """Premia tener unidades cerca de cities enemigas conocidas.

        Considera:
        - Solo cities que self.player_id conoce (VISIBLE o SEEN). Si no conoce
          ninguna, fallback a exploracion hacia el centro del mapa.
        - Para cada unidad propia, encuentra la city enemiga conocida mas cercana.
        - Suma negativa de distancias, ponderada por W_DISTANCE.

        Resultado: score sube cuando MOVE acerca al enemigo, baja cuando se aleja.
        """
        if not units_me or not cities_opp:
            return 0.0

        me = self.player_id
        known_cities = [
            c for c in cities_opp
            if me in state.fog
            and c.position in state.fog[me]
            and state.fog[me][c.position] in (FogState.VISIBLE, FogState.SEEN)
        ]

        if not known_cities:
            # Sin info del enemigo, premiamos exploracion: acercarse al centro.
            center = Position(state.board_size // 2, state.board_size // 2)
            total_distance = sum(
                u.position.chebyshev_distance(center) for u in units_me
            )
            return -self.W_DISTANCE * total_distance * 0.5

        total_distance = 0
        for u in units_me:
            min_dist = min(
                u.position.chebyshev_distance(c.position)
                for c in known_cities
            )
            total_distance += min_dist

        return -self.W_DISTANCE * total_distance

    def _count_archer_formations(
        self,
        units_me: list,
        units_opp: list,
    ) -> tuple[int, int]:
        """Cuenta archers shielded vs expuestos. (Sin cambios respecto a v1.)"""
        melee_positions = [
            u.position for u in units_me
            if u.unit_type in (UnitType.WARRIOR, UnitType.RIDER)
        ]
        enemy_positions = [u.position for u in units_opp]

        shielded = 0
        exposed = 0

        for u in units_me:
            if u.unit_type != UnitType.ARCHER:
                continue

            is_exposed = any(
                u.position.chebyshev_distance(ep) <= 1
                for ep in enemy_positions
            )

            if is_exposed:
                exposed += 1
            else:
                is_shielded = any(
                    u.position.chebyshev_distance(mp) <= 1
                    for mp in melee_positions
                )
                if is_shielded:
                    shielded += 1

        return shielded, exposed
