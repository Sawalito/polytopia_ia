from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from polytopia.interfaces import (
    Action,
    FogState,
    GameState,
    Position,
    ResourceType,
    TerrainType,
    UnitType,
)

CONSOLE = Console()

TERRAIN_CHAR = {
    TerrainType.FIELD: ".",
    TerrainType.FOREST: "T",
    TerrainType.MOUNTAIN: "^",
    TerrainType.WATER: "~",
}

RESOURCE_CHAR = {
    ResourceType.FRUIT: "F",
    ResourceType.ANIMAL: "A",
}

UNIT_CHAR = {
    UnitType.WARRIOR: "W",
    UnitType.ARCHER: "A",
    UnitType.RIDER: "R",
}

PLAYER_COLOR = {0: "cyan", 1: "magenta"}


def _cell_text(state: GameState, pos: Position, viewer_player: int | None) -> Text:
    fog_state = (
        state.fog[viewer_player].get(pos, FogState.UNKNOWN)
        if viewer_player is not None
        else FogState.VISIBLE
    )

    if fog_state == FogState.UNKNOWN:
        return Text("?", style="white on grey23")

    tile = state.tile_at(pos)
    if tile is None:
        return Text(" ")

    char = TERRAIN_CHAR.get(tile.terrain, "?")
    style = "white"

    if tile.resource in RESOURCE_CHAR:
        char = RESOURCE_CHAR[tile.resource]
        style = "yellow"

    city_here = next((c for c in state.cities.values() if c.position == pos), None)
    if city_here is not None:
        char = "C" if city_here.owner == 0 else "c"
        style = PLAYER_COLOR[city_here.owner]

    # Units only show on currently VISIBLE tiles (fog-of-war).
    if fog_state == FogState.VISIBLE:
        unit_here = state.unit_at(pos)
        if unit_here is not None:
            base = UNIT_CHAR[unit_here.unit_type]
            char = base if unit_here.owner == 0 else base.lower()
            style = PLAYER_COLOR[unit_here.owner]

    if fog_state == FogState.SEEN:
        style = f"dim {style}"

    return Text(char, style=style)


def render_state(
    state: GameState,
    viewer_player: int | None = None,
    console: Console | None = None,
) -> None:
    out = console or CONSOLE
    size = state.board_size

    header = Table.grid(padding=(0, 2))
    header.add_column()
    header.add_column()
    header.add_column()
    header.add_row(
        Text(f"Turn {state.turn}/{state.max_turns}", style="bold"),
        Text(f"Current: P{state.current_player}",
             style=PLAYER_COLOR[state.current_player]),
        Text("(fog: P{})".format(viewer_player) if viewer_player is not None else "(debug)",
             style="dim"),
    )
    for pid in (0, 1):
        units_count = sum(1 for u in state.units.values() if u.owner == pid and u.is_alive)
        cities_count = sum(1 for c in state.cities.values() if c.owner == pid)
        line = Text()
        line.append(f"P{pid}: ", style=PLAYER_COLOR[pid])
        line.append(
            f"{state.stars[pid]} stars, {units_count} units, {cities_count} cities"
        )
        header.add_row(line, Text(""), Text(""))

    out.print(Panel(header, title="Polytopia AI", border_style="bright_black"))

    grid = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 0))
    grid.add_column(" ", justify="right")
    for x in range(size):
        grid.add_column(str(x % 10), justify="center")
    for y in range(size):
        row: list = [Text(str(y % 10), style="bold dim")]
        for x in range(size):
            row.append(_cell_text(state, Position(x, y), viewer_player))
        grid.add_row(*row)
    out.print(grid)


def render_action_menu(actions: list[Action], console: Console | None = None) -> None:
    out = console or CONSOLE
    table = Table(title="Legal Actions", border_style="bright_black")
    table.add_column("Idx", justify="right", style="bold")
    table.add_column("Type")
    table.add_column("Details")
    for idx, action in enumerate(actions):
        parts: list[str] = []
        if action.unit_id is not None:
            parts.append(f"unit={action.unit_id}")
        if action.city_id is not None:
            parts.append(f"city={action.city_id}")
        if action.target is not None:
            parts.append(f"target=({action.target.x},{action.target.y})")
        if action.unit_type_to_train is not None:
            parts.append(f"train={action.unit_type_to_train.name}")
        table.add_row(str(idx), action.action_type.name, ", ".join(parts))
    out.print(table)


def prompt_human_action(
    actions: list[Action],
    console: Console | None = None,
) -> Action:
    out = console or CONSOLE
    render_action_menu(actions, console=out)
    while True:
        raw = input(f"Choose action [0-{len(actions) - 1}]: ")
        try:
            idx = int(raw.strip())
            if 0 <= idx < len(actions):
                return actions[idx]
        except ValueError:
            pass
        out.print("[red]Invalid choice, try again.[/red]")
