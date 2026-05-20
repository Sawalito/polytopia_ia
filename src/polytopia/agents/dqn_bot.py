"""DQN sobre features compartidas. Q(s, a) scoring sobre cada accion legal.

Arquitectura:
- Input: FEATURE_DIM = 14 + 14 + 8 = 36
- 2 hidden layers de 64 unidades, ReLU
- Output: 1 scalar Q-value

Inferencia: para cada accion legal, calcular Q(s, a) y elegir argmax.
Durante training: epsilon-greedy.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn

from polytopia.agents.base import BaseBot
from polytopia.agents.features import FEATURE_DIM, extract_state_action_features
from polytopia.interfaces import Action, GameState


class DQNNet(nn.Module):
    def __init__(self, input_dim: int = FEATURE_DIM, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class DQNBot(BaseBot):
    def __init__(
        self,
        player_id: int,
        name: str = "dqn",
        seed: int = 42,
        model: Optional[DQNNet] = None,
        device: str = "auto",
        epsilon: float = 0.0,
    ):
        super().__init__(player_id, name)
        self._rng = random.Random(seed)
        self.epsilon = epsilon
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.model = (model if model is not None else DQNNet()).to(self.device)
        self.model.eval()

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        if len(legal_actions) == 1:
            return legal_actions[0]
        if self._rng.random() < self.epsilon:
            return self._rng.choice(legal_actions)
        features = np.stack([
            extract_state_action_features(state, a, self.player_id)
            for a in legal_actions
        ])
        with torch.no_grad():
            features_t = torch.from_numpy(features).to(self.device)
            q_values = self.model(features_t).cpu().numpy()
        return legal_actions[int(np.argmax(q_values))]

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), path)

    @classmethod
    def load(cls, path: str | Path, player_id: int, **kwargs) -> "DQNBot":
        model = DQNNet()
        model.load_state_dict(torch.load(path, map_location="cpu"))
        return cls(player_id=player_id, model=model, **kwargs)
