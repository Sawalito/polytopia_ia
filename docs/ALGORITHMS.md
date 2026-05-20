# Algoritmos: reglas del juego, bots y DQN

Este documento describe **matemáticamente** las reglas del simulador y cada agente del proyecto. La idea es que se pueda reproducir todo a mano (o auditarlo) leyendo solo este archivo.

Convenciones:

- **`s`** denota un `GameState`, **`a`** una `Action`, **`p`** un jugador (0 o 1), **`u`** una unidad.
- `d(x, y) = max(|x.x − y.x|, |x.y − y.y|)` es la distancia de Chebyshev (rey de ajedrez). Está implementada en `Position.chebyshev_distance` (`src/polytopia/interfaces.py:65`).
- Las funciones puras del motor (`apply_action`, `legal_actions`, `resolve_combat`) **no mutan el estado**: hacen `copy.deepcopy(state)` y devuelven uno nuevo (`engine/rules.py:135`). Esto es lo que permite que todos los bots heurísticos / lookahead / DQN simulen libremente.

Para resultados empíricos (matriz de torneo, win rates, sanity checks), ver [`reports/tournament_narrative.md`](../reports/tournament_narrative.md). Este doc cubre el **cómo funcionan**; el narrative cubre el **qué pasó cuando los comparamos**.

---

## 1. Reglas del juego

Polytopia simplificado, 2 jugadores, mapa cuadrado con niebla de guerra.

### 1.1 Mapa y estado inicial

- **Tamaño:** `board_size = 11` (configurable, default en `engine/state_init.py:9`).
- **Borde de agua:** todas las casillas con `x ∈ {0, size−1}` o `y ∈ {0, size−1}` son `WATER` y por tanto no transitables (`engine/map_gen.py:66`).
- **Interior:** se reparte por fracciones aproximadas con un jitter de ±2 sobre el conteo objetivo:

| Terreno    | Fracción del interior | Pasable | Notas |
|------------|-----------------------|---------|-------|
| `FIELD`    | ~60 %                 | sí      | puede contener `FRUIT` con p = 0.30 |
| `FOREST`   | ~20 %                 | sí      | puede contener `ANIMAL` con p = 0.30 |
| `MOUNTAIN` | ~10 %                 | **no**  |       |
| `WATER`    | ~10 %                 | **no**  | crece en 1–2 lagos por flood fill |

- **Posiciones iniciales:** `P0` en `(1, 1)`, `P1` en `(size−2, size−2)`.
- **Cada jugador empieza con:**
  - 1 `City` en su starting position, nivel 1.
  - 1 `WARRIOR` en la misma casilla.
  - `INITIAL_STARS = 5` (`engine/state_init.py:4`).
  - Niebla inicial: visible solo en un círculo de Chebyshev radio 2 alrededor del spawn.
- **Duración:** `max_turns = 30` por defecto. Pasados los 30 turnos el juego termina por desempate de score.

### 1.2 Unidades y stats

Tres tipos, stats fijos en `interfaces.py:41` (`UNIT_STATS`):

| Tipo      | `max_hp` | `attack` | `defense` | `movement` | `range` | `cost` |
|-----------|----------|----------|-----------|------------|---------|--------|
| `WARRIOR` | 10       | 2.0      | 2.0       | 1          | 1       | 2      |
| `ARCHER`  | 10       | 2.0      | 1.0       | 1          | 2       | 3      |
| `RIDER`   | 10       | 2.0      | 1.0       | **2**      | 1       | 3      |

Notas:

- `movement` y `range` están en distancia de Chebyshev.
- `ARCHER` es la única unidad con rango a distancia: puede atacar a `d = 2` sin recibir retaliación si el atacante está fuera del rango defensivo del enemigo.
- Una unidad tiene dos flags por turno: `has_moved`, `has_attacked`. Se resetean en `END_TURN` (`engine/rules.py:73`).

### 1.3 Acciones legales

`legal_actions(state, p)` (`engine/actions.py:41`) devuelve la lista plana de todas las acciones legales del jugador `p`. Su orden es importante porque algunos bots se apoyan en él: por unidad **`MOVE → ATTACK → HARVEST → RECOVER → CAPTURE`**, luego `TRAIN` por city, luego `LEVEL_UP`, y al final siempre **`END_TURN`**.

Reglas precisas (cito condiciones del código):

