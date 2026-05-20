import time
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel

from polytopia.agents.base import BaseBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action, calculate_score, check_game_over
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import Action, ActionType, GameState
from polytopia.renderers.terminal import render_separator, render_state


@dataclass
class WatchConfig:
    """Configuración del modo watch."""

    enabled: bool = False
    delay: float = 0.8
    step_by_step: bool = False
    viewer_player: int | None = None
    show_action_log: bool = True
    show_evaluations: bool = False
    clear_screen: bool = True


def _clear_screen(console: Console) -> None:
    console.clear()


def _format_action(action: Action) -> str:
    """Representación corta y legible de una acción para el log."""
    t = action.action_type.name
    if t == "MOVE":
        return f"MOVE u={action.unit_id} -> ({action.target.x},{action.target.y})"
    if t == "ATTACK":
        return f"ATTACK u={action.unit_id} -> ({action.target.x},{action.target.y})"
    if t == "HARVEST":
        return f"HARVEST u={action.unit_id}"
    if t == "RECOVER":
        return f"RECOVER u={action.unit_id}"
    if t == "CAPTURE":
        return f"CAPTURE u={action.unit_id} city={action.city_id}"
    if t == "TRAIN":
        return f"TRAIN {action.unit_type_to_train.name} at city={action.city_id}"
    if t == "LEVEL_UP":
        return f"LEVEL_UP city={action.city_id}"
    if t == "END_TURN":
        return "END_TURN"
    return t


def _try_get_evaluations(
    bot: BaseBot,
    state: GameState,
    actions: list[Action],
    top_k: int = 3,
) -> list[tuple[float, Action]] | None:
    """Si el bot expone .evaluate(state), retorna top-k acciones con su valor.
    Si no expone evaluate, retorna None.
    """
    if not hasattr(bot, "evaluate"):
        return None
    try:
        evaluated = []
        for a in actions:
            new_state = apply_action(state, a)
            score = bot.evaluate(new_state)
            evaluated.append((score, a))
        evaluated.sort(key=lambda pair: pair[0], reverse=True)
        return evaluated[:top_k]
    except Exception:
        return None


def _render_action_header(
    console: Console,
    player: int,
    bot_name: str,
    action: Action,
    turn: int,
    max_turns: int,
) -> None:
    color = "cyan" if player == 0 else "magenta"
    console.print(
        Panel(
            f"[{color}]Turn {turn}/{max_turns} - P{player} ({bot_name})[/{color}]: "
            f"[bold]{_format_action(action)}[/bold]",
            border_style=color,
            padding=(1, 4),
        )
    )


