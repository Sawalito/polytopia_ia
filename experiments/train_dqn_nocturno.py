"""Training DQN nocturno. Soporta entrenamiento intermitente con resume.

El DQN entrena contra un opponent pool diverso:
- 40% HeuristicBot v3 (el mas fuerte, oponente principal)
- 20% AggressiveBot
- 15% DefensiveBot
- 15% EconomicBot
- 10% RandomBot (baseline ocasional para no perder cobertura)

Uso:
    # Primera sesion (target: 2000 episodios totales)
    python -m experiments.train_dqn_nocturno --episodes 2000

    # Continuar despues de pausar
    python -m experiments.train_dqn_nocturno --episodes 2000 --resume

    # Sesion limitada a tiempo (ej: 2 horas)
    python -m experiments.train_dqn_nocturno --episodes 2000 --resume --max-time-min 120

    # Ver estado sin entrenar
    python -m experiments.train_dqn_nocturno --status
"""

from __future__ import annotations

import argparse
import random
import time
from collections import Counter, deque

import numpy as np
import torch
import torch.nn as nn

from polytopia.agents.aggressive_bot import AggressiveBot
from polytopia.agents.defensive_bot import DefensiveBot
from polytopia.agents.dqn_bot import DQNBot, DQNNet
from polytopia.agents.economic_bot import EconomicBot
from polytopia.agents.features import extract_state_action_features
from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action, check_game_over
from polytopia.engine.state_init import create_initial_state
from polytopia.training.checkpoint import (
    checkpoint_exists,
    checkpoint_metadata,
    load_checkpoint,
    save_checkpoint,
)

CHECKPOINT_PATH = "checkpoints/dqn_nocturno.pkl"
MODEL_PATH = "checkpoints/dqn_nocturno_model.pt"

OPPONENT_POOL = [
    ("HeuristicV3", 0.40, lambda pid, seed: HeuristicBot(player_id=pid, seed=seed)),
    ("Aggressive", 0.20, lambda pid, seed: AggressiveBot(player_id=pid, seed=seed)),
    ("Defensive", 0.15, lambda pid, seed: DefensiveBot(player_id=pid, seed=seed)),
    ("Economic", 0.15, lambda pid, seed: EconomicBot(player_id=pid, seed=seed)),
    ("Random", 0.10, lambda pid, seed: RandomBot(player_id=pid, seed=seed)),
]


def sample_opponent(rng: random.Random, episode: int):
    """Sample opponent del pool segun la distribucion. Retorna (name, instance)."""
    r = rng.random()
    cumulative = 0.0
    for name, prob, factory in OPPONENT_POOL:
        cumulative += prob
        if r < cumulative:
            return name, factory(1, episode + 10000)
    name, _, factory = OPPONENT_POOL[0]
    return name, factory(1, episode + 10000)


def _build_components(device: str, hyperparams: dict):
    online_net = DQNNet().to(device)
    target_net = DQNNet().to(device)
    target_net.load_state_dict(online_net.state_dict())
    target_net.eval()
    optimizer = torch.optim.Adam(online_net.parameters(), lr=hyperparams["lr"])
    return online_net, target_net, optimizer


