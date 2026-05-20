"""Bot economico: prioriza HARVEST, LEVEL_UP, TRAIN. Solo ataca si tiene
clara ventaja numerica. Optimiza para crecimiento sostenido."""

from __future__ import annotations

import random

from polytopia.agents.base import BaseBot
from polytopia.interfaces import Action, ActionType, GameState, ResourceType


class EconomicBot(BaseBot):
    """Estrategia:
    - Maximiza HARVEST.
    - LEVEL_UP cities cuando puede.
    - TRAIN cuando hay stars sobrantes.
    - ATTACK solo si tiene 2x mas unidades que el oponente.
    - Mueve unidades hacia recursos no recolectados.
    """

    ATTACK_RATIO_THRESHOLD = 2.0

    def __init__(self, player_id: int, name: str = "economic", seed: int = 42):
        super().__init__(player_id, name)
        self._rng = random.Random(seed)

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        by_type: dict[ActionType, list[Action]] = {}
        for a in legal_actions:
            by_type.setdefault(a.action_type, []).append(a)

        if ActionType.HARVEST in by_type:
            return self._rng.choice(by_type[ActionType.HARVEST])

        if ActionType.LEVEL_UP in by_type:
            return self._rng.choice(by_type[ActionType.LEVEL_UP])

        if ActionType.TRAIN in by_type:
            return self._rng.choice(by_type[ActionType.TRAIN])

        my_units = [
            u for u in state.units.values()
            if u.owner == self.player_id and u.is_alive
        ]
        opp_units = [
            u for u in state.units.values()
            if u.owner != self.player_id and u.is_alive
        ]

        if ActionType.ATTACK in by_type and opp_units:
            ratio = len(my_units) / max(len(opp_units), 1)
            if ratio >= self.ATTACK_RATIO_THRESHOLD:
                return self._rng.choice(by_type[ActionType.ATTACK])

        if ActionType.CAPTURE in by_type:
            return self._rng.choice(by_type[ActionType.CAPTURE])

        if ActionType.MOVE in by_type:
            return self._move_to_resources(state, by_type[ActionType.MOVE])

        if ActionType.END_TURN in by_type:
            return by_type[ActionType.END_TURN][0]
        return legal_actions[0]

    def _move_to_resources(self, state: GameState, moves: list[Action]) -> Action:
        resource_positions = [
            pos for pos, tile in state.tiles.items()
            if tile.resource != ResourceType.NONE
        ]
        if not resource_positions:
            return self._rng.choice(moves)

        def dist_to_resource(move: Action) -> int:
            if move.target is None:
                return 1_000_000
            return min(
                move.target.chebyshev_distance(rp) for rp in resource_positions
            )

        return min(moves, key=dist_to_resource)
