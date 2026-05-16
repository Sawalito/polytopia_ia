from polytopia.engine.map_gen import generate_map, get_starting_positions, initial_fog
from polytopia.interfaces import City, GameState, Unit, UnitType

INITIAL_STARS = 5
INITIAL_VISION_RANGE = 2


def create_initial_state(
    board_size: int = 11,
    max_turns: int = 30,
    seed: int = 42,
) -> GameState:
    tiles = generate_map(board_size, seed)
    p0_start, p1_start = get_starting_positions(board_size)

    cities = {
        0: City(city_id=0, owner=0, position=p0_start),
        1: City(city_id=1, owner=1, position=p1_start),
    }

    units = {
        0: Unit(unit_id=0, owner=0, unit_type=UnitType.WARRIOR, position=p0_start),
        1: Unit(unit_id=1, owner=1, unit_type=UnitType.WARRIOR, position=p1_start),
    }

    stars = {0: INITIAL_STARS, 1: INITIAL_STARS}

    fog = {
        0: initial_fog(board_size, p0_start, vision_range=INITIAL_VISION_RANGE),
        1: initial_fog(board_size, p1_start, vision_range=INITIAL_VISION_RANGE),
    }

    return GameState(
        turn=1,
        current_player=0,
        max_turns=max_turns,
        board_size=board_size,
        tiles=tiles,
        units=units,
        cities=cities,
        stars=stars,
        fog=fog,
    )
