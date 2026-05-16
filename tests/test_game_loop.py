import pytest

from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game


def test_random_vs_random_completes():
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state)
    # Game must end; winner is either a player id or None (draw at max_turns).
    assert result["winner"] in (None, 0, 1)
    assert result["final_turn"] >= 1


def test_run_game_returns_expected_keys():
    state = create_initial_state(seed=7)
    bot0 = RandomBot(player_id=0, seed=11)
    bot1 = RandomBot(player_id=1, seed=12)
    result = run_game(bot0, bot1, state)
    assert set(result.keys()) == {
        "winner",
        "final_turn",
        "n_actions_p0",
        "n_actions_p1",
        "action_log_p0",
        "action_log_p1",
        "final_score",
    }
    assert isinstance(result["final_score"], dict)
    assert set(result["final_score"].keys()) == {0, 1}
    assert isinstance(result["n_actions_p0"], int)
    assert isinstance(result["n_actions_p1"], int)


def test_heuristic_bot_raises_not_implemented():
    state = create_initial_state(seed=42)
    from polytopia.engine.actions import legal_actions

    bot = HeuristicBot(player_id=0)
    with pytest.raises(NotImplementedError):
        bot.select_action(state, legal_actions(state, 0))
