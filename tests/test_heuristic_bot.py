import copy

from polytopia.agents.heuristic_bot import HeuristicBot
from polytopia.engine.actions import legal_actions
from polytopia.engine.rules import apply_action
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import (
    Action,
    ActionType,
    City,
    FogState,
    Position,
    Unit,
    UnitType,
)


def test_bot_returns_legal_action():
    """El bot debe retornar una accion que este en la lista de legales."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)
    actions = legal_actions(state, 0)
    assert actions, "Debe haber acciones legales en el estado inicial"
    chosen = bot.select_action(state, actions)
    assert chosen in actions, "El bot retorno una accion fuera de las legales"


def test_evaluate_returns_float():
    """evaluate debe retornar un numero, accesible publicamente."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)
    score = bot.evaluate(state)
    assert isinstance(score, (int, float))


def test_evaluate_prefers_more_cities():
    """Un estado con mas cities propias debe evaluarse mas alto que uno con menos."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    score_base = bot.evaluate(state)

    # Forzar artificialmente una city extra del P0 modificando el state
    # (solo para test; no usar este patron en codigo de produccion).
    state_extra_city = copy.deepcopy(state)
    extra_city_id = max(state_extra_city.cities.keys()) + 1
    new_pos = Position(5, 5)
    state_extra_city.cities[extra_city_id] = City(
        city_id=extra_city_id, owner=0, position=new_pos, level=1
    )

    score_with_extra = bot.evaluate(state_extra_city)
    assert score_with_extra > score_base, (
        f"Tener una city extra debe subir el score; base={score_base}, "
        f"extra={score_with_extra}"
    )


def test_evaluate_penalizes_exposed_archers():
    """Un archer adyacente a enemigo debe puntuar mas bajo que uno protegido."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    # Encontrar la unit existente de P0 y reemplazarla por un Archer
    p0_unit_id = next(uid for uid, u in state.units.items() if u.owner == 0)

    state_safe = copy.deepcopy(state)
    state_safe.units[p0_unit_id] = Unit(
        unit_id=p0_unit_id, owner=0, unit_type=UnitType.ARCHER,
        position=Position(0, 0),
    )

    state_exposed = copy.deepcopy(state)
    # Encontrar enemigo y poner archer adyacente
    p1_unit = next(u for u in state.units.values() if u.owner == 1)
    archer_pos = Position(p1_unit.position.x, p1_unit.position.y - 1)
    state_exposed.units[p0_unit_id] = Unit(
        unit_id=p0_unit_id, owner=0, unit_type=UnitType.ARCHER,
        position=archer_pos,
    )

    score_safe = bot.evaluate(state_safe)
    score_exposed = bot.evaluate(state_exposed)
    assert score_safe > score_exposed, (
        f"Archer expuesto debe puntuar peor que archer seguro; "
        f"safe={score_safe}, exposed={score_exposed}"
    )


def test_late_game_adjusts_stars_weight():
    """Despues del turno LATE_GAME_TURN, el peso de stars debe bajar.
    Esto se verifica indirectamente: el bot deja de preferir acumular stars."""
    bot = HeuristicBot(player_id=0)
    state_early = create_initial_state(seed=42)
    state_early.turn = 5
    state_late = create_initial_state(seed=42)
    state_late.turn = 25

    # Con muchas stars y todo lo demas igual, el score debe ser MENOR en late game
    # (porque w_stars baja de 1.0 a 0.2).
    state_early_rich = copy.deepcopy(state_early)
    state_early_rich.stars[0] = 100

    state_late_rich = copy.deepcopy(state_late)
    state_late_rich.stars[0] = 100

    bonus_early = bot.evaluate(state_early_rich) - bot.evaluate(state_early)
    bonus_late = bot.evaluate(state_late_rich) - bot.evaluate(state_late)

    assert bonus_late < bonus_early, (
        f"El bonus por tener stars debe ser menor en late game; "
        f"early_bonus={bonus_early}, late_bonus={bonus_late}"
    )


def test_jitter_is_deterministic_with_seed():
    """Dos bots con la misma seed deben tomar las mismas decisiones."""
    state = create_initial_state(seed=42)
    actions = legal_actions(state, 0)

    bot_a = HeuristicBot(player_id=0, seed=123)
    bot_b = HeuristicBot(player_id=0, seed=123)

    # Misma seed -> misma secuencia de decisiones
    for _ in range(5):
        action_a = bot_a.select_action(state, actions)
        action_b = bot_b.select_action(state, actions)
        assert action_a == action_b