def train_session(
    target_total_episodes: int,
    resume: bool = False,
    max_time_seconds: float | None = None,
    save_every_episodes: int = 50,
    log_every: int = 20,
) -> dict:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    default_hyperparams = {
        "batch_size": 64,
        "buffer_size": 20000,
        "gamma": 0.97,
        "lr": 5e-4,
        "epsilon_start": 1.0,
        "epsilon_end": 0.05,
        "epsilon_decay_episodes": 1000,
        "target_sync_every": 25,
    }

    start_episode = 0
    epsilon = default_hyperparams["epsilon_start"]
    win_rate_log: list = []
    losses_log: list = []
    replay_buffer: deque = deque(maxlen=default_hyperparams["buffer_size"])
    hyperparams = default_hyperparams
    opponent_distribution: Counter = Counter()

    online_net, target_net, optimizer = _build_components(device, hyperparams)
    loss_fn = nn.MSELoss()
    sample_rng = random.Random()

    if resume and checkpoint_exists(CHECKPOINT_PATH):
        print(f"Cargando checkpoint: {CHECKPOINT_PATH}")
        state = load_checkpoint(CHECKPOINT_PATH, online_net, target_net, optimizer)
        start_episode = state["episode"]
        epsilon = state["epsilon"]
        win_rate_log = state["win_rate_log"]
        losses_log = state["losses_log"]
        hyperparams = state["hyperparams"]
        replay_buffer = deque(state["replay_buffer"], maxlen=hyperparams["buffer_size"])
        opponent_distribution = Counter(state.get("opponent_distribution", {}))
        edad_h = (time.time() - state["timestamp"]) / 3600
        print(
            f"Reanudando desde ep {start_episode}, eps={epsilon:.3f}, "
            f"buffer={len(replay_buffer)}, edad_checkpoint={edad_h:.1f}h"
        )
    elif resume:
        print("--resume pasado pero no existe checkpoint. Empezando fresh.")

    if start_episode >= target_total_episodes:
        print(
            f"Ya alcanzaste {start_episode} >= {target_total_episodes}. Nada que hacer."
        )
        return {"episode": start_episode}

    wins_in_session = 0
    episodes_in_session = 0
    wins_by_opponent: Counter = Counter()
    games_by_opponent: Counter = Counter()
    start_time = time.time()

    print(f"Entrenando ep {start_episode + 1} a {target_total_episodes}")
    if max_time_seconds:
        print(f"Limite de sesion: {max_time_seconds/60:.0f} min")
    print(f"Opponent pool: {[name for name, _, _ in OPPONENT_POOL]}")
    print()

    for episode in range(start_episode, target_total_episodes):
        elapsed = time.time() - start_time
        if max_time_seconds and elapsed >= max_time_seconds:
            print(f"\n>>> Limite de tiempo alcanzado ({elapsed:.0f}s). Guardando.")
            break

        epsilon = max(
            hyperparams["epsilon_end"],
            hyperparams["epsilon_start"]
            - (hyperparams["epsilon_start"] - hyperparams["epsilon_end"])
            * episode / hyperparams["epsilon_decay_episodes"],
        )

        opp_name, opponent = sample_opponent(sample_rng, episode)
        opponent_distribution[opp_name] += 1
        games_by_opponent[opp_name] += 1

        dqn_bot = DQNBot(
            player_id=0, model=online_net, epsilon=epsilon, seed=episode,
        )
        state = create_initial_state(seed=episode)
        episode_transitions: list = []

        while not state.game_over:
            player = state.current_player
            actions = legal_actions(state, player)
            if not actions:
                break

            if player == 0:
                action = dqn_bot.select_action(state, actions)
                features = extract_state_action_features(state, action, 0)
                next_state = apply_action(state, action)
                done = next_state.game_over
                episode_transitions.append((features, 0.0, done, next_state))
                state = next_state
            else:
                action = opponent.select_action(state, actions)
                state = apply_action(state, action)

        _, winner = check_game_over(state)
        if winner == 0:
            wins_in_session += 1
            wins_by_opponent[opp_name] += 1

        final_reward = 1.0 if winner == 0 else (-1.0 if winner == 1 else 0.0)
        if episode_transitions:
            features, _r, _done, next_state = episode_transitions[-1]
            episode_transitions[-1] = (features, final_reward, True, next_state)

        for features, r, done, next_state in episode_transitions:
            if done:
                next_features = np.zeros_like(features)
            else:
                next_actions = legal_actions(next_state, 0)
                if not next_actions:
                    next_features = np.zeros_like(features)
                    done = True
                else:
                    next_features_all = np.stack([
                        extract_state_action_features(next_state, na, 0)
                        for na in next_actions
                    ])
                    with torch.no_grad():
                        nf_t = torch.from_numpy(next_features_all).to(device)
                        q_next = target_net(nf_t).cpu().numpy()
                    next_features = next_features_all[int(np.argmax(q_next))]
            replay_buffer.append((features, r, done, next_features))

        if len(replay_buffer) >= hyperparams["batch_size"]:
            batch_idx = np.random.choice(
                len(replay_buffer), hyperparams["batch_size"], replace=False
            )
            batch = [replay_buffer[i] for i in batch_idx]
            features_batch = torch.from_numpy(
                np.stack([b[0] for b in batch])
            ).to(device)
            rewards_batch = torch.tensor(
                [b[1] for b in batch], dtype=torch.float32
            ).to(device)
            dones_batch = torch.tensor(
                [b[2] for b in batch], dtype=torch.float32
            ).to(device)
            next_features_batch = torch.from_numpy(
                np.stack([b[3] for b in batch])
            ).to(device)

            with torch.no_grad():
                q_next = target_net(next_features_batch)
                q_target = rewards_batch + hyperparams["gamma"] * q_next * (1.0 - dones_batch)

            online_net.train()
            q_online = online_net(features_batch)
            loss = loss_fn(q_online, q_target)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(online_net.parameters(), 1.0)
            optimizer.step()
            online_net.eval()
            losses_log.append(loss.item())

        if (episode + 1) % hyperparams["target_sync_every"] == 0:
            target_net.load_state_dict(online_net.state_dict())

        episodes_in_session += 1

        if (episode + 1) % log_every == 0:
            session_wr = wins_in_session / max(episodes_in_session, 1)
            win_rate_log.append((episode + 1, session_wr))
            avg_loss = float(np.mean(losses_log[-100:])) if losses_log else 0.0
            print(
                f"Ep {episode+1}/{target_total_episodes}  "
                f"sess_wr={session_wr:.2%}  eps={epsilon:.2f}  "
                f"loss={avg_loss:.4f}  buf={len(replay_buffer)}  "
                f"t={elapsed:.0f}s"
            )

        if (episode + 1) % save_every_episodes == 0:
            save_checkpoint(
                CHECKPOINT_PATH,
                online_net=online_net, target_net=target_net, optimizer=optimizer,
                replay_buffer=replay_buffer,
                episode=episode + 1, epsilon=epsilon,
                win_rate_log=win_rate_log, losses_log=losses_log,
                hyperparams=hyperparams,
                opponent_distribution=dict(opponent_distribution),
            )
            torch.save(online_net.state_dict(), MODEL_PATH)

    final_episode = start_episode + episodes_in_session
    save_checkpoint(
        CHECKPOINT_PATH,
        online_net=online_net, target_net=target_net, optimizer=optimizer,
        replay_buffer=replay_buffer,
        episode=final_episode, epsilon=epsilon,
        win_rate_log=win_rate_log, losses_log=losses_log,
        hyperparams=hyperparams,
        opponent_distribution=dict(opponent_distribution),
    )
    torch.save(online_net.state_dict(), MODEL_PATH)

    total_time = time.time() - start_time
    session_wr = wins_in_session / max(episodes_in_session, 1)

    print("\n" + "=" * 60)
    print("RESUMEN DE LA SESION")
    print("=" * 60)
    print(f"Episodios en esta sesion:    {episodes_in_session}")
    print(f"Episodios totales:           {final_episode}/{target_total_episodes}")
    print(f"Win rate en sesion:          {session_wr:.2%}")
    print(f"Tiempo de sesion:            {total_time:.0f}s ({total_time/60:.1f}min)")
    print()
    print("Win rate por oponente (en esta sesion):")
    for opp_name, _, _ in OPPONENT_POOL:
        games = games_by_opponent[opp_name]
        wins = wins_by_opponent[opp_name]
        wr = wins / games if games else 0.0
        print(f"  vs {opp_name:<12} {wins:>3}/{games:<3} ({wr:.0%})")
    print()
    print(f"Checkpoint guardado: {CHECKPOINT_PATH}")
    print(f"Modelo guardado:     {MODEL_PATH}")

    return {
        "episode": final_episode,
        "session_episodes": episodes_in_session,
        "session_win_rate": session_wr,
        "win_rate_log": win_rate_log,
        "total_time": total_time,
    }


