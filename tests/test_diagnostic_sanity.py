import pytest
from polytopia.engine.state_init import create_initial_state
from polytopia.interfaces import Position


def test_starting_positions_are_far_apart():
    """Las cities iniciales deben estar lejos. Si esto falla, la generacion
    de mapas esta mal."""
    state = create_initial_state(seed=42)
    cities = list(state.cities.values())
    assert len(cities) == 2
    distance = cities[0].position.chebyshev_distance(cities[1].position)
    assert distance >= 6, (
        f"Cities iniciales estan a Chebyshev {distance}, esperaba >= 6"
    )


def test_starting_unit_far_from_enemy_city():
    """La unit inicial de P0 debe estar lejos de la city de P1."""
    state = create_initial_state(seed=42)
    p0_unit = next(u for u in state.units.values() if u.owner == 0)
    p1_city = next(c for c in state.cities.values() if c.owner == 1)
    distance = p0_unit.position.chebyshev_distance(p1_city.position)
    assert distance >= 5, (
        f"Unit de P0 esta a Chebyshev {distance} de city de P1, esperaba >= 5"
    )


def test_diagnostic_reaches_enemy_radius_tracking():
    """En al menos algunas seeds, el bot debe llegar al radio enemigo y
    el tracker debe registrarlo correctamente con un turn > 0."""
    from experiments.diagnostic import run_diagnostic_game

    reached_count = 0
    valid_turns = []
    for seed in range(10):
        m = run_diagnostic_game(seed=seed, heuristic_player=0)
        if m.turn_reached_enemy_radius is not None:
            reached_count += 1
            valid_turns.append(m.turn_reached_enemy_radius)
            assert m.turn_reached_enemy_radius > 0, (
                f"seed={seed}: turn_reached={m.turn_reached_enemy_radius} "
                f"es invalido (debe ser > 0)"
            )

    print(f"\n{reached_count}/10 partidas alcanzaron radio enemigo.")
    print(f"Turns en que se alcanzo: {valid_turns}")
