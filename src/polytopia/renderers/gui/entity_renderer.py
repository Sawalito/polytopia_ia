import pygame

from polytopia.interfaces import City, FogState, GameState, Unit, UnitType
from polytopia.renderers.gui import colors
from polytopia.renderers.gui.iso_projection import grid_to_screen

PLAYER_COLORS = {0: colors.PLAYER_0, 1: colors.PLAYER_1}
PLAYER_COLORS_DARK = {0: colors.PLAYER_0_DARK, 1: colors.PLAYER_1_DARK}


def _dim(color: tuple[int, int, int], factor: float = 0.6) -> tuple[int, int, int]:
    return tuple(int(c * factor) for c in color)


def render_city(
    surface: pygame.Surface,
    city: City,
    camera_offset: tuple[int, int],
    font: pygame.font.Font,
    dimmed: bool = False,
) -> None:
    """Pirámide isométrica del color del jugador con su nivel encima."""
    cx, cy = grid_to_screen(city.position.x, city.position.y, camera_offset)
    player_color = PLAYER_COLORS[city.owner]
    dark_color = PLAYER_COLORS_DARK[city.owner]
    if dimmed:
        player_color = _dim(player_color)
        dark_color = _dim(dark_color)

    base_w = 36
    body_h = 24
    roof_h = 14

    base_pts = [
        (cx - base_w // 2, cy),
        (cx + base_w // 2, cy),
        (cx + base_w // 2 - 4, cy - body_h),
        (cx - base_w // 2 + 4, cy - body_h),
    ]
    pygame.draw.polygon(surface, dark_color, base_pts)
    pygame.draw.polygon(surface, (20, 20, 30), base_pts, width=2)

    roof_pts = [
        (cx - base_w // 2 + 4, cy - body_h),
        (cx + base_w // 2 - 4, cy - body_h),
        (cx, cy - body_h - roof_h),
    ]
    pygame.draw.polygon(surface, player_color, roof_pts)
    pygame.draw.polygon(surface, (20, 20, 30), roof_pts, width=2)

    level_text = font.render(str(city.level), True, colors.TEXT_PRIMARY)
    text_rect = level_text.get_rect(center=(cx, cy - body_h // 2))
    surface.blit(level_text, text_rect)


def render_unit(
    surface: pygame.Surface,
    unit: Unit,
    camera_offset: tuple[int, int],
    font: pygame.font.Font,
    dimmed: bool = False,
) -> None:
    """Forma por tipo (círculo/triángulo/rombo), letra dentro, barra de HP si dañado."""
    cx, cy = grid_to_screen(unit.position.x, unit.position.y, camera_offset)
    cy -= 8

    player_color = PLAYER_COLORS[unit.owner]
    dark_color = PLAYER_COLORS_DARK[unit.owner]
    if dimmed:
        player_color = _dim(player_color)
        dark_color = _dim(dark_color)

    size = 14
    letter = "?"

    if unit.unit_type == UnitType.WARRIOR:
        pygame.draw.circle(surface, dark_color, (cx, cy), size + 2)
        pygame.draw.circle(surface, player_color, (cx, cy), size)
        letter = "W"
    elif unit.unit_type == UnitType.ARCHER:
        pts = [(cx, cy - size), (cx - size, cy + size - 2), (cx + size, cy + size - 2)]
        outer = [
            (cx, cy - size - 2),
            (cx - size - 2, cy + size),
            (cx + size + 2, cy + size),
        ]
        pygame.draw.polygon(surface, dark_color, outer)
        pygame.draw.polygon(surface, player_color, pts)
        letter = "A"
    elif unit.unit_type == UnitType.RIDER:
        pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
        outer = [
            (cx, cy - size - 2),
            (cx + size + 2, cy),
            (cx, cy + size + 2),
            (cx - size - 2, cy),
        ]
        pygame.draw.polygon(surface, dark_color, outer)
        pygame.draw.polygon(surface, player_color, pts)
        letter = "R"

    letter_text = font.render(letter, True, (20, 20, 30))
    text_rect = letter_text.get_rect(center=(cx, cy))
    surface.blit(letter_text, text_rect)

    if unit.hp is not None and unit.hp < unit.max_hp:
        hp_ratio = unit.hp / unit.max_hp
        bar_w = 24
        bar_h = 4
        bx = cx - bar_w // 2
        by = cy + size + 4
        pygame.draw.rect(surface, (40, 40, 50), (bx, by, bar_w, bar_h))
        fill_w = int(bar_w * hp_ratio)
        if hp_ratio < 0.34:
            fill_color = (200, 60, 60)
        elif hp_ratio < 0.67:
            fill_color = (220, 180, 60)
        else:
            fill_color = (80, 200, 100)
        pygame.draw.rect(surface, fill_color, (bx, by, fill_w, bar_h))


def render_entities(
    surface: pygame.Surface,
    state: GameState,
    camera_offset: tuple[int, int],
    font: pygame.font.Font,
    viewer_player: int | None,
) -> None:
    """Pinta cities y luego units que el viewer puede ver."""
    for city in state.cities.values():
        fog = (
            state.fog[viewer_player][city.position]
            if viewer_player is not None
            else FogState.VISIBLE
        )
        if fog == FogState.UNKNOWN:
            continue
        render_city(surface, city, camera_offset, font, dimmed=(fog == FogState.SEEN))

    for unit in state.units.values():
        if not unit.is_alive:
            continue
        fog = (
            state.fog[viewer_player][unit.position]
            if viewer_player is not None
            else FogState.VISIBLE
        )
        if fog != FogState.VISIBLE:
            continue
        render_unit(surface, unit, camera_offset, font)
