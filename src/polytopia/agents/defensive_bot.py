"""Bot defensivo: prioriza acumular stars, fortificar, entrenar muchas
unidades, y solo atacar enemigos en su propio territorio.
Replica el comportamiento que ganaba con el reward viejo."""

from __future__ import annotations

import random

from polytopia.agents.base import BaseBot
from polytopia.interfaces import Action, ActionType, GameState


class DefensiveBot(BaseBot):
    """Estrategia:
    - Mantiene unidades cerca de cities propias.
    - Solo ataca si el enemigo esta a chebyshev <= 3 de city propia.
    - Hoarda stars y entrena cuando puede.
    - Ignora cities enemigas (no expande).
    """

    DEFENSE_RADIUS = 3

    def __init__(self, player_id: int, name: str = "defensive", seed: int = 42):
        super().__init__(player_id, name)
        self._rng = random.Random(seed)

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        by_type: dict[ActionType, list[Action]] = {}
        for a in legal_actions:
            by_type.setdefault(a.action_type, []).append(a)

        my_city_positions = [
            c.position for c in state.cities.values() if c.owner == self.player_id
        ]

        if ActionType.ATTACK in by_type:
            for atk in by_type[ActionType.ATTACK]:
                if atk.target is None:
                    continue
                if any(
                    atk.target.chebyshev_distance(cp) <= self.DEFENSE_RADIUS
                    for cp in my_city_positions
                ):
                    return atk

        if ActionType.TRAIN in by_type:
            return self._rng.choice(by_type[ActionType.TRAIN])

        if ActionType.HARVEST in by_type:
            return self._rng.choice(by_type[ActionType.HARVEST])

        if ActionType.LEVEL_UP in by_type:
            return self._rng.choice(by_type[ActionType.LEVEL_UP])

        if ActionType.MOVE in by_type and my_city_positions:
            def dist_to_my_city(move: Action) -> int:
                if move.target is None:
                    return 1_000_000
                return min(
                    move.target.chebyshev_distance(cp) for cp in my_city_positions
                )

            return min(by_type[ActionType.MOVE], key=dist_to_my_city)

        if ActionType.END_TURN in by_type:
            return by_type[ActionType.END_TURN][0]
        return legal_actions[0]
