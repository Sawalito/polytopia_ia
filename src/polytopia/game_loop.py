from polytopia.agents.base import BaseBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import Action, ActionType, GameState
from polytopia.renderers.terminal import render_state


def _force_end_turn(state: GameState) -> GameState:
    actions = legal_actions(state, state.current_player)
    end = next((a for a in actions if a.action_type == ActionType.END_TURN), None)
    if end is None:
        end = Action(action_type=ActionType.END_TURN)
    return apply_action(state, end)


def run_game(
    bot0: BaseBot,
    bot1: BaseBot,
    state: GameState,
    render: bool = False,
    viewer: int | None = None,
    max_actions_per_turn: int = 30,
) -> dict:
    """Run a full game between two bots.

    Returns: {
        "winner": int | None,
        "final_turn": int,
        "n_actions_p0": int,
        "n_actions_p1": int,
        "final_score": dict[int, int],
    }
    """
    n_actions = {0: 0, 1: 0}
    actions_this_turn = 0
    current_turn = state.turn
    current_player = state.current_player

    while not state.game_over:
        if state.turn != current_turn or state.current_player != current_player:
            actions_this_turn = 0
            current_turn = state.turn
            current_player = state.current_player

        player = state.current_player
        bot = bot0 if player == 0 else bot1

        if actions_this_turn >= max_actions_per_turn:
            state = _force_end_turn(state)
        else:
            actions = legal_actions(state, player)
            if not actions:
                state = _force_end_turn(state)
            else:
                action = bot.select_action(state, actions)
                state = apply_action(state, action)
                n_actions[player] += 1
                actions_this_turn += 1

        if render:
            render_state(state, viewer)

    final_score = {
        pid: state.stars[pid]
        + sum(1 for u in state.units.values() if u.owner == pid and u.is_alive)
        + sum(1 for c in state.cities.values() if c.owner == pid) * 10
        for pid in (0, 1)
    }

    return {
        "winner": state.winner,
        "final_turn": state.turn,
        "n_actions_p0": n_actions[0],
        "n_actions_p1": n_actions[1],
        "final_score": final_score,
    }


def main() -> None:
    """Demo: RandomBot vs RandomBot, prints the result."""
    state = create_initial_state(seed=42)
    bot0 = RandomBot(player_id=0, seed=1)
    bot1 = RandomBot(player_id=1, seed=2)
    result = run_game(bot0, bot1, state, render=False)
    winner = result["winner"]
    label = "draw" if winner is None else f"P{winner}"
    print(
        f"Winner: {label}, turn {result['final_turn']}, "
        f"actions=(P0:{result['n_actions_p0']}, P1:{result['n_actions_p1']}), "
        f"score={result['final_score']}"
    )


if __name__ == "__main__":
    main()
