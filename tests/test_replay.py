import tempfile
from pathlib import Path

from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import ActionType
from polytopia.replay import GameRecorder, load_replay


def test_record_and_load_roundtrip():
    """Grabar una partida corta y recargarla debe preservar estados clave."""
    state = create_initial_state(seed=42)
    recorder = GameRecorder()
    recorder.record_frame(state, None)

    for _ in range(5):
        actions = legal_actions(state, state.current_player)
        if not actions:
            break
        action = next(a for a in actions if a.action_type == ActionType.END_TURN)
        state = apply_action(state, action)
        recorder.record_frame(state, action)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
    recorder.save(path)

    frames = load_replay(path)
    assert len(frames) == 6  # estado inicial + 5 acciones
    assert frames[0]["action"] is None
    assert frames[1]["action"].action_type == ActionType.END_TURN
    assert frames[-1]["state"].turn >= 2

    path.unlink()
