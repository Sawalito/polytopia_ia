import json
from pathlib import Path

from polytopia.interfaces import (
    Action,
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


def load_replay(path: str | Path) -> list[dict]:
    """Carga un replay y devuelve la lista de frames deserializados."""
    with open(path) as f:
        data = json.load(f)
    return [
        {
            "action": _deserialize_action(frame["action"]) if frame["action"] else None,
            "state": _deserialize_state(frame["state"]),
        }
        for frame in data["frames"]
    ]


def _deserialize_action(d: dict) -> Action:
    target = Position(d["target"]["x"], d["target"]["y"]) if d.get("target") else None
    unit_type = (
        UnitType[d["unit_type_to_train"]] if d.get("unit_type_to_train") else None
    )
    return Action(
        action_type=ActionType[d["action_type"]],
        unit_id=d.get("unit_id"),
        city_id=d.get("city_id"),
        target=target,
        unit_type_to_train=unit_type,
    )


def _deserialize_state(d: dict) -> GameState:
    tiles = {}
    for key, t in d["tiles"].items():
        x, y = map(int, key.split(","))
        pos = Position(x, y)
        tiles[pos] = Tile(
            position=pos,
            terrain=TerrainType[t["terrain"]],
            resource=ResourceType[t["resource"]],
            has_road=t["has_road"],
        )

    units = {}
    for uid, u in d["units"].items():
        pos = Position(u["position"]["x"], u["position"]["y"])
        units[int(uid)] = Unit(
            unit_id=u["unit_id"],
            owner=u["owner"],
            unit_type=UnitType[u["unit_type"]],
            position=pos,
            hp=u["hp"],
            has_moved=u["has_moved"],
            has_attacked=u["has_attacked"],
        )

    cities = {}
    for cid, c in d["cities"].items():
        pos = Position(c["position"]["x"], c["position"]["y"])
        cities[int(cid)] = City(
            city_id=c["city_id"],
            owner=c["owner"],
            position=pos,
            level=c["level"],
        )

    fog = {}
    for player_key, player_fog_dict in d["fog"].items():
        player_fog = {}
        for pos_key, fs_name in player_fog_dict.items():
            x, y = map(int, pos_key.split(","))
            player_fog[Position(x, y)] = FogState[fs_name]
        fog[int(player_key)] = player_fog

    return GameState(
        turn=d["turn"],
        current_player=d["current_player"],
        max_turns=d["max_turns"],
        board_size=d["board_size"],
        tiles=tiles,
        units=units,
        cities=cities,
        stars={int(k): v for k, v in d["stars"].items()},
        fog=fog,
        game_over=d["game_over"],
        winner=d["winner"],
    )
