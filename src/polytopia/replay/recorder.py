import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

from polytopia.interfaces import Action, GameState, Position


class GameRecorder:
    """Graba un game loop frame por frame en formato JSON."""

    def __init__(self):
        self.frames: list[dict] = []

    def record_frame(self, state: GameState, action: Action | None) -> None:
        """Snapshot del estado y la acción que llevó a él (None en el frame 0)."""
        self.frames.append(
            {
                "action": _serialize(action) if action is not None else None,
                "state": _serialize_state(state),
            }
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"frames": self.frames}, f, indent=2)

    def n_frames(self) -> int:
        return len(self.frames)


def _serialize(obj):
    """Serialización recursiva: dataclasses, enums, Position, dicts, listas."""
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.name
    if isinstance(obj, Position):
        return {"x": obj.x, "y": obj.y}
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(_serialize(k)): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    return obj


def _serialize_state(state: GameState) -> dict:
    """Serializa GameState con keys de tiles y fog como strings 'x,y'."""
    return {
        "turn": state.turn,
        "current_player": state.current_player,
        "max_turns": state.max_turns,
        "board_size": state.board_size,
        "game_over": state.game_over,
        "winner": state.winner,
        "stars": {str(k): v for k, v in state.stars.items()},
        "tiles": {
            f"{pos.x},{pos.y}": {
                "terrain": tile.terrain.name,
                "resource": tile.resource.name,
                "has_road": tile.has_road,
            }
            for pos, tile in state.tiles.items()
        },
        "units": {
            str(uid): {
                "unit_id": u.unit_id,
                "owner": u.owner,
                "unit_type": u.unit_type.name,
                "position": {"x": u.position.x, "y": u.position.y},
                "hp": u.hp,
                "has_moved": u.has_moved,
                "has_attacked": u.has_attacked,
            }
            for uid, u in state.units.items()
        },
        "cities": {
            str(cid): {
                "city_id": c.city_id,
                "owner": c.owner,
                "position": {"x": c.position.x, "y": c.position.y},
                "level": c.level,
            }
            for cid, c in state.cities.items()
        },
        "fog": {
            str(player): {
                f"{pos.x},{pos.y}": fs.name for pos, fs in player_fog.items()
            }
            for player, player_fog in state.fog.items()
        },
    }
