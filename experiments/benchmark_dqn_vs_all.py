"""Benchmarkea el DQN entrenado vs todos los bots del tournament."""

from polytopia.agents.aggressive_bot import AggressiveBot
from polytopia.agents.defensive_bot import DefensiveBot
from polytopia.agents.dqn_bot import DQNBot
from polytopia.agents.economic_bot import EconomicBot
from polytopia.agents.greedy_attack_bot import GreedyAttackBot
from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game


OPPONENTS = [
    ("Random", lambda s: RandomBot(player_id=1, seed=s + 1000)),
    ("Aggressive", lambda s: AggressiveBot(player_id=1, seed=s + 1000)),
    ("Defensive", lambda s: DefensiveBot(player_id=1, seed=s + 1000)),
    ("Economic", lambda s: EconomicBot(player_id=1, seed=s + 1000)),
    ("GreedyAttack", lambda s: GreedyAttackBot(player_id=1, seed=s + 1000)),
    ("HeuristicV3", lambda s: HeuristicBot(player_id=1, seed=s + 1000)),
]


def main():
    print("DQN vs todos los bots (n=20 por matchup):")
    print("=" * 50)
    results = {}
    for name, factory in OPPONENTS:
        wins = 0
        for seed in range(20):
            state = create_initial_state(seed=seed)
            bot0 = DQNBot.load(
                "checkpoints/dqn_nocturno_model.pt", player_id=0, seed=seed,
            )
            bot1 = factory(seed)
            result = run_game(bot0, bot1, state)
            if result["winner"] == 0:
                wins += 1
        wr = wins / 20
        results[name] = wr
        print(f"  vs {name:<14} {wins:>3}/20 ({wr:.0%})")

    avg = sum(results.values()) / len(results)
    print(f"\nWin rate promedio: {avg:.0%}")


if __name__ == "__main__":
    main()
