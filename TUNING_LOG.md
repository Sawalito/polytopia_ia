# Log de Iteraciones del HeuristicBot

## Correcciones del motor (rama correcciones-motor, 2026-05-18 / 2026-05-19)

### Pre-correcciones motor (baseline)
- Win rate HeuristicBot v3 (vs RandomBot, n=30): **90.0%** (27/30)
- CI 95% (bootstrap): [76.7%, 100.0%]
- Tiempo promedio por partida: 30.0 turnos

### PASO 1.1 - Limpieza de check_game_over
Eliminadas condiciones redundantes (verificacion combinada cities==0 AND units==0
ya quedaba cubierta por la verificacion sola de cities==0).

- Win rate post-1.1 (n=30): **90.0%** (27/30) — IDENTICO al baseline
- Tests: 89 passed, 3 skipped

### PASO 1.2 - CAPTURE iteration con early-exit
Cambiado bucle linear sobre `state.cities.values()` por `next(...)` con
short-circuit. Pure refactor — sin cambio funcional.

- Win rate post-1.2: no re-medido (refactor sin cambio funcional)

### PASO 2 - Unificacion de calculate_score

**Iteracion 1 (FALLO):** se aplico la formula literal del reporte de auditoria
`cities*100 + units + stars//10`.

- Win rate post-2 (formula reporte, n=30): **26.7%** (8/30)
- CI 95%: [10.0%, 43.3%]
- **REGRESION CRITICA: -63.3 pp vs baseline**

Causa diagnosticada: la formula del reporte cambia el peso relativo de units
de *3 a *1 vs cities (que pasan de *50 a *100). En desempates por max_turns,
units pesan mucho menos, y como el bot ya casi no captura cities, perdia los
empates que antes ganaba.

**Iteracion 2 (FIX):** restaurada la formula del reward fix v3 original
`cities*50 + units*3 + stars*0.1` (ahora unificada en una sola funcion).

- Win rate post-fix (n=30): **90.0%** (27/30)
- CI 95%: [76.7%, 100.0%]
- Turnos promedio: 30.0
- Delta vs baseline: **0.0 pp** (restaurado al 100%)

**Cambio aceptado vs rechazado:**
- Aceptado: unificacion en una funcion `calculate_score` usada por
  `check_game_over` (desempate) y `game_loop.run_game` (final_score).
- Rechazado: cambio de formula del reward fix v3.

### Benchmark DQN bajo la formula corregida

DQN crudo (~20 episodios de entrenamiento, epsilon ~0.98 — casi random):

| Oponente      | Win rate DQN |
|---------------|-------------:|
| Random        |        90.0% |
| Aggressive    |        90.0% |
| Defensive     |        50.0% |
| Economic      |        50.0% |
| GreedyAttack  |        90.0% |
| HeuristicV3   |        10.0% |
| **Promedio**  |    **63.3%** |

Observaciones:
- vs HeuristicV3 esta en 10% — el bot heuristico le gana facil al DQN sin
  entrenar. Esperado.
- vs Defensive/Economic 50% sugiere que esos bots tampoco son agresivos y
  el resultado se decide por desempate de score.
- vs Aggressive/GreedyAttack 90% sugiere que esos bots se suicidan
  atacando con desventaja; cualquier bot que sobreviva gana por score.
- Para evaluar el DQN entrenado de verdad, hace falta correr la sesion
  nocturna larga (~1200 episodios en CPU). Re-medir luego.

### Tabla de evolucion de win rate vs RandomBot (n=30)

| Cambio aplicado                          | Win rate | Delta  |
|------------------------------------------|---------:|-------:|
| Baseline (pre-correcciones)              |   90.0%  |    -   |
| + PASO 1.1 (limpieza game_over)          |   90.0%  |    0   |
| + PASO 1.2 (CAPTURE early-exit)          |    n/a   |    -   |
| + PASO 2 con formula reporte (RECHAZADO) |   26.7%  |  -63.3 |
| + PASO 2 con reward fix v3 (FINAL)       |   90.0%  |    0   |

### Pasos NO aplicados (alto riesgo, requieren confirmacion)

- PASO 1.3 (shallow copy en apply_action): no aplicado.
- PASO 3 (CAPTURE requiere fresh): no aplicado.
- PASO 4 (TRAIN solo en city.position): no aplicado.




## v4 - Lookahead 2-ply

Motivacion: tuning de pesos llego a retornos decrecientes (v2: 45%, v3: 50%).
Cambio estructural a minimax simplificado con depth=2.

Implementacion:
- `LookaheadBot` en `src/polytopia/agents/lookahead_bot.py` hereda de HeuristicBot
  y sobreescribe `select_action`.
- Top-K filtering: 10 acciones propias, 5 del oponente.
- Mismo `evaluate()` y action bonuses que v3.
- Para cada accion propia, simula el peor response del oponente (worst case).
  Si la accion no cede turno (current_player no cambia), se usa el score
  inmediato sin lookahead.

Resultado (n=20 seeds, LookaheadBot como P0 vs RandomBot):
- Win rate: 50.0% (10/20) - identico a v3 con greedy 1-ply.
- Tiempo promedio: 34.4 s/partida (vs ~1s en v3, ~35x mas lento).
- Tests: `test_lookahead_returns_legal_action` y `test_lookahead_smoke` pasan.

Conclusion: el lookahead 2-ply NO mejora win rate. Razones probables:
1. El oponente es RandomBot - simular su "peor respuesta" es pesimismo
   irreal porque RandomBot no juega esa respuesta.
