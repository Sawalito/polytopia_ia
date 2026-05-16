from polytopia.agents.base import BaseBot
from polytopia.interfaces import Action, GameState


class HeuristicBot(BaseBot):
    """STUB. Persona B implementa la heurística aquí.

    Sugerencias:
    - Score de estado: stars + units_value + cities_value*10 - distance_to_enemy.
    - State machine: ECONOMY (turnos 1-10) -> EXPANSION (11-20) -> ATTACK (21-30).
    - O greedy: max sobre evaluate(apply_action(state, a)).

    Métodos sugeridos:
    - evaluate_state(state) -> float
    - select_action(state, legal_actions): elige la acción que maximiza
      evaluate_state tras aplicarla.
    """

    def select_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        raise NotImplementedError("Persona B - implementar heurística")
