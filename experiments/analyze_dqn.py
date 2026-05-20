"""Analiza pesos aprendidos del DQN entrenado."""

import numpy as np
import torch

from polytopia.agents.dqn_bot import DQNNet
from polytopia.agents.features import N_FEATURES
from polytopia.agents.heuristic_bot import HeuristicBot

FEATURE_NAMES = [
    "stars_diff", "cities_diff", "units_diff", "hp_diff",
    "shielded_archers", "exposed_archers",
    "min_dist_to_enemy", "turn_progress",
    "cities_me_abs", "fresh_units", "n_units_me",
    "stars_me_abs", "hp_me_total", "has_ready_attacker",
]
ACTION_NAMES = [
    "MOVE", "ATTACK", "HARVEST", "RECOVER",
    "CAPTURE", "TRAIN", "LEVEL_UP", "END_TURN",
]


def main():
    model = DQNNet()
    model.load_state_dict(torch.load(
        "checkpoints/dqn_nocturno_model.pt", map_location="cpu"
    ))
    W1 = model.net[0].weight.detach().numpy()
    importance = np.linalg.norm(W1, axis=0)

    print("=" * 60)
    print("IMPORTANCIA DE FEATURES (norma L2 columna en primera capa)")
    print("=" * 60)

    print("\nState BEFORE features:")
    state_before = importance[:N_FEATURES]
    for idx in np.argsort(state_before)[::-1]:
        print(f"  {FEATURE_NAMES[idx]:<25} {state_before[idx]:>7.3f}")

    print("\nState AFTER features:")
    state_after = importance[N_FEATURES:2 * N_FEATURES]
    for idx in np.argsort(state_after)[::-1]:
        print(f"  {FEATURE_NAMES[idx]:<25} {state_after[idx]:>7.3f}")

    print("\nAction type features:")
    action_imp = importance[2 * N_FEATURES:]
    for idx in np.argsort(action_imp)[::-1]:
        print(f"  {ACTION_NAMES[idx]:<25} {action_imp[idx]:>7.3f}")

    print("\n" + "=" * 60)
    print("COMPARACION vs PESOS MANUALES (HeuristicBot v3)")
    print("=" * 60)
    hb = HeuristicBot(player_id=0)
    if hasattr(hb, "get_effective_weights"):
        manual = hb.get_effective_weights()
        for name, w in manual.items():
            print(f"  Manual {name:<22} = {w:>+8.2f}")
    else:
        print("HeuristicBot no expone get_effective_weights().")
        print("Para comparacion, agregar ese metodo.")


if __name__ == "__main__":
    main()
