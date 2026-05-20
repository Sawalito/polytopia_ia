"""Features compartidas entre HeuristicBot y DQN. Garantiza que ambos
agentes operan en el mismo espacio de representacion para comparacion
directa."""

from __future__ import annotations

import numpy as np

from polytopia.engine.rules import apply_action
from polytopia.interfaces import (
    Action,
    ActionType,
    FogState,
    GameState,
    Position,
    UnitType,
)

N_FEATURES = 14

ACTION_TYPE_INDICES = {
    ActionType.MOVE: 0,
    ActionType.ATTACK: 1,
    ActionType.HARVEST: 2,
    ActionType.RECOVER: 3,
    ActionType.CAPTURE: 4,
    ActionType.TRAIN: 5,
    ActionType.LEVEL_UP: 6,
    ActionType.END_TURN: 7,
}
N_ACTION_TYPES = len(ACTION_TYPE_INDICES)


def extract_state_features(state: GameState, player: int) -> np.ndarray:
    opp = 1 - player
    stars_diff = (state.stars[player] - state.stars[opp]) / 20.0

    cities_me = sum(1 for c in state.cities.values() if c.owner == player)
    cities_opp = sum(1 for c in state.cities.values() if c.owner == opp)
    cities_diff = (cities_me - cities_opp) / 3.0

    units_me = [u for u in state.units.values() if u.owner == player and u.is_alive]
    units_opp = [u for u in state.units.values() if u.owner == opp and u.is_alive]
    units_diff = (len(units_me) - len(units_opp)) / 5.0
    hp_diff = (sum(u.hp for u in units_me) - sum(u.hp for u in units_opp)) / 50.0

    shielded, exposed = _count_archer_formations(units_me, units_opp)
    shielded_n = shielded / 3.0
    exposed_n = exposed / 3.0

    min_dist_norm = _min_distance_to_known_enemy_city(state, player, units_me, opp)
    turn_progress = state.turn / max(state.max_turns, 1)
    cities_me_abs = cities_me / 3.0
    fresh_units = sum(
        1 for u in units_me if not u.has_moved and not u.has_attacked
    ) / 5.0
    n_units_me = len(units_me) / 5.0
    stars_me_abs = state.stars[player] / 30.0
    hp_me_total = sum(u.hp for u in units_me) / 50.0
    has_ready_attacker = float(any(
        u.hp >= u.max_hp * 0.7 and not u.has_attacked for u in units_me
    ))

    return np.array([
        stars_diff, cities_diff, units_diff, hp_diff,
        shielded_n, exposed_n,
        min_dist_norm, turn_progress,
        cities_me_abs, fresh_units, n_units_me,
        stars_me_abs, hp_me_total, has_ready_attacker,
    ], dtype=np.float32)


def extract_action_features(action: Action) -> np.ndarray:
    vec = np.zeros(N_ACTION_TYPES, dtype=np.float32)
    if action.action_type in ACTION_TYPE_INDICES:
        vec[ACTION_TYPE_INDICES[action.action_type]] = 1.0
    return vec


def extract_state_action_features(
    state: GameState, action: Action, player: int,
) -> np.ndarray:
    state_before = extract_state_features(state, player)
    state_after = extract_state_features(apply_action(state, action), player)
    action_vec = extract_action_features(action)
    return np.concatenate([state_before, state_after, action_vec])


FEATURE_DIM = N_FEATURES * 2 + N_ACTION_TYPES


def _count_archer_formations(units_me, units_opp):
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
            u.position.chebyshev_distance(ep) <= 1 for ep in enemy_positions
        )
        if is_exposed:
            exposed += 1
        else:
            is_shielded = any(
                u.position.chebyshev_distance(mp) <= 1 for mp in melee_positions
            )
            if is_shielded:
                shielded += 1
    return shielded, exposed


def _min_distance_to_known_enemy_city(state, player, units_me, opp):
    if not units_me:
        return 0.0
    enemy_cities = [c for c in state.cities.values() if c.owner == opp]
    if not enemy_cities:
        return 0.0
    known_cities = [
        c for c in enemy_cities
        if player in state.fog
        and c.position in state.fog[player]
        and state.fog[player][c.position] in (FogState.VISIBLE, FogState.SEEN)
    ]
    if not known_cities:
        center = Position(state.board_size // 2, state.board_size // 2)
        avg_dist = float(np.mean([
            u.position.chebyshev_distance(center) for u in units_me
        ]))
        return avg_dist / state.board_size
    min_dist = min(
        u.position.chebyshev_distance(c.position)
        for u in units_me
        for c in known_cities
    )
    return min_dist / state.board_size