- **`MOVE`** (`actions.py:67`): solo si `not has_moved and not has_attacked`. El target tiene que estar dentro de `movement` Chebyshev, ser pasable, no estar ocupado por unidad propia ni por unidad enemiga visible, y **no** caer en `FogState.UNKNOWN` (las casillas marcadas `SEEN` sí se permiten — exploración recordada).
- **`ATTACK`** (`actions.py:88`): solo bloqueada por `has_attacked`. Es decir, **una unidad puede mover y después atacar en el mismo turno**, pero no atacar y después moverse.
- **`HARVEST`** (`actions.py:100`): unidad fresca (`not has_moved and not has_attacked`) parada sobre tile con `resource ≠ NONE`. Consume el turno completo (la marca como movida **y** atacada) y otorga `+2 stars`.
- **`RECOVER`** (`actions.py:108`): unidad fresca y herida (`hp < max_hp`). Cura `+4 hp` si está en territorio propio, `+2 hp` si no (`interfaces.py:52`).
- **`CAPTURE`** (`actions.py:119`): la unidad propia debe estar parada en una `City` enemiga y no debe haber otra unidad enemiga sobre esa city. No consume el move flag pero sí el attack flag.
- **`TRAIN`** (`actions.py:142`): por cada `City` propia con al menos una casilla adyacente pasable y libre, y si `stars[p] ≥ cost`, generamos una acción `TRAIN` por `(city, unit_type, tile_adyacente_libre)`. La unidad nace ya gastada (`has_moved = has_attacked = True`).
- **`LEVEL_UP`** (`actions.py:169`): cuesta `city.level × 5` stars. Sube `city.level += 1`.
- **`END_TURN`** (`actions.py:175`): siempre legal.

**Territorio propio** (`interfaces.py:186`): casillas a `d ≤ 1` (Chebyshev) de cualquier city propia. Esto importa para `RECOVER`.

### 1.4 Combate

La fórmula está en `engine/rules.py:21`. Llamémosla con la siguiente notación:

- `A` = atacante, `D` = defensor.
- `A.atk`, `D.def` = stats base (`attack` y `defense`).
- `A.hp`, `A.maxhp` (ídem `D`).
- `b` = `defender_terrain_bonus`. Vale **1.5** si el defensor está parado en una city propia; **1.0** en cualquier otro caso (`rules.py:58`, `CITY_DEFENSE_BONUS = 1.5`).
- `M = COMBAT_MULTIPLIER = 4.5`.

```
attack_force  = A.atk · (A.hp / A.maxhp)
defense_force = D.def · (D.hp / D.maxhp) · b
total         = attack_force + defense_force

dmg_a→d = round( (attack_force  / total) · A.atk · 4.5 )
dmg_d→a = round( (defense_force / total) · D.def · 4.5 )   solo si:
                                                              D sobrevive  AND
                                                              d(A.pos, D.pos) ≤ D.range
```

Si `total = 0` (caso degenerado), no pasa nada (`rules.py:37`). El daño se aplica primero al defensor; si **muere**, la retaliación es 0 (no hay retaliación de un cadáver). Si el atacante está **fuera del rango defensivo** (típico de un ARCHER pegándole a un WARRIOR desde `d = 2`), tampoco hay retaliación.

**Auto-advance al matar (Polytopia "stomp"):** si el atacante es `WARRIOR` o `RIDER`, la distancia inicial era exactamente 1, y el defensor murió, el atacante **se mueve a la casilla del defensor** (`rules.py:157`). Los `ARCHER` no avanzan al matar.

**Ejemplos numéricos (HP llenos, sin terreno bonus):**

| Matchup                 | `dmg_a→d` | `dmg_d→a` |
|-------------------------|-----------|-----------|
| WARRIOR (2/2) → WARRIOR (2/2) | `round(0.5 · 2 · 4.5) = 5` | `round(0.5 · 2 · 4.5) = 5` |
| ARCHER (2/1) → WARRIOR (2/2), `d=2` | `round((2/(2+2)) · 2 · 4.5) = 5` | **0** (fuera de rango) |
| WARRIOR (2/2) → ARCHER (2/1) en city `b=1.5` | `attack_force=2, defense_force=1.5; total=3.5; round((2/3.5)·2·4.5) ≈ 5` | `round((1.5/3.5)·1·4.5) ≈ 2` |

### 1.5 Economía

- **Ingreso por turno:** en `END_TURN` cada city otorga `level` stars (`rules.py:80`). Una city nivel 1 da 1 star/turno, nivel 2 da 2, etc.
- **HARVEST:** `+2 stars` por recurso recolectado (consume el recurso).
- **Costes:** `TRAIN` cuesta `UNIT_STATS[type]["cost"]`, `LEVEL_UP` cuesta `level · 5`.

