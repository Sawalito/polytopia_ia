import time
from polytopia.agents.lookahead_bot import LookaheadBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game


def benchmark_lookahead(n_seeds: int = 20) -> dict:
    wins = 0
    total_time = 0.0
    for seed in range(n_seeds):
        state = create_initial_state(seed=seed)
        bot0 = LookaheadBot(player_id=0, seed=seed)
        bot1 = RandomBot(player_id=1, seed=seed + 1000)
        start = time.time()
        result = run_game(bot0, bot1, state)
        elapsed = time.time() - start
        total_time += elapsed
        if result["winner"] == 0:
            wins += 1
        print(f"Seed {seed}: winner=P{result['winner']}, t={elapsed:.1f}s")
    return {
        "win_rate": wins / n_seeds,
        "wins": wins,
        "total": n_seeds,
        "avg_time_per_game": total_time / n_seeds,
    }


if __name__ == "__main__":
    result = benchmark_lookahead(n_seeds=20)
    print(f"\nLookaheadBot vs RandomBot: {result['wins']}/{result['total']} "
          f"({result['win_rate']*100:.1f}%)")
    print(f"Tiempo promedio: {result['avg_time_per_game']:.2f}s/partida")