def print_status():
    if not checkpoint_exists(CHECKPOINT_PATH):
        print(f"No hay checkpoint en {CHECKPOINT_PATH}")
        return

    meta = checkpoint_metadata(CHECKPOINT_PATH)
    age_h = (time.time() - meta["timestamp"]) / 3600

    print("=" * 60)
    print("ESTADO DEL CHECKPOINT DQN")
    print("=" * 60)
    print(f"Path: {CHECKPOINT_PATH}")
    print(f"Episodio:               {meta['episode']}")
    print(f"Epsilon actual:         {meta['epsilon']:.3f}")
    print(f"Replay buffer size:     {meta['buffer_size']}")
    print(f"Edad del checkpoint:    {age_h:.1f}h")
    print(f"Hyperparams: {meta['hyperparams']}")
    print()
    print("Distribucion historica de oponentes:")
    dist = meta.get("opponent_distribution", {})
    total = sum(dist.values())
    if total:
        for name, count in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"  {name:<12} {count:>5} ({count/total:.0%})")
    else:
        print("  (vacio)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--episodes", type=int, default=2000,
        help="Episodios TOTALES objetivo",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Continuar desde checkpoint",
    )
    parser.add_argument(
        "--status", action="store_true", help="Solo mostrar estado",
    )
    parser.add_argument(
        "--max-time-min", type=float, default=None,
        help="Limite de sesion en minutos",
    )
    parser.add_argument("--save-every", type=int, default=50)
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    max_time_s = args.max_time_min * 60 if args.max_time_min else None
    train_session(
        target_total_episodes=args.episodes,
        resume=args.resume,
        max_time_seconds=max_time_s,
        save_every_episodes=args.save_every,
    )


if __name__ == "__main__":
    main()
