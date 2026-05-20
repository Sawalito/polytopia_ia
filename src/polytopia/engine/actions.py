from polytopia.interfaces import (
    UNIT_STATS,
    Action,
    ActionType,
    FogState,
    GameState,
    Position,
    ResourceType,
    UnitType,
)


def neighbors(pos: Position, size: int) -> list[Position]:
    out: list[Position] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = pos.x + dx, pos.y + dy
            if 0 <= nx < size and 0 <= ny < size:
                out.append(Position(nx, ny))
    return out


def tiles_in_range(pos: Position, range_: int, size: int) -> list[Position]:
    out: list[Position] = []
    for dx in range(-range_, range_ + 1):
        for dy in range(-range_, range_ + 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = pos.x + dx, pos.y + dy
            if 0 <= nx < size and 0 <= ny < size:
                out.append(Position(nx, ny))
    return out


def is_visible(state: GameState, player: int, pos: Position) -> bool:
    return state.fog[player].get(pos) == FogState.VISIBLE


def legal_actions(state: GameState, player: int) -> list[Action]:
    """Return every legal Action available to ``player`` in ``state``.

    The result is a flat list, suitable as the discrete action space for an agent.
    Order: per-unit (MOVE, ATTACK, HARVEST, RECOVER, CAPTURE), then TRAIN, then
    LEVEL_UP, then END_TURN.
    """
    if state.game_over or state.current_player != player:
        return []

    size = state.board_size
    player_fog = state.fog[player]

    own_units = [u for u in state.units.values() if u.owner == player and u.is_alive]
    own_unit_positions = {u.position for u in own_units}

    enemy_units_visible: dict[Position, int] = {
        u.position: u.unit_id
        for u in state.units.values()
        if u.owner != player and u.is_alive and player_fog.get(u.position) == FogState.VISIBLE
    }

    actions: list[Action] = []

    for unit in own_units:
        # MOVE: not attacked yet and not moved yet (no Escape skill).
        if not unit.has_moved and not unit.has_attacked:
            for target in tiles_in_range(unit.position, unit.movement, size):
                tile = state.tile_at(target)
                if tile is None or not tile.is_passable:
                    continue
                if target in own_unit_positions:
                    continue
                if target in enemy_units_visible:
                    continue
                fog_state = player_fog.get(target)
                if fog_state == FogState.UNKNOWN:
                    continue
                actions.append(
                    Action(
                        action_type=ActionType.MOVE,
                        unit_id=unit.unit_id,
                        target=target,
                    )
                )

        # ATTACK: move-then-attack is allowed; only blocked by prior attack.
        if not unit.has_attacked:
            for target in tiles_in_range(unit.position, unit.range, size):
                if target in enemy_units_visible:
                    actions.append(
                        Action(
                            action_type=ActionType.ATTACK,
                            unit_id=unit.unit_id,
                            target=target,
                        )
                    )

        # HARVEST: consumes the whole turn, so unit must be fresh.
        if not unit.has_moved and not unit.has_attacked:
            tile = state.tile_at(unit.position)
            if tile is not None and tile.resource != ResourceType.NONE:
                actions.append(
                    Action(action_type=ActionType.HARVEST, unit_id=unit.unit_id)
                )

        # RECOVER: fresh and damaged.
        if (
            not unit.has_moved
            and not unit.has_attacked
            and unit.hp is not None
            and unit.hp < unit.max_hp
        ):
            actions.append(
                Action(action_type=ActionType.RECOVER, unit_id=unit.unit_id)
            )

        # CAPTURE: on enemy city, no enemy stack on the city, no attack consumed.
        if not unit.has_attacked:
            city = next(
                (
                    c for c in state.cities.values()
                    if c.position == unit.position and c.owner != player
                ),
                None,
            )
            if city is not None:
                enemy_on_city = any(
                    u.position == city.position and u.owner != player and u.is_alive
                    for u in state.units.values()
                )
                if not enemy_on_city:
                    actions.append(
                        Action(
                            action_type=ActionType.CAPTURE,
                            unit_id=unit.unit_id,
                            city_id=city.city_id,
                        )
                    )

    # TRAIN: per city with at least one adjacent free passable tile.
    own_cities = state.cities_of(player)
    for city in own_cities:
        adjacent_free: list[Position] = []
        for npos in neighbors(city.position, size):
            tile = state.tile_at(npos)
            if tile is None or not tile.is_passable:
                continue
            if state.unit_at(npos) is not None:
                continue
            adjacent_free.append(npos)
        if not adjacent_free:
            continue
        for unit_type in UnitType:
            cost = UNIT_STATS[unit_type]["cost"]
            if state.stars[player] < cost:
                continue
            for tile_pos in adjacent_free:
                actions.append(
                    Action(
                        action_type=ActionType.TRAIN,
                        city_id=city.city_id,
                        unit_type_to_train=unit_type,
                        target=tile_pos,
                    )
                )

    # LEVEL_UP: cost = level * 5.
    for city in own_cities:
        if state.stars[player] >= city.level * 5:
            actions.append(
                Action(action_type=ActionType.LEVEL_UP, city_id=city.city_id)
            )

    actions.append(Action(action_type=ActionType.END_TURN))
    return actions
