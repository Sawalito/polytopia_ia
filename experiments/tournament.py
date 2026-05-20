"""Torneo round-robin: cada bot contra cada bot, N partidas por matchup,
alternando P0 y P1 para neutralizar sesgo de inicio."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from polytopia.agents.aggressive_bot import AggressiveBot
from polytopia.agents.defensive_bot import DefensiveBot
from polytopia.agents.economic_bot import EconomicBot
from polytopia.agents.greedy_attack_bot import GreedyAttackBot
from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game


BOT_FACTORIES = {
    "Random": lambda pid, seed: RandomBot(player_id=pid, seed=seed),
    "Aggressive": lambda pid, seed: AggressiveBot(player_id=pid, seed=seed),
    "Defensive": lambda pid, seed: DefensiveBot(player_id=pid, seed=seed),
    "Economic": lambda pid, seed: EconomicBot(player_id=pid, seed=seed),
    "GreedyAttack": lambda pid, seed: GreedyAttackBot(player_id=pid, seed=seed),
    "HeuristicV3": lambda pid, seed: HeuristicBot(player_id=pid, seed=seed),
}


def run_matchup(bot_a_name: str, bot_b_name: str, n_seeds: int = 20) -> dict:
    """Corre n_seeds partidas entre bot_a y bot_b alternando P0/P1."""
    factory_a = BOT_FACTORIES[bot_a_name]
    factory_b = BOT_FACTORIES[bot_b_name]

    wins_a = 0
    wins_b = 0
    draws = 0
    total_turns: list[int] = []
    times_per_game: list[float] = []

    for seed in range(n_seeds):
        a_as_p0 = seed % 2 == 0

        state = create_initial_state(seed=seed)
        if a_as_p0:
            bot0 = factory_a(0, seed)
            bot1 = factory_b(1, seed + 5000)
        else:
            bot0 = factory_b(0, seed + 5000)
            bot1 = factory_a(1, seed)

        start = time.time()
        result = run_game(bot0, bot1, state)
        times_per_game.append(time.time() - start)
        total_turns.append(result["final_turn"])

        winner = result["winner"]
        if winner is None:
            draws += 1
        elif (winner == 0 and a_as_p0) or (winner == 1 and not a_as_p0):
            wins_a += 1
        else:
            wins_b += 1

    win_rate_a = wins_a / n_seeds
    ci_low, ci_high = _bootstrap_ci(wins_a, n_seeds)

    return {
        "bot_a": bot_a_name,
        "bot_b": bot_b_name,
        "n_seeds": n_seeds,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "draws": draws,
        "win_rate_a": win_rate_a,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "avg_turns": sum(total_turns) / len(total_turns),
        "avg_time_per_game": sum(times_per_game) / len(times_per_game),
    }


def _bootstrap_ci(
    wins: int, total: int, n_resamples: int = 2000
) -> tuple[float, float]:
    rng = random.Random(42)
    outcomes = [1] * wins + [0] * (total - wins)
    rates = []
    for _ in range(n_resamples):
        sample = [rng.choice(outcomes) for _ in range(total)]
        rates.append(sum(sample) / len(sample))
    rates.sort()
    return rates[int(n_resamples * 0.025)], rates[int(n_resamples * 0.975)]


def run_tournament(
    bot_names: list[str] | None = None,
    n_seeds: int = 20,
) -> dict:
    if bot_names is None:
        bot_names = list(BOT_FACTORIES.keys())

    total_matchups = len(bot_names) * (len(bot_names) - 1) // 2
    print(f"Torneo round-robin: {len(bot_names)} bots, n_seeds={n_seeds}")
    print(f"Bots: {bot_names}")
    print(f"Total matchups: {total_matchups}")
    print()

    matchups: list[dict] = []
    matrix: dict[str, dict[str, float | None]] = {
        a: {b: None for b in bot_names} for a in bot_names
    }

    start_time = time.time()
    matchup_idx = 0

    for i, bot_a in enumerate(bot_names):
        for j, bot_b in enumerate(bot_names):
            if i >= j:
                continue
            matchup_idx += 1
            print(
                f"[{matchup_idx}/{total_matchups}] {bot_a} vs {bot_b}...",
                end=" ",
                flush=True,
            )
            mu_start = time.time()
            r = run_matchup(bot_a, bot_b, n_seeds=n_seeds)
            matchups.append(r)
            elapsed = time.time() - mu_start
            print(
                f"{r['wins_a']}-{r['wins_b']}-{r['draws']} "
                f"({r['win_rate_a']:.0%}, {elapsed:.1f}s)"
            )

            matrix[bot_a][bot_b] = r["win_rate_a"]
            matrix[bot_b][bot_a] = 1 - r["win_rate_a"] - (r["draws"] / n_seeds)

    for b in bot_names:
        matrix[b][b] = 0.5

    ranking = []
    for bot in bot_names:
        wins_avg = sum(
            matrix[bot][other] for other in bot_names if other != bot
        ) / (len(bot_names) - 1)
        ranking.append((bot, wins_avg))
    ranking.sort(key=lambda x: x[1], reverse=True)

    total_time = time.time() - start_time

    return {
        "bots": bot_names,
        "n_seeds": n_seeds,
        "matrix": matrix,
        "matchups": matchups,
        "ranking": ranking,
        "total_time": total_time,
    }


def print_tournament_table(results: dict) -> None:
    bots = results["bots"]
    matrix = results["matrix"]

    print()
    print("=" * 80)
    print("MATRIZ DE WIN RATES (filas = bot fila vs columna)")
    print("=" * 80)

    print(f"{'':<14}", end="")
    for b in bots:
        print(f"{b:>13}", end="")
    print()

    for bot_row in bots:
        print(f"{bot_row:<14}", end="")
        for bot_col in bots:
            val = matrix[bot_row][bot_col]
            if val is None or bot_row == bot_col:
                print(f"{'    -    ':>13}", end="")
            else:
                print(f"{val * 100:>11.0f}%", end="  ")
        print()

    print()
    print("=" * 80)
    print("RANKING (win rate promedio)")
    print("=" * 80)
    for rank, (bot, wr) in enumerate(results["ranking"], 1):
        print(f"  {rank}. {bot:<14} {wr * 100:>5.1f}%")
    print()


def save_tournament(results: dict, path: str) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    serializable = {
        "bots": results["bots"],
        "n_seeds": results["n_seeds"],
        "matrix": {
            a: dict(row.items()) for a, row in results["matrix"].items()
        },
        "matchups": results["matchups"],
        "ranking": results["ranking"],
        "total_time": results["total_time"],
    }
    with open(out_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"Resultados guardados en {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--output", type=str, default="reports/tournament.json")
    parser.add_argument(
        "--bots",
        type=str,
        nargs="+",
        default=None,
        help="Subset de bots a usar",
    )
    args = parser.parse_args()

    results = run_tournament(bot_names=args.bots, n_seeds=args.seeds)
    print_tournament_table(results)
    save_tournament(results, args.output)


if __name__ == "__main__":
    main()