### 1.6 Visión y niebla

`engine/map_gen.py:141` (`update_fog`). Cada jugador tiene su propio mapa de niebla `fog[p]: Position → FogState`. Tres estados:

- `UNKNOWN`: nunca visto.
- `SEEN`: visto antes, no actualmente visible (la geografía se recuerda; unidades enemigas no).
- `VISIBLE`: a `d ≤ VISION_RANGE = 2` (Chebyshev) de una unidad o city propia actual.

Se recomputa en cada `END_TURN`, en cada `MOVE` propio, y tras `ATTACK` o `CAPTURE`. Las acciones legales filtran enemigos en `VISIBLE` (no en `SEEN` — no puedes atacar fantasmas).

### 1.7 Score y victoria

`engine/rules.py:85`:

```
score(s, p) = 50 · |cities(p)|  +  3 · |units_vivas(p)|  +  0.1 · stars(p)
```

Estos pesos son del **reward fix v3**, calibrados para que la agresión gane sobre la pasividad. El comentario en código advierte que cambiarlos puede regresarnos al techo del 50 % de win rate.

`check_game_over` (`rules.py:106`) decide la partida así:

1. **Dominación:** si un jugador termina con 0 cities, el otro gana de inmediato.
2. **Timeout (`turn ≥ max_turns`):** el jugador con mayor `score` gana; si empatan, draw.

---

## 2. Bots (agentes scriptados)

Todos heredan de `BaseBot` (`agents/base.py`) que define `select_action(state, legal_actions) -> Action`. Cada bot decide sin acceso a información oculta — solo ve lo que su `state.fog[player_id]` permite, aunque por simplicidad varios bots leen `state.units` y `state.cities` enteros (el motor sí filtra acciones legales contra la niebla, así que esto no rompe nada).

### 2.1 RandomBot

`agents/random_bot.py`. Baseline trivial:

```
no_end := { a ∈ legal_actions : a.type ≠ END_TURN }
si no_end ≠ ∅ y Uniform(0,1) < 0.7:
    devuelve uniform(no_end)
sino:
    devuelve la acción END_TURN
```

El sesgo `p = 0.7` contra terminar turno fuerza al bot a *hacer algo* en lugar de pasar inmediatamente (lo cual rompería los oponentes que esperan a que el contrario coopere).

### 2.2 HeuristicBot v3

`agents/heuristic_bot.py`. **Greedy 1-ply con evaluación lineal y bonos por tipo de acción.** Es el bot fuerte de referencia (68 % de win rate promedio en el torneo, ver narrative).

**Decisión:**

```
para cada a ∈ legal_actions:
    s' = apply_action(s, a)
    score(a) = evaluate(s') + bonus(s, a) + jitter
devuelve argmax_a score(a)
```

`jitter ~ Uniform(0, 0.01)` rompe empates de forma determinista (con seed).

**`evaluate(s)` — función completa:**

Sea `Δx = x_yo − x_oponente`. Definimos:

| Cantidad           | Definición                                           |
|--------------------|------------------------------------------------------|
| `Δstars`           | `stars[me] − stars[opp]`                             |
| `Δcities`          | `|cities(me)| − |cities(opp)|`                       |
| `Δunits`           | `|units_vivas(me)| − |units_vivas(opp)|`             |
| `Δhp`              | `Σ hp(units(me)) − Σ hp(units(opp))`                 |
| `S`                | `# archers propios shielded` (definido abajo)         |
| `E`                | `# archers propios expuestos`                         |
| `OP`               | presión ofensiva (definida abajo)                     |

Con los pesos del código (`HeuristicBot.W_*`):

```
evaluate(s)  =   w_stars · Δstars
              +  20 · Δcities
              +   5 · Δunits
              +  0.5 · Δhp
              +   4 · S
              −   6 · E
              +  OP
```

donde el peso de stars cambia con la fase de juego:

```
w_stars =  1.0   si  s.turn ≤ 15      (early/mid)
           0.2   si  s.turn >  15      (late: stars valen menos, cities importan más)
```

**Formaciones de archers** (`_count_archer_formations`):

- `melee_positions` = posiciones de mis `WARRIOR`/`RIDER`.
- Un archer propio es **expuesto** si algún enemigo está a `d ≤ 1` de él.
- Un archer es **shielded** si **no** es expuesto **y** hay un melee propio a `d ≤ 1`.

La idea: los archers en primera línea sin meatshield mueren; con meatshield al lado son los que más dañan.

**Presión ofensiva (`_compute_offensive_pressure`):**

