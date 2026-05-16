from polytopia.engine.rules import (
    apply_action,
    check_game_over,
    end_turn_tick,
    resolve_combat,
)
from polytopia.interfaces import (
    Action,
    ActionType,
    City,
    FogState,
    GameState,
    Position,
    TerrainType,
    Tile,
    Unit,
    UnitType,
)

SIZE = 11


def _all_visible_fog() -> dict[Position, FogState]:
    return {Position(x, y): FogState.VISIBLE for x in range(SIZE) for y in range(SIZE)}


def _empty_state(current_player: int = 0, turn: int = 1, max_turns: int = 30) -> GameState:
    tiles = {
        Position(x, y): Tile(Position(x, y), TerrainType.FIELD)
        for x in range(SIZE) for y in range(SIZE)
    }
    return GameState(
        turn=turn, current_player=current_player, max_turns=max_turns,
        board_size=SIZE, tiles=tiles, units={}, cities={},
        stars={0: 0, 1: 0}, fog={0: _all_visible_fog(), 1: _all_visible_fog()},
    )


# --- Combat formula tests ---------------------------------------------------


def test_combat_warrior_vs_warrior_no_bonus_balanced():
    attacker = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5))
    defender = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR, position=Position(6, 5))
    atk, ret = resolve_combat(attacker, defender, defender_terrain_bonus=1.0)
    # raw 4.5 / 4.5; tolerate ±1 around the rounded value
    assert 4 <= atk <= 5
    assert 4 <= ret <= 5


def test_combat_archer_at_range_2_takes_no_retaliation():
    archer = Unit(unit_id=1, owner=0, unit_type=UnitType.ARCHER, position=Position(5, 5))
    warrior = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR, position=Position(7, 5))
    atk, ret = resolve_combat(archer, warrior, defender_terrain_bonus=1.0)
    assert atk > 0
    assert ret == 0  # Warrior.range = 1 < chebyshev distance = 2


def test_combat_city_defense_bonus_shifts_balance():
    attacker = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5))
    defender = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR, position=Position(6, 5))
    base_atk, base_ret = resolve_combat(attacker, defender, defender_terrain_bonus=1.0)
    bonus_atk, bonus_ret = resolve_combat(attacker, defender, defender_terrain_bonus=1.5)
    # raw bonus_atk = (2/5)*2*4.5 = 3.6 -> 4; raw bonus_ret = (3/5)*2*4.5 = 5.4 -> 5
    assert bonus_atk == 4
    assert bonus_ret == 5
    assert bonus_atk <= base_atk
    assert bonus_ret >= base_ret


def test_combat_wounded_attacker_deals_less_takes_more():
    attacker = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                    position=Position(5, 5), hp=2)
    defender = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR, position=Position(6, 5))
    atk, ret = resolve_combat(attacker, defender, defender_terrain_bonus=1.0)
    # attack_force=0.4, defense_force=2.0, total=2.4
    # atk = round((0.4/2.4)*2*4.5) = round(1.5) = 2 (banker)
    # ret = round((2.0/2.4)*2*4.5) = round(7.5) = 8 (banker)
    assert atk <= 2
    assert ret >= 7


def test_combat_defender_dies_no_retaliation():
    attacker = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5))
    defender = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR,
                    position=Position(6, 5), hp=1)
    atk, ret = resolve_combat(attacker, defender, defender_terrain_bonus=1.0)
    assert atk >= 1
    assert ret == 0


# --- RECOVER tests ----------------------------------------------------------


def test_recover_outside_territory_heals_2():
    state = _empty_state()
    state.units[1] = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(5, 5), hp=4)
    new_state = apply_action(state, Action(action_type=ActionType.RECOVER, unit_id=1))
    assert new_state.units[1].hp == 6


def test_recover_inside_territory_heals_4():
    state = _empty_state()
    state.cities[1] = City(city_id=1, owner=0, position=Position(5, 5))
    state.units[1] = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(5, 5), hp=4)
    new_state = apply_action(state, Action(action_type=ActionType.RECOVER, unit_id=1))
    assert new_state.units[1].hp == 8


def test_recover_caps_at_max_hp():
    state = _empty_state()
    state.cities[1] = City(city_id=1, owner=0, position=Position(5, 5))
    state.units[1] = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(5, 5), hp=9)
    new_state = apply_action(state, Action(action_type=ActionType.RECOVER, unit_id=1))
    assert new_state.units[1].hp == 10


# --- end_turn_tick tests ----------------------------------------------------


def test_end_turn_tick_resets_flags_for_player_only():
    state = _empty_state(current_player=0)
    state.units[1] = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(5, 5),
                          has_moved=True, has_attacked=True)
    state.units[2] = Unit(unit_id=2, owner=1, unit_type=UnitType.WARRIOR,
                          position=Position(8, 8),
                          has_moved=True, has_attacked=True)
    end_turn_tick(state, 0)
    assert state.units[1].has_moved is False
    assert state.units[1].has_attacked is False
    assert state.units[2].has_moved is True
    assert state.units[2].has_attacked is True


def test_end_turn_tick_adds_stars_per_city_level():
    state = _empty_state(current_player=0)
    state.cities[10] = City(city_id=10, owner=0, position=Position(5, 5), level=2)
    state.cities[11] = City(city_id=11, owner=0, position=Position(3, 3), level=1)
    state.cities[12] = City(city_id=12, owner=1, position=Position(8, 8), level=3)
    state.stars[0] = 0
    state.stars[1] = 0
    end_turn_tick(state, 0)
    assert state.stars[0] == 3  # 2 + 1
    assert state.stars[1] == 0


# --- check_game_over tests --------------------------------------------------


def test_game_over_when_player_has_no_cities():
    state = _empty_state()
    state.cities[1] = City(city_id=1, owner=1, position=Position(5, 5))
    over, winner = check_game_over(state)
    assert over is True
    assert winner == 1


def test_game_over_at_max_turns_decided_by_score():
    state = _empty_state(turn=30, max_turns=30)
    # Player 0: city level 3 (30) + 2 units + 5 stars = 37
    # Player 1: city level 1 (10) + 0 units + 0 stars = 10
    state.cities[1] = City(city_id=1, owner=0, position=Position(5, 5), level=3)
    state.cities[2] = City(city_id=2, owner=1, position=Position(8, 8), level=1)
    state.units[10] = Unit(unit_id=10, owner=0, unit_type=UnitType.WARRIOR,
                           position=Position(5, 5))
    state.units[11] = Unit(unit_id=11, owner=0, unit_type=UnitType.WARRIOR,
                           position=Position(4, 5))
    state.stars[0] = 5
    over, winner = check_game_over(state)
    assert over is True
    assert winner == 0
