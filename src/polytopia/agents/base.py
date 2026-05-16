from abc import ABC, abstractmethod

from polytopia.interfaces import Action, GameState


class BaseBot(ABC):
    def __init__(self, player_id: int, name: str = "bot"):
        self.player_id = player_id
        self.name = name

    @abstractmethod
    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        ...

    def reset(self) -> None:
        pass
