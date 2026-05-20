# Polytopia AI

Bot de IA para una versión simplificada de *The Battle of Polytopia*, con motor
de juego propio, agentes baseline + heurístico, dos interfaces de visualización
(terminal y gráfica isométrica) y un sistema de grabación/reproducción de
partidas.

## Tabla de contenidos

- [Resumen](#resumen)
- [Quick Start](#quick-start)
- [Comandos disponibles](#comandos-disponibles)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Mecanica de juego implementada](#mecanica-de-juego-implementada)
- [Dos modos de visualizacion](#dos-modos-de-visualizacion)
- [Como correr una partida](#como-correr-una-partida)
- [Sistema de Replay](#sistema-de-replay)
- [Desarrollo de heuristicas](#desarrollo-de-heuristicas)
- [Benchmark](#benchmark)
- [Tests](#tests)
- [Arquitectura](#arquitectura)
- [Roles del equipo](#roles-del-equipo)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Troubleshooting](#troubleshooting)
- [Referencias](#referencias)
- [Licencia y creditos](#licencia-y-creditos)

## Resumen

Este repositorio implementa un agente de IA para una versión 1v1 simplificada
de *The Battle of Polytopia*, un juego 4X por turnos. El objetivo del trabajo
es construir, desde cero, todo el camino que va desde el motor de juego hasta
el bot que toma decisiones, pasando por las herramientas necesarias para
visualizar partidas, grabarlas y reproducirlas. El agente principal compite
contra un baseline aleatorio sobre tableros de 11×11 y partidas de 30 turnos.

El motor reproduce con fidelidad las mecánicas centrales de Polytopia: la
fórmula oficial de combate (con su multiplicador `4.5`), el bonus defensivo
`1.5×` cuando una unidad defiende dentro de su ciudad, la retaliación
condicional (solo si el defensor sobrevive y el atacante está en rango), la
recuperación `+4 HP` en territorio propio (`+2` fuera), y los stats y costos
auténticos de WARRIOR, ARCHER y RIDER. Se omitieron mecánicas que multiplican
el alcance del proyecto sin agregar valor pedagógico inmediato (tribus
asimétricas, árbol tecnológico, naval, diplomacia); estas omisiones están
listadas explícitamente más abajo.

Sobre ese motor corren dos agentes: `RandomBot` (acción aleatoria con un sesgo
en contra de terminar el turno temprano) y `HeuristicBot` (stub donde se
implementa la heurística greedy con función de evaluación ponderada). El
agente heurístico todavía está sin implementar; este README documenta el
contrato que debe cumplir y los hooks de visualización (`make watch-eval`,
`make gui-live-heuristic`) que permiten depurar sus decisiones en vivo.

El sistema de visualización tiene dos caras: un renderer ASCII en terminal
(útil para iterar rápido, debuggear sin display y correr en CI/SSH) y un
renderer gráfico isométrico en pygame (útil para defensa, demos en vivo y para
grabar replays). Las partidas pueden grabarse a JSON y reproducirse después
con controles de pausa, frame seek y velocidad ajustable, lo cual habilita
mostrar partidas memorables sin depender de RNG y comparar agentes sobre el
mismo seed sin tener que volver a jugarlas.

## Quick Start

```bash
git clone <url-del-repo>
cd polytopia_ai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gui]"
make test
make demo
```

El comando `make demo` corre una partida silenciosa de `RandomBot` vs
`RandomBot` y debe terminar imprimiendo `Winner: PX, turn N` sin errores. Con
el seed por defecto (`42`) la línea es:

```
Winner: P0, turn 30
```

Si solo te interesa la línea de comandos sin gráficos, basta con
`pip install -e ".[dev]"`; pygame y la GUI son opcionales y viven detrás del
extra `[gui]`.

## Comandos disponibles

Referencia consolidada de todo lo que se puede ejecutar. Bots disponibles en
torneo: `Random`, `Aggressive`, `Defensive`, `Economic`, `GreedyAttack`,
`HeuristicV3`.

### Setup, tests y formato

```bash
make install            # pip install -e ".[dev]"
make test               # pytest
make lint               # ruff + black --check
make format             # black + ruff --fix
make clean              # borra caches, build/, *.egg-info
```

### Partidas en terminal (sin pygame)

```bash
make demo               # partida silenciosa, solo imprime ganador
make watch              # auto-avance, delay 0.5s
make watch-step         # paso a paso, Enter para avanzar
make watch-eval         # muestra top-3 evaluaciones por acción

# Flags manuales del game_loop
python -m polytopia.game_loop --watch --delay 1.0
python -m polytopia.game_loop --watch --viewer 0       # niebla desde P0
python -m polytopia.game_loop --watch --eval --step
```

### Partidas en GUI gráfica (pygame)

```bash
make gui-demo                # render estático de un estado inicial
make gui-live                # Random vs Random
make gui-live-heuristic      # HeuristicV3 vs Random
make gui-mirror-heuristic    # HeuristicV3 vs HeuristicV3 (mirror)
make gui-dqn-vs-random       # DQN vs Random
make gui-dqn-vs-heuristic    # DQN vs HeuristicV3
make gui-mirror-dqn          # DQN vs DQN (mirror)
make gui-paused              # arranca pausado (Random vs Random)
make gui-record              # graba a replays/last_game.json
make gui-replay FILE=replays/last_game.json

# Flags manuales del live_runner (--p0 y --p1 aceptan random|heuristic|dqn)
python -m polytopia.renderers.gui.live_runner --p0 heuristic --p1 heuristic --seed 7
python -m polytopia.renderers.gui.live_runner --p0 dqn --p1 heuristic --paused
python -m polytopia.renderers.gui.live_runner --p0 dqn --p1 heuristic --viewer 0
python -m polytopia.renderers.gui.live_runner --p0 dqn --p1 heuristic --record replays/dqn.json

# DQN requiere checkpoint (default: checkpoints/dqn_nocturno_model.pt).
# Si querés usar otro:
python -m polytopia.renderers.gui.live_runner --p0 dqn --p1 random \
       --dqn-checkpoint checkpoints/otro_modelo.pt
```

### Torneo round-robin (todos contra todos)

```bash
make tournament-quick       # 10 seeds por matchup (rápido)
make tournament             # 20 seeds (default)
make tournament-full        # 50 seeds (más confiable)
make tournament-plot        # heatmap desde reports/tournament.json

# Subset de bots (cualquier combinación)
python -m experiments.tournament --seeds 20 --bots HeuristicV3 Aggressive Defensive
python -m experiments.tournament --seeds 30 --bots HeuristicV3 GreedyAttack
python -m experiments.tournament --seeds 50 --bots Aggressive Defensive Economic GreedyAttack
python -m experiments.tournament --seeds 30 --bots HeuristicV3 HeuristicV3 \
       --output reports/mirror_heuristic.json
```

### Benchmark heurístico vs Random (script viejo)

```bash
make benchmark              # 20 seeds, HeuristicV3 como P0
make benchmark-full         # 50 seeds

python -m experiments.benchmark --n 100              # 100 seeds
python -m experiments.benchmark --n 50 --as 1        # HeuristicV3 como P1
```

### DQN — entrenamiento, evaluación y análisis

```bash
make train-dqn              # 2000 episodios desde cero
make train-dqn-resume       # 2000 episodios, retoma desde checkpoint
make train-dqn-status       # status del checkpoint actual
make train-dqn-night        # 3000 ep con resume y límite de 480 min

make benchmark-dqn          # DQN contra cada bot del pool
make analyze-dqn            # reporte de análisis del DQN entrenado
```

### Replay

```bash
# Grabar desde la GUI
python -m polytopia.renderers.gui.live_runner --p0 heuristic --p1 heuristic \
       --record replays/mi_partida.json

# Reproducir
make gui-replay FILE=replays/mi_partida.json
python -m polytopia.renderers.gui.replay_player replays/mi_partida.json --delay 0.5
```

### Outputs

| Comando | Genera |
|---|---|
| `make tournament*` | `reports/tournament.json` |
| `make tournament-plot` | `reports/tournament_heatmap.png` |
| `make gui-record` | `replays/last_game.json` |
| `make train-dqn*` | `checkpoints/dqn_nocturno.pkl` + `.pt` |
| `make analyze-dqn` | reporte en stdout |

> **Limitación de la GUI:** `live_runner` acepta `random`, `heuristic` y
> `dqn` en `--p0`/`--p1`. Para visualizar los otros bots de estrategia
> (`Aggressive`, `Defensive`, `Economic`, `GreedyAttack`) usá el torneo
> (estadística) o extendé `bot_choices` en `live_runner.py`.

## Estructura del proyecto

```
polytopia_ai/
├── src/polytopia/
│   ├── interfaces.py              Tipos compartidos: GameState, Unit, Action, etc.
│   ├── engine/
│   │   ├── map_gen.py             Generación procedural del mapa y fog of war.
│   │   ├── state_init.py          Estado inicial: ciudades, unidades, stars.
│   │   ├── rules.py               Combate, RECOVER, apply_action, end_turn.
│   │   └── actions.py             legal_actions: enumerador de acciones legales.
│   ├── agents/
│   │   ├── base.py                BaseBot abstracta.
│   │   ├── random_bot.py          Baseline aleatorio.
│   │   └── heuristic_bot.py       Stub a implementar por Persona B.
│   ├── renderers/
│   │   ├── terminal.py            Renderer ASCII con rich.
│   │   └── gui/
│   │       ├── iso_projection.py    Math de proyeccion isometrica.
│   │       ├── colors.py            Paleta neon estilo Polytopia.
│   │       ├── terrain_renderer.py  Pinta tiles, arboles, montanas, agua.
│   │       ├── entity_renderer.py   Pinta ciudades y unidades.
│   │       ├── hud_renderer.py      Top bar, bottom bar, game over overlay.
│   │       ├── main_renderer.py     PolytopiaRenderer + demo_main.
│   │       ├── live_runner.py       Modo "ver al bot jugar" en pygame.
│   │       └── replay_player.py     Reproductor de replays grabados.
│   ├── replay/
│   │   ├── recorder.py            GameRecorder: graba frames a JSON.
│   │   └── loader.py              load_replay: deserializa JSON a GameState.
│   └── game_loop.py               Loop principal con modo silencioso y watch terminal.
├── tests/                         Suite pytest (8 archivos).
├── replays/                       Partidas grabadas (gitignored, se crea al primer record).
├── NEXT_STEPS.md                  Plan por persona para iteraciones futuras.
├── pyproject.toml
└── Makefile
```

La carpeta que la plantilla original mencionaba pero **no existe aún en el
código** es:

- `experiments/` — pendiente. El benchmark documentado más abajo todavía no
  está implementado.

## Mecanica de juego implementada

### Mecánicas auténticas de Polytopia

- **Fórmula de combate oficial** con multiplicador `4.5`. Implementada en
  `engine/rules.py::resolve_combat`. La fórmula es:

  ```
  attack_force  = attacker.attack  * (attacker.hp / attacker.max_hp)
  defense_force = defender.defense * (defender.hp / defender.max_hp) * defender_bonus
  total         = attack_force + defense_force
  damage_to_def = round((attack_force  / total) * attacker.attack  * 4.5)
  retaliation   = round((defense_force / total) * defender.defense * 4.5)
  ```

- **Defense bonus en ciudad** (`CITY_DEFENSE_BONUS = 1.5`): cuando el defensor
  está dentro de su propia ciudad, su `defense_force` se multiplica por `1.5`.
  El efecto neto es que el defensor recibe menos daño (o el mismo, por
  redondeo) y reparte más retaliación.

- **Retaliation condicional**: la retaliación es `0` si el defensor muere por
  el ataque (`defender.hp - damage_to_def <= 0`) **o** si el atacante está
  fuera del rango del defensor (`chebyshev_distance > defender.range`). Esto
  es lo que hace al ARCHER (range 2) seguro contra un WARRIOR (range 1) a
  distancia 2.

- **RECOVER**: cura `+4 HP` si la unidad está en territorio propio (definido
  como chebyshev ≤ `CITY_TERRITORY_RADIUS = 1` de una ciudad propia) y `+2
  HP` fuera. La acción solo es legal si la unidad no se movió ni atacó este
  turno y está dañada.

- **Stats auténticos** (ver `interfaces.UNIT_STATS`):

  | Unidad   | HP | ATK | DEF | MOV | RNG | Cost |
  |----------|----|-----|-----|-----|-----|------|
  | WARRIOR  | 10 | 2.0 | 2.0 | 1   | 1   | 2    |
  | ARCHER   | 10 | 2.0 | 1.0 | 1   | 2   | 3    |
  | RIDER    | 10 | 2.0 | 1.0 | 2   | 1   | 3    |

- **Ingresos**: cada ciudad genera `level` stars al cierre de cada turno
  propio (`end_turn_tick`).

- **End game**: una partida termina cuando un jugador pierde todas sus
  ciudades, o cuando se alcanza `max_turns = 30`. En empate por turnos, gana
  quien tenga más `score = 10·city_levels + units_alive + stars`.

### Simplificaciones explícitas

| Mecánica Polytopia                           | Estado     | Razón                                            |
|----------------------------------------------|------------|--------------------------------------------------|
| Tribus asimétricas                           | No         | 16 tribus × bonos = 16× el alcance               |
| Árbol tecnológico                            | No         | 24 techs con dependencias = otra semana entera   |
| City Walls (4× def)                          | No         | Requiere tech tree                               |
| Habilidades especiales (Persist, Escape, …)  | No         | Específicas por unidad y tribu                   |
| Naval / Sailing                              | No         | Mapa puramente terrestre                         |
| Diplomacia                                   | No         | Solo 1v1                                         |
| Montañas transitables                        | No         | Requiere Climbing tech                           |
| Niveles de ciudad >1 dinámicos               | Parcial    | Estructura existe; sin crecimiento por población |
| Resources: ANIMAL/FRUIT                      | Sí (parcial) | Se generan en el mapa y son cosechables vía HARVEST; sin bonos pasivos |

Esta sección es la principal defensa del proyecto frente al profesor: las
omisiones son decisiones de alcance, no errores. Lo que sí se implementó tiene
fidelidad numérica al juego original.

## Dos modos de visualizacion

### Renderer Terminal

Para desarrollo e iteración rápida. Usa `rich` para colores y paneles. No
necesita display: corre en SSH, contenedores y CI.

Comandos:

```bash
make demo         # partida silenciosa, solo imprime el resultado final
make watch        # ver paso a paso con delay 0.8 s
make watch-step   # avanza con Enter en cada acción
make watch-eval   # muestra top-3 de acciones evaluadas (requiere bot.evaluate)
```

Flags del CLI `python -m polytopia.game_loop`:

| Flag         | Default | Descripción                                          |
|--------------|---------|------------------------------------------------------|
| `--watch`    | off     | Activa el modo de visualización paso a paso          |
| `--delay`    | `0.8`   | Segundos entre acciones                              |
| `--step`     | off     | Pausa hasta Enter después de cada acción             |
| `--viewer`   | `None`  | `0` o `1` para ver con fog de un jugador específico  |
| `--eval`     | off     | Muestra el top-3 de evaluaciones del bot             |
| `--no-clear` | off     | No limpia pantalla entre frames (útil para debug)    |
| `--seed`     | `42`    | Semilla del estado inicial                           |

### Renderer Gráfico (Pygame)

Para defensa, presentaciones y grabación de replays. Estética isométrica
plana inspirada en Polytopia, construida solo con primitivas geométricas: no
hay sprites externos. Tiles de 64×32 px, paleta neón cyan/magenta para los
dos jugadores.

Comandos:

```bash
make gui-demo             # abre el estado inicial; cierra con ESC
make gui-live             # RandomBot vs RandomBot en tiempo real
make gui-live-heuristic   # HeuristicBot vs RandomBot (requiere implementacion)
make gui-paused           # gui-live arrancando pausado
make gui-record           # graba la partida a replays/last_game.json
make gui-replay FILE=...  # reproduce un .json grabado
```

Controles de teclado en los modos `live` y `replay`:

| Tecla            | Live runner                              | Replay player                          |
|------------------|------------------------------------------|----------------------------------------|
| `SPACE`          | pausa / reanuda                          | pausa / reanuda                        |
| `UP` / `DOWN`    | acelera / desacelera (±0.1 s, 0.05–3 s)  | acelera / desacelera                   |
| `S`              | un step y pausa                          | —                                      |
| `LEFT` / `RIGHT` | —                                        | frame anterior / siguiente (pausa)     |
| `HOME` / `END`   | —                                        | primer / último frame (pausa)          |
| `ESC` / `Q`      | salir                                    | salir                                  |

### Cuándo usar cuál

- **Terminal**: desarrollo, debug rápido, ambientes sin display (SSH/CI), y
  para correr lotes de partidas no interactivas.
- **Gráfico**: demos en vivo, defensa final, grabación de replays
  memorables, comparación visual entre versiones del bot.

## Como correr una partida

Ejemplos concretos:

```bash
# Partida silenciosa: solo imprime quien gano y en que turno
make demo

# Ver una partida random vs random en terminal con animacion
make watch

# Ver una partida en pygame
make gui-live

# Heuristico vs random, grafico, partida acelerada
python -m polytopia.renderers.gui.live_runner --bot heuristic --delay 0.3

# Misma partida pero con fog de P0 (ves lo que P0 ve)
python -m polytopia.renderers.gui.live_runner --viewer 0

# Grabar partida para mostrarla despues
make gui-record
# -> escribe replays/last_game.json al cerrar la ventana

# Reproducir una partida grabada
make gui-replay FILE=replays/last_game.json

# Otra seed
python -m polytopia.game_loop --watch --seed 7
```

Todos los comandos `python -m ...` aceptan `--help` para ver el listado de
flags actualizado.

## Sistema de Replay

**Por qué existe.** Tres motivos: (1) reproducibilidad — poder volver a ver
exactamente la misma partida sin depender de RNG ni de la versión del bot;
(2) presentación — mostrar partidas memorables en la defensa sin riesgo de
que el RNG arruine el ejemplo; (3) debugging — guardar partidas donde el bot
toma una decisión sospechosa y revisarlas frame por frame.

**Formato.** JSON con la forma:

```json
{
  "frames": [
    {
      "action": null,
      "state": { "turn": 1, "current_player": 0, "tiles": {}, "...": "..." }
    },
    {
      "action": { "action_type": "MOVE", "unit_id": 0, "target": {"x": 2, "y": 1} },
      "state": { "turn": 1, "...": "..." }
    }
  ]
}
```

El primer frame tiene `action: null` (estado inicial). Cada frame siguiente
tiene la acción aplicada y el estado resultante. Los enums viajan por nombre
(`"MOVE"`, `"WARRIOR"`); las posiciones de `Tile` y `fog` se serializan con
keys `"x,y"` para que sean válidas en JSON.

**Cómo grabar.** Tres formas:

```python
# Programáticamente, desde código propio
from polytopia.replay import GameRecorder
recorder = GameRecorder()
recorder.record_frame(state, action=None)   # frame inicial
# ... después de cada apply_action ...
recorder.record_frame(state, action)
recorder.save("replays/mi_partida.json")
```

```bash
# Desde el live runner gráfico
python -m polytopia.renderers.gui.live_runner --record replays/mi_partida.json
# o equivalentemente:
make gui-record   # graba a replays/last_game.json
```

**Cómo reproducir.**

```bash
make gui-replay FILE=replays/last_game.json
# o directamente:
python -m polytopia.renderers.gui.replay_player replays/last_game.json --delay 0.5
```

**Controles** ya descritos en la tabla de la sección anterior: pausa, seek
frame a frame, speed, jump al primer/último frame.

## Desarrollo de heuristicas

El archivo único que debe modificar Persona B para tener un bot competitivo
es:

```
src/polytopia/agents/heuristic_bot.py
```

**Contrato mínimo.** Debe implementar `select_action(state, legal_actions)
-> Action`. Opcionalmente puede exponer `evaluate(state) -> float`, lo cual
habilita visualizar las top-3 acciones consideradas con `make watch-eval`.

**Plantilla greedy básica** (referencia, ver también `NEXT_STEPS.md`):

```python
from polytopia.engine.rules import apply_action

class HeuristicBot(BaseBot):
    def evaluate(self, state) -> float:
        me, opp = self.player_id, 1 - self.player_id
        cities_me  = sum(1 for c in state.cities.values() if c.owner == me)
        cities_opp = sum(1 for c in state.cities.values() if c.owner == opp)
        units_me   = [u for u in state.units.values() if u.owner == me  and u.is_alive]
        units_opp  = [u for u in state.units.values() if u.owner == opp and u.is_alive]
        hp_me  = sum(u.hp for u in units_me)
        hp_opp = sum(u.hp for u in units_opp)
        return (
            (state.stars[me] - state.stars[opp])
            + 10  * (cities_me - cities_opp)
            +  2  * (len(units_me) - len(units_opp))
            +  0.5 * (hp_me - hp_opp)
        )

    def select_action(self, state, legal_actions):
        return max(legal_actions, key=lambda a: self.evaluate(apply_action(state, a)))
```

**Loop de iteración recomendado.**

1. Editar pesos o reglas en `heuristic_bot.py`.
2. Verificar comportamiento en una partida visual:
   `python -m polytopia.game_loop --watch --eval` (o la variante gráfica
   `make gui-live-heuristic`) y observar qué acciones está priorizando.
3. Medir win rate vs `RandomBot` (ver sección [Benchmark](#benchmark)).
4. Repetir.

**Hooks útiles durante el desarrollo:**

- `make watch-eval` imprime las top-3 acciones evaluadas en cada frame, con
  su score. Útil para ver cuándo la heurística diverge de lo intuitivo.
- `make gui-live-heuristic` corre el bot en la GUI con HUD; la bottom bar
  muestra la última acción.
- `--seed N` fija la semilla del estado inicial; útil para comparar dos
  versiones del bot sobre el mismo tablero.

> Pendiente: el documento `guia_heuristica_persona_B.md` mencionado en
> conversaciones previas todavía no existe en el repo. Por ahora, las pistas
> de iteración están en `NEXT_STEPS.md`.

## Benchmark

> **Pendiente: módulo `experiments/benchmark.py` aún no implementado.**

La intención es que exista un comando `python -m experiments.benchmark` que
corra N partidas (default `n=20` seeds) entre dos bots y reporte: wins,
draws, win rate, turnos promedio y duración. Mientras tanto, un benchmark
manual se puede armar con:

```python
from polytopia.agents.random_bot import RandomBot
from polytopia.engine.state_init import create_initial_state
from polytopia.game_loop import run_game

wins = {0: 0, 1: 0, None: 0}
for seed in range(20):
    state = create_initial_state(seed=seed)
    bot0 = RandomBot(player_id=0, seed=seed + 100)
    bot1 = RandomBot(player_id=1, seed=seed + 200)
    result = run_game(bot0, bot1, state)
    wins[result["winner"]] += 1
print(wins)
```

**Objetivos.**

- Mínimo aceptable: `HeuristicBot` con ≥ 80 % de win rate vs `RandomBot`
  sobre `n=20` seeds.
- Stretch: ≥ 90 % manteniendo decisiones interpretables (cada acción
  trazable a un componente claro de la función de evaluación).

## Tests

```bash
make test            # corre toda la suite (pytest)
```

> Pendiente: target `make test-fast` mencionado en la plantilla todavía no
> existe en el Makefile.

**Estado actual.** 66 tests pasando, 3 skipped (los skipped son smokes de la
GUI que requieren un display real). La cobertura está distribuida así:

| Archivo                          | Cubre                                                       |
|----------------------------------|-------------------------------------------------------------|
| `test_interfaces.py`             | Stats de unidades, territorio propio, terreno transitable.  |
| `test_map.py`                    | Generación de mapa, bordes de agua, fog inicial.            |
| `test_legal_actions.py`          | Enumerador de acciones legales por tipo.                    |
| `test_rules.py`                  | Combate, RECOVER, end-turn tick, game over.                 |
| `test_terminal_renderer.py`     | Renderer ASCII y prompt humano.                             |
| `test_watch_mode.py`             | Modo watch silencioso vs activo, `_format_action`.          |
| `test_game_loop.py`              | `run_game` end-to-end, claves del dict de resultado.        |
| `test_replay.py`                 | Roundtrip record → save → load.                             |
| `test_gui_iso.py`                | Proyección iso, polígono de tile, smokes de pygame.         |

**Test crítico manual.** Para validar que la fórmula de combate de Polytopia
está bien implementada:

```python
from polytopia.interfaces import Position, Unit, UnitType
from polytopia.engine.rules import resolve_combat

w0 = Unit(0, 0, UnitType.WARRIOR, Position(0, 0))
w1 = Unit(1, 1, UnitType.WARRIOR, Position(1, 0))
dmg, retal = resolve_combat(w0, w1, defender_terrain_bonus=1.0)
# WARRIOR vs WARRIOR sano sin bonus -> daño 4-5 a cada lado
assert 4 <= dmg <= 5 and 4 <= retal <= 5
```

El test equivalente automatizado vive en
`tests/test_rules.py::test_combat_warrior_vs_warrior_no_bonus_balanced`.

## Arquitectura

Flujo de datos de una partida:

```
[game_loop] -> requests legal_actions -> [engine.actions]
     |
     +-> selects action via bot --------> [agents.heuristic_bot or random_bot]
     |
     +-> applies action ----------------> [engine.rules.apply_action]
     |
     +-> renders state -----------------> [renderers.terminal or renderers.gui]
     |
     +-> records frame -----------------> [replay.recorder]  (opcional)
```

`game_loop.run_game(bot0, bot1, state, ...)` orquesta el bucle. La variante
gráfica `renderers.gui.live_runner.run_game_live(...)` reemplaza el render
por una ventana pygame y agrega controles de teclado, pero el contrato con
el motor es el mismo.

**Decisiones de diseño documentadas.**

- **Estado inmutable**: `apply_action(state, action)` retorna un *nuevo*
  `GameState` (vía `copy.deepcopy`), no muta el original. Esto permite a la
  heurística probar acciones (`evaluate(apply_action(state, a))`) sin
  romper el estado actual del juego. Cuesta más memoria pero simplifica
  enormemente la lógica del bot y de los renderers (especialmente de
  `replay`, que conserva snapshots).
- **`Action` genérica con campos opcionales**: en vez de N subclases por
  tipo, una sola dataclass con `action_type` + `unit_id?`, `city_id?`,
  `target?`, `unit_type_to_train?`. Simplifica enormemente el contrato de
  `bot.select_action(state, list[Action])` pero requiere validación
  defensiva en `apply_action` (cubierta por `test_rules.py`).
- **Two-renderer split**: terminal vs GUI son módulos completamente
  separados que comparten el engine. Esto permite que la GUI (con sus
  dependencias pygame pesadas y su requerimiento de display) sea opcional.
- **Replay como JSON**: deliberadamente legible y editable a mano. El
  costo en tamaño es asumible (~50 KB por partida) y a cambio se obtiene
  inspección manual trivial y diff entre versiones.
- **Fog of war per-player**: cada jugador tiene su propio mapa de
  `FogState` (`UNKNOWN` / `SEEN` / `VISIBLE`). Esto es lo que permite que
  el modo `--viewer N` muestre la partida desde la perspectiva de un solo
  jugador, fundamental para la presentación.

## Roles del equipo

| Persona | Módulos                                          | Responsabilidad                                                            |
|---------|--------------------------------------------------|----------------------------------------------------------------------------|
| A       | `engine/`, `interfaces.py`                       | Reglas auténticas de Polytopia, optimización del motor, tests del motor.   |
| B       | `agents/heuristic_bot.py`                        | Diseño e iteración de la heurística. Objetivo: vencer al baseline.         |
| C       | `renderers/gui/`, `replay/`, `experiments/` (TBD) | Interfaz gráfica, replay, benchmarks, demo del jueves.                     |

Ver `NEXT_STEPS.md` para el desglose detallado de tareas por persona.

## Limitaciones conocidas

- **Sin animaciones de transición** en pygame: las unidades "saltan" entre
  tiles. Suficiente para ver la lógica del bot, no para impresionar
  visualmente.
- **Sin scrolling de cámara**: el mapa entero debe caber en la ventana
  (1280×800 default). Tableros mayores a ~15×15 se ven apretados.
- **Sin sonido.**
- **Mapa máximo recomendado**: 15×15. Más allá, la GUI no escala y el motor
  empieza a notar el costo de `legal_actions`.
- **`legal_actions` es O(unidades × tiles)** por jugador. Para tableros
  grandes o muchas unidades es el cuello de botella obvio. Persona A tiene
  esto en su backlog.
- **Sin paralelización de partidas**: el benchmark (cuando exista) correrá
  partidas en serie. Para `n=20` esto es trivial; para experimentos de
  miles, requerirá `multiprocessing.Pool`.
- **`HeuristicBot.select_action` sigue siendo un stub** que lanza
  `NotImplementedError`. Es deliberado: es el slot de Persona B.

## Troubleshooting

- **`make test` falla con `ModuleNotFoundError`**: verificá que estás en un
  venv activo con Python ≥ 3.11 y que ejecutaste
  `pip install -e ".[dev]"`. El proyecto usa hatchling como build backend;
  un `pip` muy viejo (< 21) puede fallar.
- **`make gui-demo` no abre ventana o lanza `pygame.error: video system not
  initialized`**: probablemente no instalaste el extra `gui`. Corré
  `pip install -e ".[dev,gui]"`. Si estás en SSH, necesitás X11 forwarding
  (`ssh -X`) o limitarte al renderer terminal.
- **`make gui-replay` imprime `Usa: make gui-replay FILE=...`**: el target
  requiere la variable `FILE`. Ejemplo:
  `make gui-replay FILE=replays/last_game.json`.
- **El bot heurístico pierde contra random**: probablemente los pesos no
  son comparables entre sí. Como regla general, `W_CITY` debe ser ~10× más
  grande que `W_STARS` y ~5× más grande que `W_UNITS`. Usá `make
  watch-eval` para ver qué está priorizando.
- **El damage calculation parece raro**: validá manualmente con el snippet
  de la sección [Tests](#tests). WARRIOR vs WARRIOR sano sin bonus debe
  dar 4-5 a cada lado. Recordá que Python usa banker's rounding
  (`round(4.5) == 4`), por eso algunos casos limítrofes dan números pares.
- **`make watch-step` no avanza**: estás en un terminal sin TTY (e.g.,
  pipe). Corré el comando en un terminal interactivo real.

## Referencias

- *The Battle of Polytopia* Wiki — stats oficiales, fórmula de combate
  exacta y constantes (`COMBAT_MULTIPLIER = 4.5`,
  `CITY_DEFENSE_BONUS = 1.5`). La fuente para los números en
  `interfaces.UNIT_STATS`.
- Russell & Norvig, *Artificial Intelligence: A Modern Approach* —
  capítulos de búsqueda adversarial y teoría de juegos; marco mental para
  `evaluate(state)` y la heurística greedy.
- Sutton & Barto, *Reinforcement Learning: An Introduction* — funciones
  de valor y heurísticas; relevante si la extensión natural del proyecto
  fuera reemplazar el greedy por value iteration o MCTS.

## Licencia y creditos

Proyecto académico para el curso de Foundations of AI. Implementación
independiente, no afiliada con Midjiwan. Las mecánicas de juego están
inspiradas en *The Battle of Polytopia* (Midjiwan AB); el código de este
repositorio es original.
