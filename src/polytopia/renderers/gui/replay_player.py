import time

import pygame

from polytopia.replay import load_replay
from polytopia.renderers.gui import PolytopiaRenderer


def _format_action(action) -> str:
    if action is None:
        return "Estado inicial"
    name = action.action_type.name
    if name == "MOVE":
        return f"MOVE unit={action.unit_id} -> ({action.target.x},{action.target.y})"
    if name == "ATTACK":
        return f"ATTACK unit={action.unit_id} -> ({action.target.x},{action.target.y})"
    if name == "HARVEST":
        return f"HARVEST unit={action.unit_id}"
    if name == "RECOVER":
        return f"RECOVER unit={action.unit_id}"
    if name == "CAPTURE":
        return f"CAPTURE unit={action.unit_id}"
    if name == "TRAIN":
        return f"TRAIN {action.unit_type_to_train.name}"
    if name == "LEVEL_UP":
        return f"LEVEL_UP city={action.city_id}"
    if name == "END_TURN":
        return "END_TURN"
    return name


def play_replay(
    replay_path: str,
    initial_delay: float = 0.5,
    viewer_player: int | None = None,
    window_width: int = 1280,
    window_height: int = 800,
) -> None:
    """Reproduce un replay grabado con controles de playback.

    Controles:
        SPACE        - pausa / reanuda
        LEFT/RIGHT   - frame anterior / siguiente (pausa)
        UP/DOWN      - acelera / desacelera
        HOME         - reinicia al primer frame
        END          - salta al último frame
        ESC o Q      - salir
    """
    frames = load_replay(replay_path)
    if not frames:
        print(f"Replay vacío: {replay_path}")
        return

    state_sample = frames[0]["state"]
    renderer = PolytopiaRenderer(
        board_size=state_sample.board_size,
        window_width=window_width,
        window_height=window_height,
        title=f"Polytopia Replay - {replay_path}",
    )

    current_frame = 0
    paused = False
    delay = initial_delay
    last_advance = time.time()
    quit_requested = False

    while not quit_requested:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    quit_requested = True
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_LEFT:
                    paused = True
                    current_frame = max(0, current_frame - 1)
                elif event.key == pygame.K_RIGHT:
                    paused = True
                    current_frame = min(len(frames) - 1, current_frame + 1)
                elif event.key == pygame.K_UP:
                    delay = max(0.05, delay - 0.1)
                elif event.key == pygame.K_DOWN:
                    delay = min(3.0, delay + 0.1)
                elif event.key == pygame.K_HOME:
                    current_frame = 0
                    paused = True
                elif event.key == pygame.K_END:
                    current_frame = len(frames) - 1
                    paused = True

        now = time.time()
        if not paused and current_frame < len(frames) - 1:
            if (now - last_advance) >= delay:
                current_frame += 1
                last_advance = now

        frame = frames[current_frame]
        status = (
            f"Frame {current_frame + 1}/{len(frames)}  |  "
            + ("PAUSADO" if paused else f"delay {delay:.1f}s")
            + f"  |  {_format_action(frame['action'])}"
        )

        renderer.render(
            frame["state"],
            viewer_player=viewer_player,
            last_action_text=status,
        )
        renderer.clock.tick(60)

    renderer.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("replay_path", help="ruta al .json del replay")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--viewer", type=int, choices=[0, 1], default=None)
    args = parser.parse_args()
    play_replay(args.replay_path, args.delay, args.viewer)


if __name__ == "__main__":
    main()
