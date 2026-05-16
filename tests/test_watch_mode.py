import io

from rich.console import Console

from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import WatchConfig, _format_action, run_game
from polytopia.interfaces import Action, ActionType, Position, UnitType
from polytopia.renderers.terminal import render_separator, render_state


def _capture_console() -> Console:
    return Console(file=io.StringIO(), width=160, record=True, force_terminal=False)


def test_watch_disabled_runs_silently_like_before(capsys):
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state, watch=WatchConfig(enabled=False))
    captured = capsys.readouterr()
    # Silent mode must not print anything during the game.
    assert captured.out == ""
    assert result["winner"] in (None, 0, 1)
    assert result["final_turn"] >= 1


def test_watch_none_defaults_to_silent(capsys):
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result_default = run_game(bot0, bot1, state)
    captured = capsys.readouterr()
    assert captured.out == ""
    # And the silent-mode result matches an explicit WatchConfig(enabled=False) run.
    state2 = create_initial_state(seed=42)
    result_explicit = run_game(
        RandomBot(player_id=0, seed=1),
        RandomBot(player_id=1, seed=2),
        state2,
        watch=WatchConfig(enabled=False),
    )
    assert result_default["winner"] == result_explicit["winner"]
    assert result_default["final_turn"] == result_explicit["final_turn"]
    assert result_default["n_actions_p0"] == result_explicit["n_actions_p0"]
    assert result_default["n_actions_p1"] == result_explicit["n_actions_p1"]


def test_run_game_returns_action_log_keys():
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state)
    assert "action_log_p0" in result
    assert "action_log_p1" in result
    assert isinstance(result["action_log_p0"], list)
    assert isinstance(result["action_log_p1"], list)


def test_action_log_matches_action_counts():
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state)
    assert len(result["action_log_p0"]) == result["n_actions_p0"]
    assert len(result["action_log_p1"]) == result["n_actions_p1"]
    # Every log entry must be a non-empty string starting with the turn marker.
    for entry in result["action_log_p0"] + result["action_log_p1"]:
        assert isinstance(entry, str)
        assert entry.startswith("T")


def test_action_log_reflects_action_types_seen():
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state)
    # A full random game must contain at least one END_TURN per player.
    assert any("END_TURN" in e for e in result["action_log_p0"])
    assert any("END_TURN" in e for e in result["action_log_p1"])


def test_format_action_move():
    a = Action(action_type=ActionType.MOVE, unit_id=3, target=Position(4, 5))
    assert _format_action(a) == "MOVE u=3 -> (4,5)"


def test_format_action_attack():
    a = Action(action_type=ActionType.ATTACK, unit_id=2, target=Position(7, 1))
    assert _format_action(a) == "ATTACK u=2 -> (7,1)"


def test_format_action_harvest_recover_capture():
    assert _format_action(Action(action_type=ActionType.HARVEST, unit_id=1)) == "HARVEST u=1"
    assert _format_action(Action(action_type=ActionType.RECOVER, unit_id=8)) == "RECOVER u=8"
    cap = Action(action_type=ActionType.CAPTURE, unit_id=4, city_id=9)
    assert _format_action(cap) == "CAPTURE u=4 city=9"


def test_format_action_train_level_up_end_turn():
    train = Action(
        action_type=ActionType.TRAIN,
        city_id=2,
        unit_type_to_train=UnitType.ARCHER,
    )
    assert _format_action(train) == "TRAIN ARCHER at city=2"
    lvl = Action(action_type=ActionType.LEVEL_UP, city_id=5)
    assert _format_action(lvl) == "LEVEL_UP city=5"
    assert _format_action(Action(action_type=ActionType.END_TURN)) == "END_TURN"


def test_render_separator_empty_and_labeled_does_not_crash():
    console = _capture_console()
    render_separator(console)
    render_separator(console, "P0 - Acción 7")
    output = console.export_text()
    # The labeled call must have written the label somewhere.
    assert "P0 - Acción 7" in output
    # The empty call still produces a horizontal line (at least one dash).
    assert "─" in output or "-" in output


def test_render_state_uses_triple_width_cells():
    state = create_initial_state(seed=42)
    console = _capture_console()
    render_state(state, viewer_player=None, console=console)
    output = console.export_text()
    # Triple-width cells produce at least two consecutive spaces between adjacent
    # one-character cell contents (e.g. ' .  . ' or ' ~  ~ ' on a map row).
    map_lines = [
        line for line in output.splitlines()
        if line.strip() and "~" in line and "─" not in line
    ]
    assert map_lines, "expected at least one map row with water tiles"
    assert any("  " in line for line in map_lines), (
        "expected ≥2 consecutive spaces between adjacent cells; "
        f"sample: {map_lines[:2]!r}"
    )
