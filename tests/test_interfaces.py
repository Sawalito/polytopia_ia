from polytopia.interfaces import (
    UNIT_STATS,
    City,
    GameState,
    Position,
    Tile,
    TerrainType,
    Unit,
    UnitType,
)


def test_warrior_stats_match_unit_stats():
    s = UNIT_STATS[UnitType.WARRIOR]
    assert s == {"max_hp": 10, "attack": 2.0, "defense": 2.0,
                 "movement": 1, "range": 1, "cost": 2}


def test_archer_stats_match_unit_stats():
    s = UNIT_STATS[UnitType.ARCHER]
    assert s == {"max_hp": 10, "attack": 2.0, "defense": 1.0,
                 "movement": 1, "range": 2, "cost": 3}


def test_rider_stats_match_unit_stats():
    s = UNIT_STATS[UnitType.RIDER]
    assert s == {"max_hp": 10, "attack": 2.0, "defense": 1.0,
                 "movement": 2, "range": 1, "cost": 3}


def test_unit_max_hp_accessible_and_hp_initialized():
    for ut in (UnitType.WARRIOR, UnitType.ARCHER, UnitType.RIDER):
        unit = Unit(unit_id=1, owner=0, unit_type=ut, position=Position(0, 0))
        assert unit.max_hp == 10
        assert unit.hp == unit.max_hp


def test_unit_attack_returns_float():
    unit = Unit(unit_id=1, owner=0, unit_type=UnitType.WARRIOR, position=Position(0, 0))
    assert unit.attack == 2.0
    assert isinstance(unit.attack, float)


def _state_with_city(owner: int, pos: Position) -> GameState:
    city = City(city_id=1, owner=owner, position=pos)
    return GameState(
        turn=0, current_player=0, max_turns=30, board_size=11,
        tiles={}, units={}, cities={1: city},
        stars={0: 0, 1: 0}, fog={0: {}, 1: {}},
    )


def test_is_own_territory_adjacent_to_city():
    state = _state_with_city(owner=0, pos=Position(5, 5))
    assert state.is_own_territory(0, Position(5, 5)) is True
    assert state.is_own_territory(0, Position(6, 5)) is True
    assert state.is_own_territory(0, Position(4, 6)) is True
    assert state.is_own_territory(0, Position(6, 6)) is True


def test_is_own_territory_far_from_city():
    state = _state_with_city(owner=0, pos=Position(5, 5))
    assert state.is_own_territory(0, Position(7, 7)) is False
    assert state.is_own_territory(0, Position(0, 0)) is False
    assert state.is_own_territory(1, Position(5, 5)) is False


def test_is_passable_field_and_forest():
    assert Tile(Position(0, 0), TerrainType.FIELD).is_passable is True
    assert Tile(Position(0, 0), TerrainType.FOREST).is_passable is True


def test_is_passable_water_and_mountain():
    assert Tile(Position(0, 0), TerrainType.WATER).is_passable is False
    assert Tile(Position(0, 0), TerrainType.MOUNTAIN).is_passable is False
