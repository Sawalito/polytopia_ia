from polytopia.engine.actions import legal_actions
from polytopia.interfaces import (
    ActionType,
    City,
    FogState,
    GameState,
    Position,
    ResourceType,
    TerrainType,
    Tile,
    Unit,
    UnitType,
)

SIZE = 11


def _all_visible_fog() -> dict[Position, FogState]:
    return {Position(x, y): FogState.VISIBLE for x in range(SIZE) for y in range(SIZE)}


def _all_field_tiles() -> dict[Position, Tile]:
    return {
        Position(x, y): Tile(Position(x, y), TerrainType.FIELD)
        for x in range(SIZE)
        for y in range(SIZE)
    }


def _open_state(current_player: int = 0) -> GameState:
    return GameState(
        turn=1,
        current_player=current_player,
        max_turns=30,
        board_size=SIZE,
        tiles=_all_field_tiles(),
        units={},
        cities={},
        stars={0: 0, 1: 0},
        fog={0: _all_visible_fog(), 1: _all_visible_fog()},
    )


def _add_unit(state: GameState, unit: Unit) -> None:
    state.units[unit.unit_id] = unit


def _add_city(state: GameState, city: City) -> None:
    state.cities[city.city_id] = city


def test_warrior_on_open_field_generates_eight_moves():
    state = _open_state()
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    actions = legal_actions(state, 0)
    moves = [a for a in actions if a.action_type == ActionType.MOVE and a.unit_id == 1]
    assert len(moves) == 8
    targets = {a.target for a in moves}
    expected = {Position(5 + dx, 5 + dy)
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx, dy) != (0, 0)}
    assert targets == expected


def test_archer_attacks_at_range_2_warrior_only_at_range_1():
    state = _open_state()
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.ARCHER, position=Position(5, 5)))
    _add_unit(state, Unit(unit_id=2, owner=0, unit_type=UnitType.WARRIOR, position=Position(3, 3)))
    # Enemies:
    #   e10 at (6,5): cheb to archer=1, to warrior=3
    #   e11 at (7,5): cheb to archer=2, to warrior=4
    #   e12 at (4,3): cheb to archer=2, to warrior=1
    _add_unit(state, Unit(unit_id=10, owner=1, unit_type=UnitType.WARRIOR, position=Position(6, 5)))
    _add_unit(state, Unit(unit_id=11, owner=1, unit_type=UnitType.WARRIOR, position=Position(7, 5)))
    _add_unit(state, Unit(unit_id=12, owner=1, unit_type=UnitType.WARRIOR, position=Position(4, 3)))

    actions = legal_actions(state, 0)
    archer_targets = {a.target for a in actions
                      if a.action_type == ActionType.ATTACK and a.unit_id == 1}
    warrior_targets = {a.target for a in actions
                       if a.action_type == ActionType.ATTACK and a.unit_id == 2}

    assert archer_targets == {Position(6, 5), Position(7, 5), Position(4, 3)}
    assert warrior_targets == {Position(4, 3)}


def test_harvest_only_on_resource_tiles():
    state = _open_state()
    state.tiles[Position(5, 5)] = Tile(Position(5, 5), TerrainType.FIELD, ResourceType.FRUIT)
    state.tiles[Position(6, 6)] = Tile(Position(6, 6), TerrainType.FOREST, ResourceType.ANIMAL)
    state.tiles[Position(7, 7)] = Tile(Position(7, 7), TerrainType.FIELD, ResourceType.NONE)

    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    _add_unit(state, Unit(unit_id=2, owner=0, unit_type=UnitType.WARRIOR, position=Position(6, 6)))
    _add_unit(state, Unit(unit_id=3, owner=0, unit_type=UnitType.WARRIOR, position=Position(7, 7)))

    actions = legal_actions(state, 0)
    harvest_units = {a.unit_id for a in actions if a.action_type == ActionType.HARVEST}
    assert harvest_units == {1, 2}


