import random

from polytopia.agents.base import BaseBot
from polytopia.interfaces import Action, ActionType, GameState


class RandomBot(BaseBot):
    """Baseline: random legal action, biased against ending the turn until there
    is nothing else to do."""

    def __init__(self, player_id: int, seed: int = 42, name: str = "random"):
        super().__init__(player_id, name)
        self.rng = random.Random(seed)

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        non_end = [a for a in legal_actions if a.action_type != ActionType.END_TURN]
        if non_end and self.rng.random() < 0.7:
            return self.rng.choice(non_end)
        return next(a for a in legal_actions if a.action_type == ActionType.END_TURN)
