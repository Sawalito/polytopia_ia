# Siguientes pasos por persona

## Persona A — Engine
- Optimizar legal_actions (probablemente la función más llamada del juego).
- Tests de stress: 100 partidas random-vs-random deben completar sin excepciones.
- Considerar agregar Action.RESEARCH si el equipo habilita árbol tecnológico.

## Persona B — Agentes
- Implementar HeuristicBot.select_action en src/polytopia/agents/heuristic_bot.py.
- Empezar con plantilla greedy:

  def select_action(self, state, legal_actions):
      from polytopia.engine.rules import apply_action
      best_action = max(legal_actions, key=lambda a: self.evaluate(apply_action(state, a)))
      return best_action

  def evaluate(self, state) -> float:
      me, opp = self.player_id, 1 - self.player_id
      cities_me = len([c for c in state.cities.values() if c.owner == me])
      cities_opp = len([c for c in state.cities.values() if c.owner == opp])
      units_me = [u for u in state.units.values() if u.owner == me]
      units_opp = [u for u in state.units.values() if u.owner == opp]
      hp_me = sum(u.hp for u in units_me)
      hp_opp = sum(u.hp for u in units_opp)
      return (
          (state.stars[me] - state.stars[opp])
          + 10 * (cities_me - cities_opp)
          + 0.5 * (hp_me - hp_opp)
      )

- Iterar pesos. Si pierde contra RandomBot, debug; si gana 80%+, pasar a MCTS o
  state machine por fase de juego.

## Persona C — Interfaz y métricas
- Implementar renderers/pygame_gui.py con visualización 2D top-down.
- Implementar tournament.py: correr N partidas en paralelo con seeds distintos.
- Generar plots: winrate, turnos promedio, distribución de scores.
- Bootstrap CIs para reportar diferencias entre versiones del bot.

## Para todos
- Una vez que HeuristicBot gane 80% vs RandomBot, torneo con n_seeds=20 y reportar
  bootstrap CIs.
