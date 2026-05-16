import copy

from polytopia.engine.map_gen import update_fog
from polytopia.interfaces import (
    CITY_DEFENSE_BONUS,
    COMBAT_MULTIPLIER,
    RECOVER_HP_OUTSIDE,
    RECOVER_HP_OWN_TERRITORY,
    UNIT_STATS,
    Action,
    ActionType,
    GameState,
    ResourceType,
    Unit,
    UnitType,
)

VISION_RANGE = 2


def resolve_combat(
    attacker: Unit,
    defender: Unit,
    defender_terrain_bonus: float,
) -> tuple[int, int]:
    """Polytopia damage formula.

    Returns (damage_to_defender, retaliation_to_attacker). Retaliation is 0
    when the defender dies or the attacker is outside the defender's range.
    """
    attack_force = attacker.attack * (attacker.hp / attacker.max_hp)
    defense_force = (
        defender.defense * (defender.hp / defender.max_hp) * defender_terrain_bonus
    )
    total_damage = attack_force + defense_force

    if total_damage == 0:
        return (0, 0)

    attack_result = round(
        (attack_force / total_damage) * attacker.attack * COMBAT_MULTIPLIER
    )

    distance = attacker.position.chebyshev_distance(defender.position)
    defender_survives = (defender.hp - attack_result) > 0
    attacker_in_defender_range = distance <= defender.range

    if defender_survives and attacker_in_defender_range:
        defense_result = round(
            (defense_force / total_damage) * defender.defense * COMBAT_MULTIPLIER
        )
    else:
        defense_result = 0

    return (attack_result, defense_result)


def compute_defender_bonus(state: GameState, defender: Unit) -> float:
    for city in state.cities.values():
        if city.position == defender.position and city.owner == defender.owner:
            return CITY_DEFENSE_BONUS
    return 1.0


def _refresh_fog(state: GameState, player: int) -> None:
    own_units = [u for u in state.units.values() if u.owner == player]
    own_cities = [c for c in state.cities.values() if c.owner == player]
    state.fog[player] = update_fog(
        state.fog[player], own_units, own_cities, owner=player, vision_range=VISION_RANGE
    )


def end_turn_tick(state: GameState, player: int) -> GameState:
    for unit in state.units.values():
        if unit.owner == player:
            unit.has_moved = False
            unit.has_attacked = False
    for city in state.cities.values():
        if city.owner == player:
            state.stars[player] += city.level
    _refresh_fog(state, player)
    return state


def _score(state: GameState, player: int) -> int:
    city_score = sum(c.level * 10 for c in state.cities.values() if c.owner == player)
    unit_count = sum(1 for u in state.units.values() if u.owner == player and u.is_alive)
    return city_score + unit_count + state.stars[player]


def check_game_over(state: GameState) -> tuple[bool, int | None]:
    cities_0 = [c for c in state.cities.values() if c.owner == 0]
    cities_1 = [c for c in state.cities.values() if c.owner == 1]
    if not cities_0 and not cities_1:
        return (True, None)
    if not cities_0:
        return (True, 1)
    if not cities_1:
        return (True, 0)
    if state.turn >= state.max_turns:
        s0 = _score(state, 0)
        s1 = _score(state, 1)
        if s0 > s1:
            return (True, 0)
        if s1 > s0:
            return (True, 1)
        return (True, None)
    return (False, None)


def apply_action(state: GameState, action: Action) -> GameState:
    s = copy.deepcopy(state)
    player = s.current_player

    if action.action_type == ActionType.MOVE:
        unit = s.units[action.unit_id]
        unit.position = action.target
        unit.has_moved = True
        _refresh_fog(s, player)

    elif action.action_type == ActionType.ATTACK:
        attacker = s.units[action.unit_id]
        defender = s.unit_at(action.target)
        if defender is None:
            return s
        bonus = compute_defender_bonus(s, defender)
        initial_distance = attacker.position.chebyshev_distance(defender.position)
        attack_dmg, retaliation = resolve_combat(attacker, defender, bonus)
        defender.hp -= attack_dmg
        attacker.has_attacked = True
        defender_died = defender.hp <= 0
        if defender_died:
            del s.units[defender.unit_id]
            if (
                attacker.unit_type in (UnitType.WARRIOR, UnitType.RIDER)
                and initial_distance == 1
            ):
                attacker.position = action.target
        if retaliation > 0:
            attacker.hp -= retaliation
            if attacker.hp <= 0:
                del s.units[attacker.unit_id]
        _refresh_fog(s, player)

    elif action.action_type == ActionType.HARVEST:
        unit = s.units[action.unit_id]
        tile = s.tile_at(unit.position)
        s.stars[player] += 2
        if tile is not None:
            tile.resource = ResourceType.NONE
        unit.has_moved = True
        unit.has_attacked = True

    elif action.action_type == ActionType.RECOVER:
        unit = s.units[action.unit_id]
        heal = (
            RECOVER_HP_OWN_TERRITORY
            if s.is_own_territory(player, unit.position)
            else RECOVER_HP_OUTSIDE
        )
        unit.hp = min(unit.max_hp, unit.hp + heal)
        unit.has_moved = True
        unit.has_attacked = True

    elif action.action_type == ActionType.CAPTURE:
        city = s.cities[action.city_id]
        city.owner = player
        unit = s.units[action.unit_id]
        unit.has_attacked = True
        _refresh_fog(s, player)

    elif action.action_type == ActionType.TRAIN:
        new_id = max(s.units.keys(), default=-1) + 1
        new_unit = Unit(
            unit_id=new_id,
            owner=player,
            unit_type=action.unit_type_to_train,
            position=action.target,
            has_moved=True,
            has_attacked=True,
        )
        s.units[new_id] = new_unit
        cost = UNIT_STATS[action.unit_type_to_train]["cost"]
        s.stars[player] -= int(cost)

    elif action.action_type == ActionType.LEVEL_UP:
        city = s.cities[action.city_id]
        cost = city.level * 5
        city.level += 1
        s.stars[player] -= cost

    elif action.action_type == ActionType.END_TURN:
        end_turn_tick(s, player)
        s.current_player = 1 - s.current_player
        if s.current_player == 0:
            s.turn += 1
        game_over, winner = check_game_over(s)
        s.game_over = game_over
        s.winner = winner

    return s