Sean `C_opp_conocidas` = cities enemigas en `state.fog[me]` con valor `VISIBLE` o `SEEN`.

```
si no hay units propias o no hay cities enemigas:
    OP = 0

si no hay cities enemigas conocidas (exploración):
    center = (board_size/2, board_size/2)
    OP = − 0.8 · 0.5 · Σ_u  d(u.pos, center)            # fallback: ir al centro

en otro caso:
    OP = − 0.8 · Σ_u  min_{c ∈ C_opp_conocidas} d(u.pos, c.pos)
```

OP es **negativa** — restamos distancia. Score sube cuando un `MOVE` me acerca al objetivo y baja si me alejo. El peso 0.8 (`W_DISTANCE`) fue subido de 0.3 a 0.8 en la fase 3 del tuning tras observar que el 100 % de las partidas perdidas exhibían el patrón "nunca alcancé al enemigo".

**Bonos por tipo de acción** (`_action_type_bonus`):

```
bonus(s, a) =
    +50      si a.type = CAPTURE              (W_CAPTURE_BONUS)
    +8       si a.type = ATTACK               (W_ATTACK_BONUS)
    −2·F     si a.type = END_TURN             (W_IDLE_PENALTY · # unidades fresh)
     0       en cualquier otro caso
```

donde `F` = número de unidades propias **fresh** (ni movidas ni atacadas). Esto:

- garantiza que capturar una city (50) es prácticamente siempre mejor que cualquier otra cosa, dado que el cambio en `evaluate` por capturar ya vale `+20·Δcities = +20`,
- da un empujón a atacar aunque el daño no cambie mucho el `evaluate` agregado,
- castiga el "doblar la rodilla" — terminar turno con unidades sin usar.

### 2.3 LookaheadBot (experimental, no en el torneo)

`agents/lookahead_bot.py`. **Minimax 2-ply** sobre la misma `evaluate` del heurístico. *No está exportado en `agents/__init__.py` ni participa del round-robin ni del opponent pool del DQN* — está como prueba de concepto para futura comparación.

Hereda de `HeuristicBot` y solo sobreescribe `select_action`:

```
1. Pre-filtrar mis acciones a top-K (K = SELF_TOP_K = 10) por score greedy:
       score_quick(a) = evaluate(apply(s, a)) + bonus(s, a)

2. Para cada a ∈ candidate_actions:
       s' = apply(s, a)
       si s'.current_player == me:       # mi acción no terminó turno
           worst(a) = evaluate(s') + bonus(s, a)
       sino:
           opp_actions = legal_actions(s', opp)
           pre-filtrar opp_actions a top-K' (K' = OPPONENT_TOP_K = 5) por
                score_para_mi(oa) = evaluate(apply(s', oa))
           tomando las K' MENORES (las peores para mí)
           worst(a) = min_{oa ∈ opp_candidates} evaluate(apply(s', oa))

3. Devolver argmax_a (worst(a) + jitter)
```

Esto es **minimax limitado**: mi acción + 1 acción del oponente. Justificación del top-K: el branching de `legal_actions` puede ser de cientos en mid-game (muchos `MOVE × TRAIN × LEVEL_UP`), evaluar todo el árbol 2-ply puro saldría caro.

### 2.4 AggressiveBot

`agents/aggressive_bot.py`. **Prioridad estricta por tipo de acción:**

```
si CAPTURE disponible:        elegir random uniform sobre CAPTUREs
sino si ATTACK disponible:    elegir random uniform sobre ATTACKs
sino si MOVE disponible:      elegir MOVE que minimiza d(target, enemigo_más_cercano)
                              (si no hay enemigos visibles, hacia city enemiga)
sino si TRAIN disponible:     elegir random uniform sobre TRAINs
sino si HARVEST disponible:   elegir random uniform sobre HARVESTs
sino:                          END_TURN
```

Sin defensa, sin reservar stars, sin evaluar HP. La elección del `MOVE` óptimo usa Chebyshev contra unidades enemigas (con fallback a cities si no hay unidades).

### 2.5 DefensiveBot

`agents/defensive_bot.py`. **Ataca solo cerca de casa, hoarda lo demás:**

Sea `DEFENSE_RADIUS = 3`. Sea `C_me` = posiciones de mis cities.

```
si hay ATTACK a target con  min_{c ∈ C_me} d(target, c) ≤ 3:
    elegir ese ATTACK (el primero que cumpla)
sino si TRAIN disponible:    random uniform
sino si HARVEST disponible:  random uniform
sino si LEVEL_UP disponible: random uniform
sino si MOVE disponible:     MOVE que minimiza d(target, C_me)  (replegarse)
sino:                         END_TURN
```

