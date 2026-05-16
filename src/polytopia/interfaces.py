from dataclasses import dataclass
from enum import Enum, auto


class TerrainType(Enum):
    FIELD = auto()
    FOREST = auto()
    MOUNTAIN = auto()
    WATER = auto()


class ResourceType(Enum):
    NONE = auto()
    FRUIT = auto()
    ANIMAL = auto()


class UnitType(Enum):
    WARRIOR = auto()
    ARCHER = auto()
    RIDER = auto()


class ActionType(Enum):
    MOVE = auto()
    ATTACK = auto()
    HARVEST = auto()
    CAPTURE = auto()
    TRAIN = auto()
    LEVEL_UP = auto()
    RECOVER = auto()
    END_TURN = auto()


class FogState(Enum):
    UNKNOWN = auto()
    SEEN = auto()
    VISIBLE = auto()


UNIT_STATS: dict[UnitType, dict[str, float | int]] = {
    UnitType.WARRIOR: {"max_hp": 10, "attack": 2.0, "defense": 2.0,
                       "movement": 1, "range": 1, "cost": 2},
    UnitType.ARCHER:  {"max_hp": 10, "attack": 2.0, "defense": 1.0,
                       "movement": 1, "range": 2, "cost": 3},
    UnitType.RIDER:   {"max_hp": 10, "attack": 2.0, "defense": 1.0,
                       "movement": 2, "range": 1, "cost": 3},
}

COMBAT_MULTIPLIER = 4.5
CITY_DEFENSE_BONUS = 1.5
RECOVER_HP_OWN_TERRITORY = 4
RECOVER_HP_OUTSIDE = 2
CITY_TERRITORY_RADIUS = 1


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def manhattan_distance(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def chebyshev_distance(self, other: "Position") -> int:
        return max(abs(self.x - other.x), abs(self.y - other.y))


@dataclass
class Tile:
    position: Position
    terrain: TerrainType
    resource: ResourceType = ResourceType.NONE
    has_road: bool = False

    @property
    def is_passable(self) -> bool:
        return self.terrain not in (TerrainType.WATER, TerrainType.MOUNTAIN)


@dataclass
class Unit:
    unit_id: int
    owner: int
    unit_type: UnitType
    position: Position
    hp: int | None = None
    has_moved: bool = False
    has_attacked: bool = False

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.max_hp

    @property
    def max_hp(self) -> int:
        return int(UNIT_STATS[self.unit_type]["max_hp"])

    @property
    def attack(self) -> float:
        return float(UNIT_STATS[self.unit_type]["attack"])

    @property
    def defense(self) -> float:
        return float(UNIT_STATS[self.unit_type]["defense"])

    @property
    def movement(self) -> int:
        return int(UNIT_STATS[self.unit_type]["movement"])

    @property
    def range(self) -> int:
        return int(UNIT_STATS[self.unit_type]["range"])

    @property
    def cost(self) -> int:
        return int(UNIT_STATS[self.unit_type]["cost"])

    @property
    def is_alive(self) -> bool:
        return self.hp is not None and self.hp > 0


@dataclass
class City:
    city_id: int
    owner: int
    position: Position
    level: int = 1

    @property
    def stars_per_turn(self) -> int:
        return self.level


@dataclass
class Action:
    action_type: ActionType
    unit_id: int | None = None
    city_id: int | None = None
    target: Position | None = None
    unit_type_to_train: UnitType | None = None

    def __repr__(self) -> str:
        parts = [self.action_type.name]
        if self.unit_id is not None:
            parts.append(f"unit={self.unit_id}")
        if self.city_id is not None:
            parts.append(f"city={self.city_id}")
        if self.target is not None:
            parts.append(f"target=({self.target.x},{self.target.y})")
        if self.unit_type_to_train is not None:
            parts.append(f"train={self.unit_type_to_train.name}")
        return f"Action({', '.join(parts)})"


@dataclass
class GameState:
    turn: int
    current_player: int
    max_turns: int
    board_size: int
    tiles: dict[Position, Tile]
    units: dict[int, Unit]
    cities: dict[int, City]
    stars: dict[int, int]
    fog: dict[int, dict[Position, FogState]]
    game_over: bool = False
    winner: int | None = None

    def units_of(self, player: int) -> list[Unit]:
        return [u for u in self.units.values() if u.owner == player]

    def cities_of(self, player: int) -> list[City]:
        return [c for c in self.cities.values() if c.owner == player]

    def unit_at(self, position: Position) -> Unit | None:
        for u in self.units.values():
            if u.position == position and u.is_alive:
                return u
        return None

    def tile_at(self, position: Position) -> Tile | None:
        return self.tiles.get(position)

    def is_own_territory(self, player: int, position: Position) -> bool:
        for city in self.cities_of(player):
            if city.position.chebyshev_distance(position) <= CITY_TERRITORY_RADIUS:
                return True
        return False
