import math

import pygame

from polytopia.interfaces import FogState, Position, ResourceType, TerrainType
from polytopia.renderers.gui import colors
from polytopia.renderers.gui.iso_projection import (
    TILE_HEIGHT,
    TILE_WIDTH,
    get_tile_polygon,
    grid_to_screen,
)


def _dim(color: tuple[int, int, int], factor: float = 0.6) -> tuple[int, int, int]:
    return tuple(int(c * factor) for c in color)


def render_tile(
    surface: pygame.Surface,
    position: Position,
    terrain: TerrainType,
    resource: ResourceType,
    fog_state: FogState,
    camera_offset: tuple[int, int],
) -> None:
    """Renderiza un tile individual con terreno, recurso (si aplica) y fog."""
    polygon = get_tile_polygon(position.x, position.y, camera_offset)

    base_colors = {
        TerrainType.FIELD: colors.GRASS_LIGHT,
        TerrainType.FOREST: colors.GRASS_DARK,
        TerrainType.MOUNTAIN: colors.MOUNTAIN_LIGHT,
        TerrainType.WATER: colors.WATER_LIGHT,
    }
    color = base_colors[terrain]

    if fog_state == FogState.UNKNOWN:
        pygame.draw.polygon(surface, colors.FOG_UNKNOWN, polygon)
        pygame.draw.polygon(surface, colors.TILE_OUTLINE, polygon, width=1)
        return

    if fog_state == FogState.SEEN:
        color = tuple(
            int(c * 0.5 + colors.FOG_SEEN[i] * 0.5) for i, c in enumerate(color)
        )

    pygame.draw.polygon(surface, color, polygon)
    pygame.draw.polygon(surface, colors.TILE_OUTLINE, polygon, width=1)

    dimmed = fog_state == FogState.SEEN

    if terrain == TerrainType.FOREST:
        _render_trees(surface, position, camera_offset, dimmed=dimmed)
    elif terrain == TerrainType.MOUNTAIN:
        _render_mountain_peak(surface, position, camera_offset, dimmed=dimmed)
    elif terrain == TerrainType.WATER:
        _render_water_lines(surface, position, camera_offset)

    if fog_state == FogState.VISIBLE:
        if resource == ResourceType.FRUIT:
            _render_fruit(surface, position, camera_offset)
        elif resource == ResourceType.ANIMAL:
            _render_animal(surface, position, camera_offset)


def _render_trees(surface, position, camera_offset, dimmed=False):
    """Dibuja 1-3 árboles en posiciones jittered estables (seed = hash de pos)."""
    cx, cy = grid_to_screen(position.x, position.y, camera_offset)
    seed = (position.x * 73856093) ^ (position.y * 19349663)
    n_trees = 1 + (seed % 3)
    foliage = _dim(colors.TREE_DARK) if dimmed else colors.TREE_DARK
    trunk = _dim(colors.TREE_TRUNK) if dimmed else colors.TREE_TRUNK
    for i in range(n_trees):
        sub = (seed >> (i * 5)) & 0xFFFF
        ox = ((sub & 0xFF) - 128) * (TILE_WIDTH // 6) // 256
        oy = (((sub >> 8) & 0xFF) - 128) * (TILE_HEIGHT // 4) // 256
        tx, ty = cx + ox, cy + oy
        pygame.draw.rect(surface, trunk, (tx - 1, ty - 2, 2, 6))
        pygame.draw.polygon(
            surface, foliage,
            [(tx, ty - 12), (tx - 5, ty - 2), (tx + 5, ty - 2)],
        )


def _render_mountain_peak(surface, position, camera_offset, dimmed=False):
    """Triángulo gris claro con punta blanca sobre el tile."""
    cx, cy = grid_to_screen(position.x, position.y, camera_offset)
    body = _dim(colors.MOUNTAIN_DARK) if dimmed else colors.MOUNTAIN_DARK
    snow = _dim(colors.SNOW) if dimmed else colors.SNOW
    apex = (cx, cy - TILE_HEIGHT // 2 - 4)
    left = (cx - TILE_WIDTH // 4, cy + 2)
    right = (cx + TILE_WIDTH // 4, cy + 2)
    pygame.draw.polygon(surface, body, [apex, left, right])
    mid_left = (cx - TILE_WIDTH // 12, cy - TILE_HEIGHT // 4)
    mid_right = (cx + TILE_WIDTH // 12, cy - TILE_HEIGHT // 4)
    pygame.draw.polygon(surface, snow, [apex, mid_left, mid_right])


def _render_water_lines(surface, position, camera_offset):
    """Líneas onduladas blancas tenues como olas."""
    cx, cy = grid_to_screen(position.x, position.y, camera_offset)
    color = (*colors.WATER_DARK, 0)
    for i, dy in enumerate((-6, 0, 6)):
        start_x = cx - TILE_WIDTH // 5
        end_x = cx + TILE_WIDTH // 5
        amplitude = 2
        points = []
        for step in range(7):
            t = step / 6
            x = int(start_x + t * (end_x - start_x))
            y = int(cy + dy + math.sin(t * math.pi * 2 + i) * amplitude)
            points.append((x, y))
        pygame.draw.lines(surface, color[:3], False, points, 1)


def _render_fruit(surface, position, camera_offset):
    """Círculo rojo pequeño en el centro del tile."""
    cx, cy = grid_to_screen(position.x, position.y, camera_offset)
    pygame.draw.circle(surface, colors.FRUIT, (cx, cy), 6)
    pygame.draw.circle(surface, (255, 255, 255), (cx - 2, cy - 2), 1)


def _render_animal(surface, position, camera_offset):
    """Óvalo marrón sobre el tile."""
    cx, cy = grid_to_screen(position.x, position.y, camera_offset)
    rect = pygame.Rect(0, 0, 14, 8)
    rect.center = (cx, cy)
    pygame.draw.ellipse(surface, colors.ANIMAL, rect)
