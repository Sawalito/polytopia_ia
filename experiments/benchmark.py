"""Benchmark del HeuristicBot vs RandomBot.

Corre N partidas con seeds distintos y reporta win rate, turnos promedio
y un intervalo de confianza bootstrap del win rate.
"""

from __future__ import annotations

import argparse
import random

from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game


def run_benchmark(
    n_seeds: int = 20,
    heuristic_plays_as: int = 0,
) -> dict:
    """Corre n_seeds partidas heuristic vs random.

    Args:
        n_seeds: numero de partidas (= numero de seeds distintas).
        heuristic_plays_as: 0 si HeuristicBot es P0, 1 si es P1.

    Returns:
        Diccionario con metricas.
    """
    heuristic_wins = 0
    random_wins = 0
    draws = 0
    final_turns = []

    for seed in range(n_seeds):
        state = create_initial_state(seed=seed)

        if heuristic_plays_as == 0:
            bot0 = HeuristicBot(player_id=0, seed=seed)
            bot1 = RandomBot(player_id=1, seed=seed + 1000)
        else:
            bot0 = RandomBot(player_id=0, seed=seed + 1000)
            bot1 = HeuristicBot(player_id=1, seed=seed)

        result = run_game(bot0, bot1, state)

        winner = result["winner"]
        if winner == heuristic_plays_as:
            heuristic_wins += 1
        elif winner == 1 - heuristic_plays_as:
            random_wins += 1
        else:
            draws += 1

        final_turns.append(result["final_turn"])

    win_rate = heuristic_wins / n_seeds
    avg_turns = sum(final_turns) / len(final_turns)

    # Bootstrap CI del win rate
    ci_low, ci_high = _bootstrap_ci(
        wins=heuristic_wins,
        total=n_seeds,
        n_resamples=2000,
    )

    return {
        "n_seeds": n_seeds,
        "heuristic_plays_as": heuristic_plays_as,
        "heuristic_wins": heuristic_wins,
        "random_wins": random_wins,
        "draws": draws,
        "win_rate": win_rate,
        "win_rate_ci_low": ci_low,
        "win_rate_ci_high": ci_high,
        "avg_turns": avg_turns,
    }


def _bootstrap_ci(wins: int, total: int, n_resamples: int = 2000) -> tuple[float, float]:
    """Bootstrap 95% CI del win rate basado en outcomes binarios."""
    rng = random.Random(42)
    outcomes = [1] * wins + [0] * (total - wins)
    rates = []
    for _ in range(n_resamples):
        sample = [rng.choice(outcomes) for _ in range(total)]
        rates.append(sum(sample) / len(sample))
    rates.sort()
    low = rates[int(n_resamples * 0.025)]
    high = rates[int(n_resamples * 0.975)]
    return low, high


def print_results(results: dict) -> None:
    print()
    print("=" * 60)
    print("BENCHMARK: HeuristicBot vs RandomBot")
    print("=" * 60)
    print(f"Partidas:            {results['n_seeds']}")
    print(f"HeuristicBot juega:  P{results['heuristic_plays_as']}")
    print(f"Victorias heuristic: {results['heuristic_wins']}")
    print(f"Victorias random:    {results['random_wins']}")
    print(f"Empates:             {results['draws']}")
    print(f"Win rate:            {results['win_rate']*100:.1f}%")
    print(f"  CI 95% (bootstrap): "
          f"[{results['win_rate_ci_low']*100:.1f}%, "
          f"{results['win_rate_ci_high']*100:.1f}%]")
    print(f"Turnos promedio:     {results['avg_turns']:.1f}")
    print("=" * 60)

    if results['win_rate'] >= 0.80:
        print("META MINIMA ALCANZADA (>= 80% win rate).")
    else:
        print("META MINIMA NO ALCANZADA. Considerar ajustar pesos.")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20, help="numero de seeds")
    parser.add_argument("--as", dest="plays_as", type=int, choices=[0, 1], default=0)
    args = parser.parse_args()

    results = run_benchmark(n_seeds=args.n, heuristic_plays_as=args.plays_as)
    print_results(results)


if __name__ == "__main__":
    main()