No captura (nunca elige `CAPTURE` ni se mueve hacia cities enemigas). El bot está diseñado a propósito para perder bajo el reward v3 — replica la política que ganaba con el reward viejo y sirve de control negativo.

### 2.6 EconomicBot

`agents/economic_bot.py`. **Crecimiento primero, ataque solo con superioridad numérica:**

```
si HARVEST disponible:                 random uniform
sino si LEVEL_UP disponible:           random uniform
sino si TRAIN disponible:              random uniform
sino si ATTACK disponible y
        |units_me| / max(|units_opp|, 1) ≥ 2.0:
    random uniform sobre ATTACKs
sino si CAPTURE disponible:            random uniform
sino si MOVE disponible:               MOVE que minimiza d(target, recurso)
sino:                                  END_TURN
```

El threshold `ATTACK_RATIO_THRESHOLD = 2.0` hace que solo entable combate cuando tenga el doble de unidades vivas que el oponente. Es la única consulta a estado que hace este bot fuera de las cantidades disponibles.

### 2.7 GreedyAttackBot

`agents/greedy_attack_bot.py`. **Ataca siempre, incluso con daño suicida:**

```
si ATTACK disponible:        random uniform sobre ATTACKs (sin filtro)
sino si CAPTURE disponible:  random uniform
sino si MOVE disponible:     MOVE que minimiza d(target, enemigo)
sino si TRAIN disponible:    random uniform
sino si HARVEST disponible:  random uniform
sino:                         END_TURN
```

Sin lógica de supervivencia, sin reservar stars. Su función en el roster es probar si los demás bots resisten ataques irracionales. Pierde 30 % de win rate promedio, el peor del torneo — y aún así le gana al RandomBot 60 %, lo que sugiere que "siempre atacar" supera a "actuar al azar".

---

## 3. DQN (Deep Q-Network) — agente aprendido

`agents/dqn_bot.py`, `agents/features.py`. Aprende una función `Q(s, a) → ℝ` y al inferir elige la acción legal con mayor Q.

### 3.1 Representación de features

A diferencia del DQN clásico (que usa `s → ℝ^|A|`), aquí parametrizamos **`Q(s, a)`** como una función escalar de un vector `φ(s, a)` que mezcla estado y acción. Esto evita lidiar con un espacio de acciones combinatorio (cientos de acciones distintas por turno).

**Estado** `ψ(s, p) ∈ ℝ^14` (`extract_state_features`, `features.py:34`). Cada componente está normalizada para tener magnitud cercana a 1:

| Idx | Componente              | Definición                                            |
|-----|-------------------------|-------------------------------------------------------|
| 0   | `stars_diff`            | `(stars[p] − stars[opp]) / 20`                        |
| 1   | `cities_diff`           | `(cities(p) − cities(opp)) / 3`                       |
| 2   | `units_diff`            | `(units(p) − units(opp)) / 5`                         |
| 3   | `hp_diff`               | `(Σhp(p) − Σhp(opp)) / 50`                            |
| 4   | `shielded_archers / 3`  | igual definición que en HeuristicBot                  |
| 5   | `exposed_archers / 3`   | igual definición que en HeuristicBot                  |
| 6   | `min_dist_to_city_norm` | `min_u d(u.pos, c.pos) / board_size` sobre cities enemigas conocidas. Fallback: distancia media al centro / board_size. |
| 7   | `turn_progress`         | `turn / max_turns`                                    |
| 8   | `cities_me_abs / 3`     | cuenta absoluta de cities propias normalizada         |
| 9   | `fresh_units / 5`       | unidades propias ni movidas ni atacadas               |
| 10  | `n_units_me / 5`        | total de unidades propias                             |
| 11  | `stars_me / 30`         | stars propios absolutos                               |
| 12  | `hp_me_total / 50`      | suma de HP propios                                    |
| 13  | `has_ready_attacker`    | `1` si existe `u` con `hp ≥ 0.7·maxhp` y `not has_attacked`, sino `0` |

**Acción** `α(a) ∈ ℝ^8` — one-hot del `ActionType` (`features.py:73`). Orden: `MOVE, ATTACK, HARVEST, RECOVER, CAPTURE, TRAIN, LEVEL_UP, END_TURN`.

**Feature combinada estado-acción:**

```
φ(s, a, p) = [ ψ(s, p)  ‖  ψ(apply_action(s, a), p)  ‖  α(a) ]   ∈ ℝ^36
```

