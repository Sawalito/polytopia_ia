from collections import Counter

import pytest

from polytopia.agents.aggressive_bot import AggressiveBot
from polytopia.agents.defensive_bot import DefensiveBot
from polytopia.agents.economic_bot import EconomicBot
from polytopia.agents.greedy_attack_bot import GreedyAttackBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.state_init import create_initial_state


@pytest.mark.parametrize(
    "bot_class",
    [AggressiveBot, DefensiveBot, EconomicBot, GreedyAttackBot],
)
def test_bot_returns_legal_action(bot_class):
    state = create_initial_state(seed=42)
    bot = bot_class(player_id=0)
    actions = legal_actions(state, 0)
    chosen = bot.select_action(state, actions)
    assert chosen in actions


def test_bots_are_actually_different():
    """Los bots deben tomar decisiones distintas en el mismo estado.

    Probamos varios seeds: en al menos uno, los 4 bots deben elegir
    al menos 2 tipos de accion diferentes.
    """
    bots = [
        AggressiveBot(player_id=0, seed=1),
        DefensiveBot(player_id=0, seed=1),
        EconomicBot(player_id=0, seed=1),
        GreedyAttackBot(player_id=0, seed=1),
    ]

    diversity_found = False
    for seed in range(10):
        state = create_initial_state(seed=seed)
        actions = legal_actions(state, 0)
        if len(actions) < 3:
            continue
        chosen_types: Counter = Counter()
        for bot in bots:
            choice = bot.select_action(state, actions)
            chosen_types[choice.action_type] += 1
        if len(chosen_types) >= 2:
            diversity_found = True
            break

    assert diversity_found, "Ningun seed produjo decisiones diferentes entre bots"
