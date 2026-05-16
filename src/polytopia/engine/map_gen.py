import random

from polytopia.interfaces import (
    City,
    FogState,
    Position,
    ResourceType,
    TerrainType,
    Tile,
    Unit,
)

FIELD_FRACTION = 0.60
FOREST_FRACTION = 0.20
MOUNTAIN_FRACTION = 0.10
WATER_FRACTION = 0.10
FRUIT_CHANCE = 0.30
ANIMAL_CHANCE = 0.30


def get_starting_positions(size: int) -> tuple[Position, Position]:
    return Position(1, 1), Position(size - 2, size - 2)


def _grow_cluster(
    start: Position,
    target_size: int,
    available: set[Position],
    rng: random.Random,
) -> set[Position]:
    cluster: set[Position] = {start}
    frontier: list[Position] = [start]
    while len(cluster) < target_size and frontier:
        idx = rng.randrange(len(frontier))
        current = frontier.pop(idx)
        neighbors = [
            Position(current.x + dx, current.y + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)
        ]
        rng.shuffle(neighbors)
        for n in neighbors:
            if n in available and n not in cluster:
                cluster.add(n)
                frontier.append(n)
                if len(cluster) >= target_size:
                    break
    return cluster


def generate_map(size: int = 11, seed: int = 42) -> dict[Position, Tile]:
    rng = random.Random(seed)
    tiles: dict[Position, Tile] = {}

    border: set[Position] = set()
    interior: set[Position] = set()
    for x in range(size):
        for y in range(size):
            pos = Position(x, y)
            if x == 0 or y == 0 or x == size - 1 or y == size - 1:
                border.add(pos)
            else:
                interior.add(pos)

    for pos in border:
        tiles[pos] = Tile(position=pos, terrain=TerrainType.WATER)

    p0, p1 = get_starting_positions(size)
    starting = {p0, p1}

    n_interior = len(interior)
    # Apply jitter (+/- a couple tiles) to introduce per-seed variation.
    jitter = lambda base: max(0, base + rng.randint(-2, 2))  # noqa: E731
    n_water = jitter(int(WATER_FRACTION * n_interior))
    n_mountain = jitter(int(MOUNTAIN_FRACTION * n_interior))
    n_forest = jitter(int(FOREST_FRACTION * n_interior))

    placeable = interior - starting

    # Grow 1-2 water lakes inside the interior.
    water_positions: set[Position] = set()
    if n_water > 0:
        n_lakes = rng.choice([1, 2])
        if n_lakes == 1:
            lake_sizes = [n_water]
        else:
            half = n_water // 2
            lake_sizes = [half, n_water - half]

        for lake_size in lake_sizes:
            available = placeable - water_positions
            if not available or lake_size <= 0:
                continue
            center = rng.choice(list(available))
            cluster = _grow_cluster(center, lake_size, available, rng)
            water_positions.update(cluster)

    remaining = list(placeable - water_positions)
    rng.shuffle(remaining)

    n_mountain = min(n_mountain, len(remaining))
    mountain_positions = set(remaining[:n_mountain])
    n_forest = min(n_forest, len(remaining) - n_mountain)
    forest_positions = set(remaining[n_mountain : n_mountain + n_forest])

    for pos in interior:
        if pos in water_positions:
            tiles[pos] = Tile(position=pos, terrain=TerrainType.WATER)
        elif pos in mountain_positions:
            tiles[pos] = Tile(position=pos, terrain=TerrainType.MOUNTAIN)
        elif pos in forest_positions:
            resource = ResourceType.ANIMAL if rng.random() < ANIMAL_CHANCE else ResourceType.NONE
            tiles[pos] = Tile(position=pos, terrain=TerrainType.FOREST, resource=resource)
        else:
            if pos in starting:
                resource = ResourceType.NONE
            else:
                resource = ResourceType.FRUIT if rng.random() < FRUIT_CHANCE else ResourceType.NONE
            tiles[pos] = Tile(position=pos, terrain=TerrainType.FIELD, resource=resource)

    return tiles


def initial_fog(
    size: int,
    starting_position: Position,
    vision_range: int = 2,
) -> dict[Position, FogState]:
    fog: dict[Position, FogState] = {}
    for x in range(size):
        for y in range(size):
            pos = Position(x, y)
            if pos.chebyshev_distance(starting_position) <= vision_range:
                fog[pos] = FogState.VISIBLE
            else:
                fog[pos] = FogState.UNKNOWN
    return fog


def update_fog(
    current_fog: dict[Position, FogState],
    units: list[Unit],
    cities: list[City],
    owner: int,
    vision_range: int = 2,
) -> dict[Position, FogState]:
    visible: set[Position] = set()
    sources: list[Position] = []
    for u in units:
        if u.owner == owner and u.is_alive:
            sources.append(u.position)
    for c in cities:
        if c.owner == owner:
            sources.append(c.position)

    for pos in current_fog:
        for src in sources:
            if pos.chebyshev_distance(src) <= vision_range:
                visible.add(pos)
                break

    new_fog: dict[Position, FogState] = {}
    for pos, state in current_fog.items():
        if pos in visible:
            new_fog[pos] = FogState.VISIBLE
        elif state == FogState.VISIBLE:
            new_fog[pos] = FogState.SEEN
        else:
            new_fog[pos] = state
    return new_fog