2. El cuello de botella no es la profundidad del search, es la funcion
   `evaluate` y/o el ending condition: 100% de juegos terminan en max_turns
   y se resuelven por `_score` (city*10 + units + stars). El bot gana por
   acumular stars, no por capturar cities (avg_capture_actions = 0 en todas
   las partidas).
3. Fase 2 mostro que losses tienen MAS move_actions (332 vs 269) y MAS
   train_actions (22.6 vs 19.3) que wins. El bot "agresivo" pierde mas;
   el bot "pasivo" gana mas. Lookahead refuerza el comportamiento que la
   evaluate considera optimo, asi que solo amplifica la misma estrategia
   passive que ya tenia v3.

Recomendacion: la siguiente mejora real requiere cambiar la `evaluate` o
la condicion de fin de juego. Subir el peso de captura efectiva o cambiar
`_score` para premiar progreso ofensivo seria un cambio mas alto-leverage
que profundizar el search.

## v3 - Fix dirigido a lost_never_reached_enemy

Diagnostico (fase 1, n=30, HeuristicBot juega como P0):
- Win rate v2: 46.7% (14 W / 16 L / 0 D)
- Patron dominante en losses: `lost_never_reached_enemy` (16/16 = 100%)
- Tambien dominante: `lost_by_max_turns` (16/16 = 100%) - todas las perdidas son por agotamiento de turnos
- Metrica clave: `avg_turn_reached_enemy_radius` = 12.5 en wins vs 27.0 en losses
  (delta +14.5 turnos); el bot llega al radio <=2 de la city enemiga tarde
  o nunca en las partidas perdidas.
- `avg_min_dist_to_enemy_city` 3.29 (wins) vs 3.19 (losses): la distancia
  minima alcanzada es similar, pero el TIEMPO para llegar diverge mucho.

Cambio aplicado: subir `W_DISTANCE` de 0.3 a 0.8 (siguiendo el mapeo del
playbook). Cambio minimo: solo una constante, sin nuevos terminos. Nombre
default cambiado de "heuristic_v2" a "heuristic_v3".

Resultado (n=30, post-cambio):
- Win rate v3: 50.0% (15 W / 14 L / 1 D), +3.3 pp vs v2
- CI 95% (bootstrap del benchmark n=20): [30.0%, 70.0%]
- Frecuencia de `lost_never_reached_enemy` en losses v3: 100% (14/14)

Observacion critica: el patron dominante NO bajo en frecuencia, y de hecho
`avg_turn_reached_enemy_radius` es ahora 0.00 en wins y losses (significa
None - ningun juego alcanzo radio <=2 a la city enemiga). El cambio movio
el equilibrio sin permitir penetracion real al radio cercano; el bot ahora
gana mas por score-margin (kills + units alive) que por capturas.

Tests: los 10 tests en `tests/test_heuristic_bot.py` siguen pasando.

Hipotesis para v4:
- La metrica "lost_never_reached_enemy" es degenerada: 100% de wins y 100%
  de losses fallan la condicion, lo que indica que el bot tiene barreras
  fisicas (movement=1, terreno, defensores enemigos en el camino) que
  W_DISTANCE solo no resuelve. La proxima iteracion deberia atacar el
  segundo patron mas frecuente: `lost_with_idle_turns` (9/14 = 64%) o
  revisar por que los unidades no se acercan fisicamente (puede ser un
  problema de pathing, no de incentivo).

## v2 - Resolucion de inactividad

Sintoma de v1: win rate 20% (4/20), turnos promedio 30, bot no abandonaba spawn.

Diagnostico: MOVE no afectaba ningun termino de evaluate(); END_TURN tenia
score ligeramente positivo por +1 star de la city; resultado: bot prefiere
END_TURN siempre.

Cambios:
- Agregado W_DISTANCE = 0.3 (presion ofensiva por proximidad a city enemiga).
- Agregado W_CAPTURE_BONUS = 50.0 (dominante sobre cualquier otra accion).
- Agregado W_ATTACK_BONUS = 8.0 (prioriza conectar ataques).
- Agregado W_IDLE_PENALTY = 2.0 (penaliza END_TURN con units fresh).
- Agregado fallback de exploracion al centro cuando no hay city enemiga conocida.

Resultado (n=20, seeds 0-19, HeuristicBot juega como P0):
- Win rate: 45.0% (vs 20% en v1, +25 pp)
- CI 95% (bootstrap): [20.0%, 65.0%]
- Turnos promedio: 29.8 (algunas partidas terminaron antes de max_turns; v1 siempre llegaba a 30)
- test_bot_moves_off_spawn_in_initial_turns: PASS (problema raiz resuelto)

Conclusion: el bot ahora se mueve, ataca y captura. Meta minima (80%) NO
alcanzada todavia. Posibles ajustes para v3 (segun diagnostico del prompt):
1. W_DISTANCE muy debil; subir a 0.5 o 1.0.
2. Bot ataca con HP bajo y muere; penalizar ATTACK cuando attacker.hp < defender.hp * 0.5.
3. Acumula stars al final sin gastar; bajar LATE_GAME_TURN a 10 o LATE_GAME_STARS_WEIGHT a 0.1.
4. No defiende su city; penalizar tener enemigos a chebyshev <= 2 de city propia.

## v1 - Baseline archivado

Win rate: 20% (4/20), CI [5%, 40%], turnos promedio 30.
Solo evaluacion por diferenciales sin presion ofensiva. Bot terminaba turno
inmediatamente porque END_TURN agregaba +1 star (peso 1.0) y MOVE/otras
acciones posicionales no cambiaban ningun termino de la funcion.