def _render_action_log(
    console: Console,
    log_p0: list[str],
    log_p1: list[str],
    max_entries: int = 5,
) -> None:
    """Imprime sidebar con últimas acciones de cada jugador."""
    p0_recent = log_p0[-max_entries:]
    p1_recent = log_p1[-max_entries:]
    console.print()
    console.print(
        Panel(
            "\n".join(f"[cyan]{i+1}.[/cyan] {a}" for i, a in enumerate(p0_recent))
            if p0_recent
            else "[dim]Sin acciones aún[/dim]",
            title="[cyan]Últimas acciones P0[/cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    console.print()
    console.print(
        Panel(
            "\n".join(f"[magenta]{i+1}.[/magenta] {a}" for i, a in enumerate(p1_recent))
            if p1_recent
            else "[dim]Sin acciones aún[/dim]",
            title="[magenta]Últimas acciones P1[/magenta]",
            border_style="magenta",
            padding=(0, 2),
        )
    )


def _render_evaluations(
    console: Console,
    evaluations: list[tuple[float, Action]],
    chosen: Action,
) -> None:
    """Imprime top-k acciones evaluadas por el bot, marcando la elegida."""
    console.print()
    console.print("[bold]Top acciones evaluadas:[/bold]")
    for score, action in evaluations:
        marker = "[green]->[/green]" if action == chosen else "  "
        console.print(f"  {marker}  {score:>+8.2f}   {_format_action(action)}")
    console.print()


def run_game(
    bot0: BaseBot,
    bot1: BaseBot,
    state: GameState,
    watch: WatchConfig | None = None,
    max_actions_per_turn: int = 30,
) -> dict:
    """Corre una partida completa entre dos bots.

    Si watch.enabled, muestra paso a paso en consola con la configuración dada.
    Si watch.enabled es False (o watch es None), modo silencioso.

    Returns:
        {
            "winner": int | None,
            "final_turn": int,
            "n_actions_p0": int,
            "n_actions_p1": int,
            "action_log_p0": list[str],
            "action_log_p1": list[str],
            "final_score": dict[int, int],
        }
    """
    if watch is None:
        watch = WatchConfig(enabled=False)

    console = Console()
    action_log_p0: list[str] = []
    action_log_p1: list[str] = []
    n_actions = {0: 0, 1: 0}
    actions_this_turn = {0: 0, 1: 0}

    while not state.game_over:
        player = state.current_player
        bot = bot0 if player == 0 else bot1
        actions = legal_actions(state, player)
        if not actions:
            break

        evaluations: list[tuple[float, Action]] | None = None
        if actions_this_turn[player] >= max_actions_per_turn:
            action = next(a for a in actions if a.action_type == ActionType.END_TURN)
        else:
            if watch.enabled and watch.show_evaluations:
                evaluations = _try_get_evaluations(bot, state, actions)
            action = bot.select_action(state, actions)

        state = apply_action(state, action)
        n_actions[player] += 1
        actions_this_turn[player] += 1

        log_entry = f"T{state.turn}: {_format_action(action)}"
        if player == 0:
            action_log_p0.append(log_entry)
        else:
            action_log_p1.append(log_entry)

        if action.action_type == ActionType.END_TURN:
            actions_this_turn[player] = 0

        if watch.enabled:
            if watch.clear_screen:
                _clear_screen(console)
            console.print()
            render_separator(console, f"P{player} - Acción {n_actions[player]}")
            console.print()
            _render_action_header(
                console, player, bot.name, action, state.turn, state.max_turns
            )
            render_state(state, viewer_player=watch.viewer_player)
            console.print()
            if watch.show_action_log:
                _render_action_log(console, action_log_p0, action_log_p1)
            if evaluations is not None:
                _render_evaluations(console, evaluations, action)
            console.print()
            console.print()
            if watch.step_by_step:
                console.input("[dim]Enter para continuar...[/dim]")
            elif watch.delay > 0:
                time.sleep(watch.delay)

    _, winner = check_game_over(state)
    final_score = {p: calculate_score(state, p) for p in (0, 1)}

    if watch.enabled:
        if watch.clear_screen:
            _clear_screen(console)
        else:
            console.print()
        console.rule("[bold]Game Over[/bold]")
        if winner is not None:
            color = "cyan" if winner == 0 else "magenta"
            console.print(f"[{color}]Ganador: P{winner}[/{color}]")
        else:
            console.print("[yellow]Empate[/yellow]")
        console.print(f"Turno final: {state.turn}")
        console.print(f"Score P0: {final_score[0]}  |  Score P1: {final_score[1]}")
        console.print(f"Acciones P0: {n_actions[0]}  |  Acciones P1: {n_actions[1]}")

    return {
        "winner": winner,
        "final_turn": state.turn,
        "n_actions_p0": n_actions[0],
        "n_actions_p1": n_actions[1],
        "action_log_p0": action_log_p0,
        "action_log_p1": action_log_p1,
        "final_score": final_score,
    }


def main() -> None:
    """CLI con argparse para distintos modos.

    Uso:
        python -m polytopia.game_loop                       # silencioso
        python -m polytopia.game_loop --watch               # paso a paso, delay 0.5s
        python -m polytopia.game_loop --watch --delay 1.0   # más lento
        python -m polytopia.game_loop --watch --step        # avanza con Enter
        python -m polytopia.game_loop --watch --viewer 0    # ver con niebla de P0
        python -m polytopia.game_loop --watch --eval        # top-3 evaluaciones
    """
    import argparse

    from polytopia.agents.random_bot import RandomBot

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="modo visualización")
    parser.add_argument("--delay", type=float, default=0.8, help="segundos entre frames")
    parser.add_argument("--step", action="store_true", help="avanza con Enter (override delay)")
    parser.add_argument(
        "--viewer", type=int, choices=[0, 1], default=None,
        help="ver con fog de un jugador específico",
    )
    parser.add_argument(
        "--eval", action="store_true",
        help="mostrar top-3 evaluaciones (requiere bot con evaluate())",
    )
    parser.add_argument(
        "--no-clear", action="store_true",
        help="no limpiar pantalla entre frames (debugging)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    state = create_initial_state(seed=args.seed)
    bot0 = RandomBot(player_id=0, seed=1, name="random_p0")
    bot1 = RandomBot(player_id=1, seed=2, name="random_p1")

    watch = WatchConfig(
        enabled=args.watch,
        delay=args.delay,
        step_by_step=args.step,
        viewer_player=args.viewer,
        show_evaluations=args.eval,
        clear_screen=not args.no_clear,
    )
    result = run_game(bot0, bot1, state, watch=watch)

    if not args.watch:
        print(f"Winner: P{result['winner']}, turn {result['final_turn']}")


if __name__ == "__main__":
    main()
