"""LookaheadBot: heuristica con search 2-ply (minimax simplificado).

Estrategia:
- Para cada accion legal del bot, simular apply_action.
- Para el estado resultante, simular la peor respuesta del oponente
  (la que minimiza el score del bot segun la misma evaluate).
- Elegir la accion del bot que maximiza el score despues de la respuesta
  pessima del oponente.

Esto es minimax con depth=2 (un ply propio + un ply del oponente).

Optimizaciones:
- Top-k filtering: solo simular las top K acciones segun pre-evaluacion.
- Sin caching de evaluate (puede agregarse si lookahead es muy lento).
"""

from __future__ import annotations

from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action
from polytopia.interfaces import Action, GameState


class LookaheadBot(HeuristicBot):
    """Hereda toda la logica de HeuristicBot (evaluate, action bonuses, etc.)
    pero sobreescribe select_action para hacer lookahead 2-ply."""

    OPPONENT_TOP_K = 5
    SELF_TOP_K = 10

    def __init__(self, player_id: int, name: str = "lookahead_v1", seed: int = 42):
        super().__init__(player_id, name, seed)

    def select_action(self, state: GameState, my_legal_actions: list[Action]) -> Action:
        # Pre-filtrar mis acciones por evaluacion greedy rapida.
        if len(my_legal_actions) <= self.SELF_TOP_K:
            candidate_actions = my_legal_actions
        else:
            scored = []
            for a in my_legal_actions:
                state_after_me = apply_action(state, a)
                quick_score = (
                    self.evaluate(state_after_me)
                    + self._action_type_bonus(state, a)
                )
                scored.append((quick_score, a))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            candidate_actions = [a for _, a in scored[:self.SELF_TOP_K]]

        best_action = candidate_actions[0]
        best_worst_case = float("-inf")

        for my_action in candidate_actions:
            state_after_me = apply_action(state, my_action)
            my_immediate_score = (
                self.evaluate(state_after_me)
                + self._action_type_bonus(state, my_action)
            )

            # Si la accion mantiene mi turno (no END_TURN), no hay respuesta del
            # oponente. El motor decide si el turno pasa o no.
            if state_after_me.current_player == self.player_id:
                worst_case_score = my_immediate_score
            else:
                opp_actions = legal_actions(state_after_me, state_after_me.current_player)
                if not opp_actions:
                    worst_case_score = my_immediate_score
                else:
                    # Top-K filtering del oponente
                    if len(opp_actions) <= self.OPPONENT_TOP_K:
                        opp_candidates = opp_actions
                    else:
                        opp_scored = []
                        for oa in opp_actions:
                            state_after_opp = apply_action(state_after_me, oa)
                            score_for_me = self.evaluate(state_after_opp)
                            opp_scored.append((score_for_me, oa))
                        opp_scored.sort(key=lambda pair: pair[0])
                        opp_candidates = [a for _, a in opp_scored[:self.OPPONENT_TOP_K]]

                    worst_score_after_opp = float("inf")
                    for opp_action in opp_candidates:
                        state_after_opp = apply_action(state_after_me, opp_action)
                        score = self.evaluate(state_after_opp)
                        if score < worst_score_after_opp:
                            worst_score_after_opp = score

                    worst_case_score = worst_score_after_opp

            worst_case_score += self._rng.uniform(0, self.JITTER_MAX)

            if worst_case_score > best_worst_case:
                best_worst_case = worst_case_score
                best_action = my_action

        return best_action