def test_evaluate_rewards_proximity_to_enemy_city():
    """Una unit cerca de la city enemiga debe puntuar mejor que una lejos."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    enemy_city = next(c for c in state.cities.values() if c.owner == 1)

    # Forzar que P0 conozca la city enemiga (VISIBLE)
    state_known = copy.deepcopy(state)
    if 0 not in state_known.fog:
        state_known.fog[0] = {}
    state_known.fog[0][enemy_city.position] = FogState.VISIBLE

    p0_unit_id = next(uid for uid, u in state_known.units.items() if u.owner == 0)

    # Far state: unit en (0, 0)
    state_far = copy.deepcopy(state_known)
    state_far.units[p0_unit_id] = Unit(
        unit_id=p0_unit_id, owner=0, unit_type=UnitType.WARRIOR,
        position=Position(0, 0),
    )

    # Near state: unit adyacente a la city enemiga
    state_near = copy.deepcopy(state_known)
    near_pos = Position(enemy_city.position.x - 1, enemy_city.position.y)
    state_near.units[p0_unit_id] = Unit(
        unit_id=p0_unit_id, owner=0, unit_type=UnitType.WARRIOR,
        position=near_pos,
    )

    score_far = bot.evaluate(state_far)
    score_near = bot.evaluate(state_near)

    assert score_near > score_far, (
        f"Estar cerca de la city enemiga debe puntuar mas alto; "
        f"far={score_far:.2f}, near={score_near:.2f}"
    )


def test_action_bonus_penalizes_idle_end_turn():
    """END_TURN con unidades fresh debe tener bonus negativo."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    end_turn = Action(action_type=ActionType.END_TURN)
    bonus = bot._action_type_bonus(state, end_turn)

    assert bonus < 0, f"END_TURN con units fresh debe penalizar, dio {bonus}"


def test_action_bonus_rewards_capture():
    """CAPTURE siempre debe tener bonus grande."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    enemy_city = next(c for c in state.cities.values() if c.owner == 1)
    capture = Action(
        action_type=ActionType.CAPTURE,
        unit_id=1,
        city_id=enemy_city.city_id,
    )
    bonus = bot._action_type_bonus(state, capture)
    assert bonus >= bot.W_CITY, f"CAPTURE bonus debe ser muy alto; dio {bonus}"


def test_bot_moves_off_spawn_in_initial_turns():
    """Test integral: el bot debe haber movido la unidad inicial en
    las primeras 10 acciones. Verifica que el problema raiz de v1
    (quedarse en spawn) esta resuelto."""
    state = create_initial_state(seed=42)
    bot = HeuristicBot(player_id=0)

    initial_unit = next(u for u in state.units.values() if u.owner == 0)
    initial_position = initial_unit.position
    initial_unit_id = initial_unit.unit_id

    moved = False
    for _ in range(20):
        if state.current_player != 0:
            # Avanzar el turno de P1 con END_TURN para no contaminar el test
            actions = legal_actions(state, state.current_player)
            end = next((a for a in actions if a.action_type == ActionType.END_TURN), None)
            if end is None:
                break
            state = apply_action(state, end)
            continue

        actions = legal_actions(state, 0)
        if not actions:
            break
        action = bot.select_action(state, actions)
        state = apply_action(state, action)

        current_unit = state.units.get(initial_unit_id)
        if current_unit and current_unit.position != initial_position:
            moved = True
            break

    assert moved, (
        "El bot no movio la unidad inicial en 20 acciones. La presion "
        "ofensiva no esta dominando END_TURN."
    )


def test_lookahead_returns_legal_action():
    """Sanity: LookaheadBot retorna una accion legal."""
    from polytopia.agents.lookahead_bot import LookaheadBot

    state = create_initial_state(seed=42)
    bot = LookaheadBot(player_id=0)
    actions = legal_actions(state, 0)
    chosen = bot.select_action(state, actions)
    assert chosen in actions


def test_lookahead_smoke():
    """Lookahead corre una partida completa sin crashear."""
    from polytopia.agents.lookahead_bot import LookaheadBot
    from polytopia.agents.random_bot import RandomBot
    from polytopia.game_loop import run_game

    state = create_initial_state(seed=42)
    bot0 = LookaheadBot(player_id=0)
    bot1 = RandomBot(player_id=1, seed=1)
    result = run_game(bot0, bot1, state)
    assert result["winner"] in (0, 1, None)
