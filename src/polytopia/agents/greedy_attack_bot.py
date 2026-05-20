"""Bot agresivo sin filtros: ataca siempre que puede, incluso suicida.
Util para probar si el oponente sobrevive a ataques irracionales."""

from __future__ import annotations

import random

from polytopia.agents.base import BaseBot
from polytopia.interfaces import Action, ActionType, GameState


class GreedyAttackBot(BaseBot):
    """Estrategia:
    - SIEMPRE ATTACK si esta disponible (sin importar HP propio).
    - CAPTURE si puede.
    - MOVE hacia enemigo.
    - TRAIN si tiene stars.
    - Sin defensa, sin economia.
    """

    def __init__(self, player_id: int, name: str = "greedy_attack", seed: int = 42):
        super().__init__(player_id, name)
        self._rng = random.Random(seed)

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        by_type: dict[ActionType, list[Action]] = {}
        for a in legal_actions:
            by_type.setdefault(a.action_type, []).append(a)

        if ActionType.ATTACK in by_type:
            return self._rng.choice(by_type[ActionType.ATTACK])

        if ActionType.CAPTURE in by_type:
            return self._rng.choice(by_type[ActionType.CAPTURE])

        if ActionType.MOVE in by_type:
            return self._best_move_towards_enemy(state, by_type[ActionType.MOVE])

        if ActionType.TRAIN in by_type:
            return self._rng.choice(by_type[ActionType.TRAIN])

        if ActionType.HARVEST in by_type:
            return self._rng.choice(by_type[ActionType.HARVEST])

        if ActionType.END_TURN in by_type:
            return by_type[ActionType.END_TURN][0]
        return legal_actions[0]

    def _best_move_towards_enemy(
        self, state: GameState, moves: list[Action]
    ) -> Action:
        enemies = [
            u for u in state.units.values()
            if u.owner != self.player_id and u.is_alive
        ]
        if not enemies:
            enemy_cities = [
                c for c in state.cities.values() if c.owner != self.player_id
            ]
            if not enemy_cities:
                return self._rng.choice(moves)
            targets = [c.position for c in enemy_cities]
        else:
            targets = [e.position for e in enemies]

        def min_dist_after(move: Action) -> int:
            if move.target is None:
                return 1_000_000
            return min(move.target.chebyshev_distance(t) for t in targets)

        return min(moves, key=min_dist_after)