(`features.py:80`). Es decir: features del estado actual, features del estado tras simular la acción, y el one-hot del tipo. **El `apply_action` se hace dentro de la extracción de features**, lo que añade un `deepcopy` por evaluación de acción. Costoso pero esencial: el DQN tiene una vista de "qué pasó" en lugar de solo "qué soy".

`FEATURE_DIM = 14 + 14 + 8 = 36`.

### 3.2 Arquitectura

`DQNNet` (`dqn_bot.py:27`):

```
input (36) → Linear(36, 64) → ReLU
           → Linear(64, 64) → ReLU
           → Linear(64,  1) → squeeze     # scalar Q(s, a)
```

Pequeña por diseño: ~6 k parámetros. Suficiente para un MDP con feature handcrafted ya semánticamente cargado.

### 3.3 Política de inferencia

`DQNBot.select_action` (`dqn_bot.py:62`):

```
si solo hay 1 acción legal:                       devolverla
si Uniform(0,1) < ε (ε-greedy):                   devolver una acción legal random
si no:
    φ_lote = stack([ φ(s, a_i, me)  for a_i in legal_actions ])
    q      = model(φ_lote)                         # ℝ^N
    devolver legal_actions[ argmax_i q[i] ]
```

Durante el juego real `ε = 0`. Durante el training `ε` decae linealmente de 1.0 a 0.05 en los primeros 1000 episodios (ver § 4.5).

### 3.4 Ecuación de Bellman y target

Lo que el DQN aprende es la función óptima `Q*(s, a) = E[ r + γ · max_{a'} Q*(s', a') | s, a ]`. En la práctica, durante el training, calculamos un **target** `y` para cada transición y minimizamos `(Q_online(s, a) − y)²`:

```
y = r  +  γ · Q_target(s', a*) · 𝟙[no es estado terminal]
```

con `γ = 0.97`. `Q_target` es una copia "congelada" del modelo online que se sincroniza cada 25 episodios (§ 4.4).

**`a*` se calcula así** — y aquí hay una particularidad del diseño que se aparta del DQN estándar:

```
en el momento de almacenar la transición (no en cada update):
    next_actions = legal_actions(s', me)
    Φ_next       = stack([ φ(s', a', me) for a' in next_actions ])
    q_next       = Q_target(Φ_next)               # ← target_net actual
    a*           = next_actions[ argmax q_next ]
    φ_next_a*    = Φ_next[ argmax ]
    guardar  (φ(s,a), r, done, φ_next_a*)  en el replay buffer
```

Es decir, **el `argmax` sobre las acciones siguientes se cristaliza al momento de generar la transición**, usando el `target_net` de entonces, y solo se guarda la feature del ganador. Después, durante el update del batch, recomputamos `Q_target(φ_next_a*)` pero ya no hacemos el `max` sobre todas las acciones legales (ya está elegida). Esto es:

- **Diferente del DQN vanilla**, que recomputa `max_{a'} Q_target(s', a')` con el target_net actual en cada update.
- **Diferente del Double DQN**, que usaría el `online_net` para elegir `a*` y el `target_net` para evaluar.

Pragmáticamente es un trade-off: ahorra recomputar `legal_actions` y un forward por cada elemento de cada batch, a cambio de que el `argmax` quede "stale" respecto a los pesos del `target_net` cuando ese batch se procesa.

### 3.5 Función de pérdida

`MSELoss` (no Huber):

```
L(θ) = (1/|B|) · Σ_{(φ, r, done, φ_next) ∈ B}  ( Q_θ(φ)  −  y )²
```

con `|B| = 64`. El optimizer es `Adam` con `lr = 5e-4`. Tras el backward se aplica `clip_grad_norm_(params, 1.0)` para estabilidad.

---

## 4. Entrenamiento del DQN

`experiments/train_dqn_nocturno.py`. Es un script "intermitente": guarda checkpoint cada N episodios y se puede pausar y reanudar sin pérdida de estado (incluidos los RNGs).

### 4.1 Reward shape

**Recompensa rala (sparse), terminal-only:**

```
r_t = 0   para t < T
r_T = +1  si el DQN (player 0) gana
       -1  si pierde
        0  si draw
```

Concretamente (`train_dqn_nocturno.py:201`): se almacenan todas las transiciones intermedias con `r = 0, done = False`; al terminar el episodio se reescribe la última transición con `r = ±1` y `done = True`.

