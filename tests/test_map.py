from collections import Counter

from polytopia.engine.map_gen import (
    generate_map,
    get_starting_positions,
    initial_fog,
    update_fog,
)
from polytopia.interfaces import (
    City,
    FogState,
    Position,
    TerrainType,
    Unit,
    UnitType,
)


def test_map_size():
    size = 11
    tiles = generate_map(size, seed=42)
    assert len(tiles) == size * size
    for x in range(size):
        for y in range(size):
            assert Position(x, y) in tiles


def test_borders_are_water():
    size = 11
    tiles = generate_map(size, seed=42)
    for i in range(size):
        assert tiles[Position(0, i)].terrain == TerrainType.WATER
        assert tiles[Position(size - 1, i)].terrain == TerrainType.WATER
        assert tiles[Position(i, 0)].terrain == TerrainType.WATER
        assert tiles[Position(i, size - 1)].terrain == TerrainType.WATER


def test_terrain_distribution_approximate():
    size = 11
    tiles = generate_map(size, seed=42)
    counts = Counter(t.terrain for t in tiles.values())
    interior = (size - 2) ** 2  # 81
    # FIELD should dominate the interior (~60%).
    assert 0.4 * interior <= counts[TerrainType.FIELD] <= 0.85 * interior
    # FOREST roughly 20% of interior.
    assert 0.05 * interior <= counts[TerrainType.FOREST] <= 0.40 * interior
    # MOUNTAIN roughly 10% of interior.
    assert counts[TerrainType.MOUNTAIN] <= 0.30 * interior


def test_starting_positions_field_and_separated():
    size = 11
    tiles = generate_map(size, seed=42)
    p0, p1 = get_starting_positions(size)
    assert tiles[p0].terrain == TerrainType.FIELD
    assert tiles[p1].terrain == TerrainType.FIELD
    assert p0.manhattan_distance(p1) >= size - 3


def test_initial_fog_center_visible_rest_unknown():
    size = 11
    start = Position(1, 1)
    fog = initial_fog(size, start, vision_range=2)
    assert len(fog) == size * size
    assert fog[start] == FogState.VISIBLE
    assert fog[Position(2, 2)] == FogState.VISIBLE
    assert fog[Position(3, 3)] == FogState.VISIBLE  # chebyshev = 2
    assert fog[Position(4, 4)] == FogState.UNKNOWN  # chebyshev = 3
    assert fog[Position(9, 9)] == FogState.UNKNOWN


def test_update_fog_adds_visible_around_new_unit():
    size = 11
    start = Position(1, 1)
    fog = initial_fog(size, start, vision_range=2)

    unit = Unit(unit_id=0, owner=0, unit_type=UnitType.WARRIOR, position=Position(8, 8))
    city = City(city_id=0, owner=0, position=start)
    new_fog = update_fog(fog, [unit], [city], owner=0, vision_range=2)

    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            p = Position(8 + dx, 8 + dy)
            if 0 <= p.x < size and 0 <= p.y < size:
                assert new_fog[p] == FogState.VISIBLE, f"expected VISIBLE at {p}"

    # City area still VISIBLE.
    assert new_fog[start] == FogState.VISIBLE
    # A faraway tile not adjacent to anyone stays UNKNOWN.
    assert new_fog[Position(5, 1)] == FogState.UNKNOWN


def test_update_fog_visible_becomes_seen_when_no_one_watches():
    size = 11
    start = Position(5, 5)
    fog = initial_fog(size, start, vision_range=2)
    # Move all observers far away; previously VISIBLE tiles must become SEEN.
    unit = Unit(unit_id=0, owner=0, unit_type=UnitType.WARRIOR, position=Position(1, 1))
    new_fog = update_fog(fog, [unit], [], owner=0, vision_range=2)
    assert new_fog[Position(5, 5)] == FogState.SEEN
    assert new_fog[Position(6, 6)] == FogState.SEEN
    # New unit's area is VISIBLE.
    assert new_fog[Position(1, 1)] == FogState.VISIBLE


def test_same_seed_yields_same_map():
    a = generate_map(11, seed=42)
    b = generate_map(11, seed=42)
    for pos in a:
        assert a[pos].terrain == b[pos].terrain
        assert a[pos].resource == b[pos].resource

    c = generate_map(11, seed=99)
    differs = any(a[pos].terrain != c[pos].terrain for pos in a)
    assert differs
