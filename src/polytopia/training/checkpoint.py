"""Checkpointing completo para entrenamiento intermitente.

Persiste:
- Modelo online + target
- Optimizer state (Adam momentos)
- Replay buffer completo
- Episode count, epsilon, hyperparams
- RNG state (Python, numpy, torch)
- Historial de metricas

Garantia: reanudar despues de pausar produce el mismo training que correr
de corrido."""

from __future__ import annotations

import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

CHECKPOINT_VERSION = 1


def save_checkpoint(
    path: str | Path,
    online_net: torch.nn.Module,
    target_net: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    replay_buffer: Any,
    episode: int,
    epsilon: float,
    win_rate_log: list,
    losses_log: list,
    hyperparams: dict,
    opponent_distribution: dict | None = None,
) -> None:
    """Guarda estado completo. Usa archivo temporal + rename para no corromper."""
    import random as py_random

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = {
        "version": CHECKPOINT_VERSION,
        "timestamp": time.time(),
        "online_net_state": online_net.state_dict(),
        "target_net_state": target_net.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "replay_buffer": list(replay_buffer),
        "episode": episode,
        "epsilon": epsilon,
        "win_rate_log": win_rate_log,
        "losses_log": losses_log,
        "hyperparams": hyperparams,
        "opponent_distribution": opponent_distribution or {},
        "rng_python": py_random.getstate(),
        "rng_numpy": np.random.get_state(),
        "rng_torch": torch.get_rng_state(),
    }

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp_path.replace(path)


def load_checkpoint(
    path: str | Path,
    online_net: torch.nn.Module,
    target_net: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
) -> dict:
    """Carga estado completo. Modifica las redes y optimizer in-place."""
    import random as py_random

    with open(path, "rb") as f:
        state = pickle.load(f)

    if state.get("version") != CHECKPOINT_VERSION:
        print(f"WARNING: checkpoint version mismatch")

    online_net.load_state_dict(state["online_net_state"])
    target_net.load_state_dict(state["target_net_state"])
    optimizer.load_state_dict(state["optimizer_state"])

    py_random.setstate(state["rng_python"])
    np.random.set_state(state["rng_numpy"])
    torch.set_rng_state(state["rng_torch"])

    return {
        "episode": state["episode"],
        "epsilon": state["epsilon"],
        "win_rate_log": state["win_rate_log"],
        "losses_log": state["losses_log"],
        "replay_buffer": state["replay_buffer"],
        "hyperparams": state["hyperparams"],
        "opponent_distribution": state.get("opponent_distribution", {}),
        "timestamp": state["timestamp"],
    }


def checkpoint_exists(path: str | Path) -> bool:
    return Path(path).exists()


def checkpoint_metadata(path: str | Path) -> dict:
    """Lee solo metadata sin cargar todo."""
    with open(path, "rb") as f:
        state = pickle.load(f)
    return {
        "version": state.get("version"),
        "timestamp": state.get("timestamp"),
        "episode": state.get("episode"),
        "epsilon": state.get("epsilon"),
        "buffer_size": len(state.get("replay_buffer", [])),
        "hyperparams": state.get("hyperparams"),
        "opponent_distribution": state.get("opponent_distribution", {}),
    }