No hay shaping (ni bonos parciales por capturar cities ni por matar unidades). La señal viaja hasta atrás por `γ`: a 1 paso del final el target vale `γ · 1 = 0.97`, a 5 pasos `0.97^5 ≈ 0.86`, a 20 pasos `≈ 0.54`. En un juego de máximo 30 turnos × ~varias acciones por turno, es razonable.

### 4.2 Replay buffer

`deque` de tamaño máximo `buffer_size = 20000`. Cada elemento es una tupla `(φ, r, done, φ_next)` ya con `a*` cristalizado (§ 3.4). Sampling: **uniforme** (`np.random.choice(N, batch_size, replace=False)`), no prioritizado.

### 4.3 Loop de entrenamiento (pseudocódigo)

```
inicializar online_net, target_net (= online_net), Adam(lr=5e-4), buffer vacío

para episode = start_episode .. target_total_episodes:
    ε  = max(ε_end, ε_start − (ε_start − ε_end) · episode / decay_episodes)
    opp = sample_opponent(distribución del pool)         # § 4.6
    s   = create_initial_state(seed = episode)
    transitions = []

    mientras no game_over:
        si current_player == 0 (DQN):
            a   = DQN.select_action(s, legal_actions, ε)
            φ   = ψ(s) ‖ ψ(apply(s,a)) ‖ α(a)
            s'  = apply(s, a)
            transitions.append( (φ, 0.0, s'.game_over, s') )
            s   = s'
        sino (oponente):
            a   = opp.select_action(s, legal_actions)
            s   = apply(s, a)

    # Reward terminal sobre la última transición
    r_final = +1 si winner==0 else (-1 si winner==1 else 0)
    transitions[-1].r    = r_final
    transitions[-1].done = True

    # Cristalizar φ_next_a* con target_net  (§ 3.4)
    para cada (φ, r, done, s_next) en transitions:
        si done:
            φ_next = 0
        sino:
            next_actions = legal_actions(s_next, 0)
            si no hay:
                φ_next, done = 0, True
            sino:
                Φn  = stack([φ(s_next, a') for a' in next_actions])
                q   = target_net(Φn)
                φ_next = Φn[ argmax q ]
        buffer.append( (φ, r, done, φ_next) )

    # Un step de SGD por episodio
    si |buffer| >= batch_size:
        B  = sample uniform sin reemplazo del buffer, |B| = 64
        y  = r_B + γ · target_net(φ_next_B) · (1 − done_B)
        loss = MSE( online_net(φ_B), y )
        Adam.zero_grad(); loss.backward()
        clip_grad_norm_(online_net.params, 1.0)
        Adam.step()

    # Hard sync del target cada 25 episodios
    si (episode + 1) % 25 == 0:
        target_net.load_state_dict(online_net.state_dict())

    # Checkpoint cada 50 episodios
    si (episode + 1) % 50 == 0:
        save_checkpoint(...)
        torch.save(online_net.state_dict(), MODEL_PATH)
```

**Detalle importante:** solo se hace **un step de gradiente por episodio**, no uno por transición. Con episodios de típicamente 60–200 acciones del DQN, eso es un ratio de ~1:120 environment-step a gradient-step, mucho menor que el típico DQN (Atari usa ~1:4). Compensa parcialmente que cada step ve un batch de 64 muestras independientes del buffer.

### 4.4 Target network

Copia "congelada" del modelo online. Se sincroniza por **hard copy** cada 25 episodios:

```
target_net.load_state_dict(online_net.state_dict())
```

No hay soft update (Polyak). La función del target es estabilizar el aprendizaje: si usáramos el mismo `online_net` para `Q(s, a)` y `Q(s', a*)`, los gradientes perseguirían un blanco móvil y el training divergiría.

### 4.5 Schedule de ε (exploración)

Lineal:

```
ε(episode) = max( 0.05,  1.0 − (1.0 − 0.05) · episode / 1000 )
```

Es decir: arranca puramente random (ε=1), llega a ε=0.05 en el episodio 1000, y se mantiene en 0.05 el resto del entrenamiento. El 5 % residual es importante para que el bot siga explorando aunque su política haya convergido.

### 4.6 Opponent pool (curriculum)

`OPPONENT_POOL` (`train_dqn_nocturno.py:55`):

| Oponente      | Probabilidad |
|---------------|--------------|
| HeuristicV3   | 0.40         |
| Aggressive    | 0.20         |
| Defensive     | 0.15         |
| Economic      | 0.15         |
| Random        | 0.10         |

`LookaheadBot` y `GreedyAttackBot` **no participan** del pool de entrenamiento.

