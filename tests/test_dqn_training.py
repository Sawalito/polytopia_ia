from collections import deque

import numpy as np
import torch

from polytopia.agents.dqn_bot import DQNBot, DQNNet
from polytopia.agents.features import FEATURE_DIM
from polytopia.engine.actions import legal_actions
from polytopia.engine.state_init import create_initial_state
from polytopia.training.checkpoint import (
    checkpoint_exists,
    checkpoint_metadata,
    load_checkpoint,
    save_checkpoint,
)


def test_dqn_returns_legal_action():
    state = create_initial_state(seed=42)
    bot = DQNBot(player_id=0)
    actions = legal_actions(state, 0)
    chosen = bot.select_action(state, actions)
    assert chosen in actions


def test_dqn_save_load(tmp_path):
    bot = DQNBot(player_id=0)
    p = tmp_path / "model.pt"
    bot.save(p)
    loaded = DQNBot.load(p, player_id=0)
    assert loaded.model is not None


def test_checkpoint_roundtrip(tmp_path):
    online = DQNNet()
    target = DQNNet()
    target.load_state_dict(online.state_dict())
    opt = torch.optim.Adam(online.parameters(), lr=1e-3)

    buffer = deque([
        (np.zeros(FEATURE_DIM, dtype=np.float32), 0.5, False,
         np.zeros(FEATURE_DIM, dtype=np.float32))
        for _ in range(10)
    ], maxlen=100)

    p = tmp_path / "ckpt.pkl"
    save_checkpoint(
        p, online, target, opt, buffer,
        episode=50, epsilon=0.3,
        win_rate_log=[(10, 0.4), (20, 0.5)],
        losses_log=[0.1, 0.08],
        hyperparams={"lr": 1e-3},
    )
    assert checkpoint_exists(p)

    meta = checkpoint_metadata(p)
    assert meta["episode"] == 50
    assert meta["buffer_size"] == 10

    online2 = DQNNet()
    target2 = DQNNet()
    target2.load_state_dict(online2.state_dict())
    opt2 = torch.optim.Adam(online2.parameters(), lr=1e-3)

    state = load_checkpoint(p, online2, target2, opt2)
    assert state["episode"] == 50
    assert len(state["replay_buffer"]) == 10
    for p1, p2 in zip(online.parameters(), online2.parameters()):
        assert torch.allclose(p1, p2)
