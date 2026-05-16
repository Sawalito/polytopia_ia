import io

from rich.console import Console

from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import (
    Action,
    ActionType,
    FogState,
    Position,
    UnitType,
)
from polytopia.renderers import terminal as term


def _capture_console() -> Console:
    return Console(file=io.StringIO(), width=160, record=True, force_terminal=False)


def test_render_state_debug_does_not_crash():
    state = create_initial_state(seed=42)
    console = _capture_console()
    term.render_state(state, viewer_player=None, console=console)
    output = console.export_text()
    assert "Turn 1/30" in output
    assert "P0" in output
    assert "P1" in output


def test_render_state_with_fog_does_not_crash():
    state = create_initial_state(seed=42)
    console = _capture_console()
    term.render_state(state, viewer_player=0, console=console)
    output = console.export_text()
    # A far-from-start tile should show as '?' in player 0's view.
    assert "?" in output


def test_unknown_tile_renders_as_question_mark():
    state = create_initial_state(seed=42)
    far = Position(8, 8)  # cheb from (1,1) is 7 > 2
    assert state.fog[0][far] == FogState.UNKNOWN
    text = term._cell_text(state, far, viewer_player=0)
    assert text.plain == "?"


def test_unit_uppercase_for_player_0():
    state = create_initial_state(seed=42)
    unit0 = state.units[0]
    assert unit0.owner == 0 and unit0.unit_type == UnitType.WARRIOR
    state.fog[0][unit0.position] = FogState.VISIBLE
    text = term._cell_text(state, unit0.position, viewer_player=0)
    assert text.plain == "W"


def test_unit_lowercase_for_player_1():
    state = create_initial_state(seed=42)
    unit1 = state.units[1]
    assert unit1.owner == 1 and unit1.unit_type == UnitType.WARRIOR
    state.fog[1][unit1.position] = FogState.VISIBLE
    text = term._cell_text(state, unit1.position, viewer_player=1)
    assert text.plain == "w"


def test_prompt_human_action_returns_selected(monkeypatch):
    actions = [
        Action(action_type=ActionType.END_TURN),
        Action(action_type=ActionType.MOVE, unit_id=1, target=Position(0, 0)),
        Action(action_type=ActionType.ATTACK, unit_id=1, target=Position(2, 2)),
    ]
    feed = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(feed))
    chosen = term.prompt_human_action(actions, console=_capture_console())
    assert chosen.action_type == ActionType.MOVE
    assert chosen.unit_id == 1
    assert chosen.target == Position(0, 0)


def test_prompt_human_action_retries_on_invalid(monkeypatch):
    actions = [
        Action(action_type=ActionType.END_TURN),
        Action(action_type=ActionType.MOVE, unit_id=1, target=Position(0, 0)),
    ]
    feed = iter(["", "foo", "99", "0"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(feed))
    chosen = term.prompt_human_action(actions, console=_capture_console())
    assert chosen.action_type == ActionType.END_TURN