La motivación de mezclar es no sobre-ajustar a un único oponente. HeuristicV3 lleva el 40 % porque es el oponente más fuerte y el benchmark que queremos batir; Random se conserva al 10 % para no perder cobertura de estados "raros" (Random visita el espacio de estados de manera más uniforme que cualquier bot scripted).

El DQN siempre juega como **player 0** durante el training (`train_dqn_nocturno.py:173`). Eso introduce un sesgo de starting position que habría que romper para producción (alternar P0/P1 como hace el torneo), pero para esta iteración se acepta.

### 4.7 Checkpointing

`training/checkpoint.py`. Cada 50 episodios persistimos con `pickle` (archivo temporal + `rename` atómico para no corromper):

- `online_net.state_dict()`
- `target_net.state_dict()`
- `optimizer.state_dict()` (incluye los momentos `m`, `v` de Adam)
- `replay_buffer` completo (lista de tuplas)
- `episode`, `epsilon`
- `hyperparams` (toda la config)
- `opponent_distribution` (histograma de oponentes encontrados)
- `rng_python`, `rng_numpy`, `rng_torch` (estados de los tres RNGs)
- Logs: `win_rate_log`, `losses_log`

La garantía documentada: reanudar después de pausar produce **exactamente el mismo training** que correr de corrido. Se logra capturando los tres RNGs y restaurándolos al cargar.

Además del checkpoint, también escribimos `MODEL_PATH = "checkpoints/dqn_nocturno_model.pt"` con solo `online_net.state_dict()` — formato standalone para que `DQNBot.load(path)` lo consuma sin necesidad del pickle entero.

### 4.8 Hyperparámetros (resumen)

| Símbolo            | Valor   | Variable             |
|--------------------|---------|----------------------|
| `batch_size`       | 64      | `hyperparams["batch_size"]` |
| `buffer_size`      | 20000   | `hyperparams["buffer_size"]` |
| `γ`                | 0.97    | `hyperparams["gamma"]` |
| `lr`               | 5e-4    | `hyperparams["lr"]` |
| `ε_start`          | 1.0     | `hyperparams["epsilon_start"]` |
| `ε_end`            | 0.05    | `hyperparams["epsilon_end"]` |
| `decay_episodes`   | 1000    | `hyperparams["epsilon_decay_episodes"]` |
| `target_sync_every`| 25      | `hyperparams["target_sync_every"]` |
| `target_total_episodes` | 2000 | `--episodes` (default) |
| `save_every`       | 50      | `--save-every` |
| `clip_grad_norm`   | 1.0     | hard-coded |

### 4.9 Uso desde la CLI

```bash
# Primera sesión (objetivo: 2000 episodios)
python -m experiments.train_dqn_nocturno --episodes 2000

# Continuar tras pausar
python -m experiments.train_dqn_nocturno --episodes 2000 --resume

# Sesión limitada a 2 horas
python -m experiments.train_dqn_nocturno --episodes 2000 --resume --max-time-min 120

# Ver estado del checkpoint sin entrenar
python -m experiments.train_dqn_nocturno --status
```

Los targets equivalentes vía Makefile (`make train-dqn`, `make train-dqn-resume`, `make train-dqn-night`, `make train-dqn-status`) llaman a estos comandos.

---

## 5. Referencias rápidas al código

| Tema                       | Archivo                                              |
|----------------------------|------------------------------------------------------|
| Tipos y constantes         | `src/polytopia/interfaces.py`                        |
| Generación de mapa         | `src/polytopia/engine/map_gen.py`                    |
| Estado inicial             | `src/polytopia/engine/state_init.py`                 |
| `legal_actions`            | `src/polytopia/engine/actions.py`                    |
| `apply_action` y combate   | `src/polytopia/engine/rules.py`                      |
| Bots scripted              | `src/polytopia/agents/*.py`                          |
| Features compartidas (DQN + heurística) | `src/polytopia/agents/features.py`      |
| DQN (modelo + bot)         | `src/polytopia/agents/dqn_bot.py`                    |
| Checkpoint                 | `src/polytopia/training/checkpoint.py`               |
| Training nocturno          | `experiments/train_dqn_nocturno.py`                  |
| Torneo round-robin         | `experiments/tournament.py`                          |
| Benchmark DQN              | `experiments/benchmark_dqn_vs_all.py`                |
| Análisis del DQN entrenado | `experiments/analyze_dqn.py`                         |

Para resultados empíricos: [`reports/tournament_narrative.md`](../reports/tournament_narrative.md) y `reports/tournament.json`.