def test_recover_only_if_fresh_and_damaged():
    state = _open_state()
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(5, 5), hp=5))
    _add_unit(state, Unit(unit_id=2, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(6, 6)))  # full hp
    _add_unit(state, Unit(unit_id=3, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(7, 7), hp=5, has_moved=True))
    _add_unit(state, Unit(unit_id=4, owner=0, unit_type=UnitType.WARRIOR,
                          position=Position(8, 8), hp=5, has_attacked=True))

    actions = legal_actions(state, 0)
    recovers = {a.unit_id for a in actions if a.action_type == ActionType.RECOVER}
    assert recovers == {1}


def test_recover_not_available_at_full_hp():
    state = _open_state()
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    actions = legal_actions(state, 0)
    assert [a for a in actions if a.action_type == ActionType.RECOVER] == []


def test_train_requires_stars():
    state = _open_state()
    _add_city(state, City(city_id=1, owner=0, position=Position(5, 5)))

    state.stars[0] = 0
    actions = legal_actions(state, 0)
    assert [a for a in actions if a.action_type == ActionType.TRAIN] == []

    state.stars[0] = 2
    actions = legal_actions(state, 0)
    train_types = {a.unit_type_to_train
                   for a in actions if a.action_type == ActionType.TRAIN}
    assert train_types == {UnitType.WARRIOR}

    state.stars[0] = 3
    actions = legal_actions(state, 0)
    train_types = {a.unit_type_to_train
                   for a in actions if a.action_type == ActionType.TRAIN}
    assert train_types == {UnitType.WARRIOR, UnitType.ARCHER, UnitType.RIDER}


def test_level_up_threshold_is_level_times_5():
    state = _open_state()
    _add_city(state, City(city_id=1, owner=0, position=Position(5, 5), level=1))

    state.stars[0] = 4
    actions = legal_actions(state, 0)
    assert [a for a in actions if a.action_type == ActionType.LEVEL_UP] == []

    state.stars[0] = 5
    actions = legal_actions(state, 0)
    levelups = [a for a in actions if a.action_type == ActionType.LEVEL_UP]
    assert len(levelups) == 1 and levelups[0].city_id == 1

    state.cities[1] = City(city_id=1, owner=0, position=Position(5, 5), level=2)
    state.stars[0] = 9
    actions = legal_actions(state, 0)
    assert [a for a in actions if a.action_type == ActionType.LEVEL_UP] == []

    state.stars[0] = 10
    actions = legal_actions(state, 0)
    assert len([a for a in actions if a.action_type == ActionType.LEVEL_UP]) == 1


def test_end_turn_always_present():
    state = _open_state()
    actions = legal_actions(state, 0)
    assert sum(1 for a in actions if a.action_type == ActionType.END_TURN) == 1

    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    _add_city(state, City(city_id=1, owner=0, position=Position(5, 5)))
    state.stars[0] = 10
    actions = legal_actions(state, 0)
    assert sum(1 for a in actions if a.action_type == ActionType.END_TURN) == 1


def test_move_excludes_unknown_tiles():
    state = _open_state()
    state.fog[0][Position(6, 5)] = FogState.UNKNOWN
    state.fog[0][Position(4, 5)] = FogState.UNKNOWN
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))

    actions = legal_actions(state, 0)
    move_targets = {a.target for a in actions if a.action_type == ActionType.MOVE}
    assert Position(6, 5) not in move_targets
    assert Position(4, 5) not in move_targets
    # SEEN tiles are still valid destinations.
    state.fog[0][Position(5, 4)] = FogState.SEEN
    actions = legal_actions(state, 0)
    move_targets = {a.target for a in actions if a.action_type == ActionType.MOVE}
    assert Position(5, 4) in move_targets


def test_move_excludes_friendly_occupied_tiles():
    state = _open_state()
    _add_unit(state, Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    _add_unit(state, Unit(unit_id=2, owner=0, unit_type=UnitType.WARRIOR, position=Position(6, 5)))
    actions = legal_actions(state, 0)
    move_targets = {a.target for a in actions
                    if a.action_type == ActionType.MOVE and a.unit_id == 1}
    assert Position(6, 5) not in move_targets


def test_no_actions_for_non_current_player():
    state = _open_state(current_player=0)
    _add_unit(state, Unit(unit_id=1, owner=1, unit_type=UnitType.WARRIOR, position=Position(5, 5)))
    assert legal_actions(state, 1) == []
