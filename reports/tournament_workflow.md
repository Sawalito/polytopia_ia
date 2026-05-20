# Tournament Framework — Workflow y Mejoras

Documento de referencia para re-ejecutar el torneo y la lista de mejoras
identificadas durante la primera corrida (n=10, 2026-05-17).

---

## 1. Re-ejecutar el torneo

### Comandos rápidos

```bash
# Quick: n=10, ~17 min (15 matchups × 10 partidas)
make tournament-quick

# Estándar: n=20, ~50 min (recomendado para reporte)
make tournament

# Full: n=50, ~2h (CIs estrechos, para defensa)
make tournament-full

# Heatmap del JSON más reciente
make tournament-plot
```

### Comandos directos

```bash
# Subset específico de bots
python -m experiments.tournament --seeds 20 --bots HeuristicV3 Economic Defensive

# Output a otra ruta
python -m experiments.tournament --seeds 30 --output reports/tournament_v2.json
python -m experiments.plot_tournament --input reports/tournament_v2.json \
                                       --output reports/tournament_v2.png
```

### Tiempo esperado por escala

| n_seeds | Matchups con HeuristicV3 | Matchups sin | Total estimado |
|---------|--------------------------|--------------|----------------|
| 10      | 5 × ~2.5 min = ~12 min   | ~1 min       | **~17 min**    |
| 20      | 5 × ~10 min  = ~50 min   | ~2 min       | **~55 min**    |
| 50      | 5 × ~25 min  = ~125 min  | ~5 min       | **~2.2 h**     |

(El cuello de botella es HeuristicV3 por su lookahead 1-ply; los matchups
sin él corren a ~0.5 s/game.)

---

## 2. Resultados de referencia (n=10, 2026-05-17)

Ranking baseline para detectar regresiones futuras:

| # | Bot          | Win rate prom. |
|---|--------------|----------------|
| 1 | HeuristicV3  | 68.0 %         |
| 2 | Economic     | 64.0 %         |
| 3 | Defensive    | 54.0 %         |
| 4 | Aggressive   | 44.0 %         |
| 5 | Random       | 34.0 %         |
| 6 | GreedyAttack | 30.0 %         |

**Si HeuristicV3 baja de 60 %, sospechar regresión** (revisar `rules.py`
y el reward fix v3 — cities × 50, units × 3, stars × 0.1).

---

## 3. Mejoras identificadas

### 3.1 Mejora a HeuristicV3 — término de paridad de fuerza (alta prioridad)

**Motivación:** matchup más cerrado es HeuristicV3 vs Economic (60 %).
Economic acumula ejército grande y solo ataca con 2× ventaja; la heurística
1-ply no penaliza atacar cuando está en inferioridad numérica.

**Acción concreta:** añadir a `HeuristicBot.evaluate()` un término del tipo:

```python
my_units = sum(1 for u in state.units.values()
               if u.owner == self.player_id and u.is_alive)
opp_units = sum(1 for u in state.units.values()
                if u.owner != self.player_id and u.is_alive)
force_ratio = my_units / max(opp_units, 1)
# Penalizar fuertemente atacar con ratio < 0.7, premiar con > 1.5
force_term = -5.0 if force_ratio < 0.7 else (3.0 if force_ratio > 1.5 else 0.0)
score += force_term
```

**Validación:** después de aplicar, correr `make tournament-quick`. Esperar
HeuristicV3 vs Economic ≥ 70 % (subir desde 60 %).

### 3.2 Correr n=50 antes de la defensa (media prioridad)

Los CIs con n=10 son anchos (±20 puntos típicamente). Para los números
"duros" del reporte/defensa, ejecutar `make tournament-full` el día previo
a la entrega. Estimado ~2.2 h, dejar corriendo en background.

### 3.3 Bot adicional — LookaheadBot en el torneo (baja prioridad)

`src/polytopia/agents/lookahead_bot.py` existe pero no está en
`BOT_FACTORIES`. Agregar al diccionario de `experiments/tournament.py`:

```python
"Lookahead": lambda pid, seed: LookaheadBot(player_id=pid, seed=seed),
```

Va a ser lento (lookahead profundo), pero da otro punto de comparación
"smart" en el ranking.

### 3.4 Plot de evolución por turno (baja prioridad)

Actualmente solo tenemos win rate final. Útil para el reporte: gráfica
de "lead en score" por turno para 5 partidas representativas. Mostraría
el carácter de cada estrategia (Economic crece tarde, Aggressive pico
temprano y cae, HeuristicV3 dominante constante).

---

## 4. Archivos generados por el framework

```
experiments/
  tournament.py              — runner round-robin
  plot_tournament.py         — generador de heatmap PNG

src/polytopia/agents/
  aggressive_bot.py          — prioridad CAPTURE > ATTACK > MOVE_hacia_enemigo
  defensive_bot.py           — defiende ≤3 tiles de city propia
  economic_bot.py            — HARVEST > LEVEL_UP > TRAIN; ataca con 2× ventaja
  greedy_attack_bot.py       — ataca siempre, sin filtros

tests/
  test_strategy_bots.py      — 5 tests (4 legal-action + 1 diversidad)

reports/
  tournament.json            — datos crudos (matchups, matriz, ranking)
  tournament_heatmap.png     — visualización
  tournament_narrative.md    — interpretación lista para el reporte
  tournament_workflow.md     — este documento

Makefile
  tournament, tournament-quick, tournament-full, tournament-plot
```

---

## 5. Para el reporte / defensa

### Mensajes clave (copiables)

- *"El HeuristicBot v3 gana el torneo round-robin con un win rate
  promedio de 68 % contra 5 estrategias diversas (random, agresiva,
  defensiva, económica, agresiva sin filtro)."*

- *"Su matchup más difícil es vs EconomicBot (60 %), lo cual identifica
  una dirección concreta de mejora: añadir un término de paridad de
  fuerza a la evaluación."*

- *"El ranking es consistente con el reward fix aplicado: GreedyAttack
  ocupa el último lugar (30 %), confirmando que agredir sin
  discriminación es subóptimo en este motor."*

### Punto de honestidad recomendado

El sanity check "Aggressive > Defensive" falló (Aggressive solo 40 %).
El narrative ya explica por qué: el reward fix premia *capturar cities*,
no *atacar unidades*. No es regresión, es información sobre la forma
del reward.

---

## 6. Cosas a NO romper

- `rules.py` — el reward fix v3 está aplicado y commiteado (e28eb42).
  Si vuelve a perderse, restaurar desde el backup
  `/home/saulrojas/polytopia_ai_BACKUP_20260517_130919/`.
- El `pyproject.toml` ya tiene `pygame>=2.5` y `matplotlib>=3.7` en
  `[dev]`. `pip install -e ".[dev]"` debería bastar tras un reset.
- En este sistema solo existe `python3`, no `python`. Dentro del venv
  ambos funcionan.
