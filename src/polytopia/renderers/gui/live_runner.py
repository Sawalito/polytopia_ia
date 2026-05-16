import time
from dataclasses import dataclass

import pygame

from polytopia.agents.base import BaseBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action, check_game_over
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import Action, ActionType, GameState
from polytopia.renderers.gui import PolytopiaRenderer
from polytopia.replay import GameRecorder


@dataclass
class LiveWatchConfig:
    delay: float = 0.6
    viewer_player: int | None = None
    paused_on_start: bool = False
    show_evaluations: bool = False
    window_width: int = 1280
    window_height: int = 800
    record_path: str | None = None


def _format_action(action: Action) -> str:
    """Versión de una sola línea para la HUD bottom bar."""
    if action.action_type == ActionType.MOVE:
        return f"MOVE unit={action.unit_id} -> ({action.target.x},{action.target.y})"
    if action.action_type == ActionType.ATTACK:
        return f"ATTACK unit={action.unit_id} -> ({action.target.x},{action.target.y})"
    if action.action_type == ActionType.HARVEST:
        return f"HARVEST unit={action.unit_id}"
    if action.action_type == ActionType.RECOVER:
        return f"RECOVER unit={action.unit_id}"
    if action.action_type == ActionType.CAPTURE:
        return f"CAPTURE unit={action.unit_id} city={action.city_id}"
    if action.action_type == ActionType.TRAIN:
        return f"TRAIN {action.unit_type_to_train.name}"
    if action.action_type == ActionType.LEVEL_UP:
        return f"LEVEL_UP city={action.city_id}"
    if action.action_type == ActionType.END_TURN:
        return "END_TURN"
    return action.action_type.name


def run_game_live(
    bot0: BaseBot,
    bot1: BaseBot,
    state: GameState,
    config: LiveWatchConfig | None = None,
) -> dict:
    """Corre una partida con visualización pygame en tiempo real.

    Controles:
        SPACE      - pausa / reanuda
        UP/DOWN    - acelera / desacelera
        S          - step (avanza una acción y pausa)
        ESC o Q    - salir
    """
    if config is None:
        config = LiveWatchConfig()

    renderer = PolytopiaRenderer(
        board_size=state.board_size,
        window_width=config.window_width,
        window_height=config.window_height,
    )

    paused = config.paused_on_start
    delay = config.delay
    last_action_text = "Esperando primera acción..."
    quit_requested = False
    step_requested = False
    last_action_time = time.time()

    n_actions = {0: 0, 1: 0}
    actions_this_turn = {0: 0, 1: 0}

    recorder = GameRecorder() if config.record_path else None
    if recorder is not None:
        recorder.record_frame(state, None)

    while not state.game_over and not quit_requested:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    quit_requested = True
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_UP:
                    delay = max(0.05, delay - 0.1)
                elif event.key == pygame.K_DOWN:
                    delay = min(3.0, delay + 0.1)
                elif event.key == pygame.K_s:
                    step_requested = True
                    paused = True

        now = time.time()
        should_advance = (
            not paused and (now - last_action_time) >= delay
        ) or step_requested

        if should_advance:
            player = state.current_player
            bot = bot0 if player == 0 else bot1
            actions = legal_actions(state, player)

            if actions:
                if actions_this_turn[player] >= 30:
                    action = next(
                        a for a in actions if a.action_type == ActionType.END_TURN
                    )
                else:
                    action = bot.select_action(state, actions)

                state = apply_action(state, action)
                n_actions[player] += 1
                actions_this_turn[player] += 1
                if action.action_type == ActionType.END_TURN:
                    actions_this_turn[player] = 0

                if recorder is not None:
                    recorder.record_frame(state, action)

                last_action_text = f"P{player}: {_format_action(action)}"
                last_action_time = now

            step_requested = False

        status_suffix = "  [PAUSADO]" if paused else f"  [delay {delay:.1f}s]"
        renderer.render(
            state,
            viewer_player=config.viewer_player,
            last_action_text=last_action_text + status_suffix,
        )
        renderer.clock.tick(60)

    final_check = check_game_over(state)
    state.game_over = True
    state.winner = final_check[1]

    end_time = time.time()
    while not quit_requested and (time.time() - end_time) < 8.0:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            elif event.type == pygame.KEYDOWN and event.key in (
                pygame.K_ESCAPE,
                pygame.K_q,
                pygame.K_SPACE,
            ):
                quit_requested = True
        renderer.render(
            state,
            viewer_player=config.viewer_player,
            last_action_text="Presiona cualquier tecla para salir",
        )
        renderer.clock.tick(30)

    if recorder is not None and config.record_path:
        recorder.save(config.record_path)

    renderer.close()

    return {
        "winner": state.winner,
        "final_turn": state.turn,
        "n_actions_p0": n_actions[0],
        "n_actions_p1": n_actions[1],
    }


def main() -> None:
    """CLI para correr una partida en modo live gráfico."""
    import argparse

    from polytopia.agents.random_bot import RandomBot

    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument("--viewer", type=int, choices=[0, 1], default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--paused", action="store_true", help="arrancar pausado")
    parser.add_argument(
        "--bot",
        choices=["random", "heuristic"],
        default="random",
        help="qué bot juega como P0 (P1 siempre es random)",
    )
    parser.add_argument(
        "--record",
        type=str,
        default=None,
        help="path al .json donde guardar el replay",
    )
    args = parser.parse_args()

    state = create_initial_state(seed=args.seed)

    if args.bot == "heuristic":
        from polytopia.agents.heuristic_bot import HeuristicBot

        bot0 = HeuristicBot(player_id=0)
    else:
        bot0 = RandomBot(player_id=0, seed=1)

    bot1 = RandomBot(player_id=1, seed=2)

    config = LiveWatchConfig(
        delay=args.delay,
        viewer_player=args.viewer,
        paused_on_start=args.paused,
        record_path=args.record,
    )
    result = run_game_live(bot0, bot1, state, config)
    print(f"Winner: P{result['winner']}, turn {result['final_turn']}")


if __name__ == "__main__":
    main()
