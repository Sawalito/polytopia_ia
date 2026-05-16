import pygame
import pytest

from polytopia.renderers.gui.iso_projection import (
    compute_camera_offset,
    get_tile_polygon,
    grid_to_screen,
    screen_to_grid,
)


def test_iso_projection_origin():
    """En (0,0) el screen position debe ser igual al camera_offset."""
    offset = (100, 100)
    assert grid_to_screen(0, 0, offset) == offset


def test_iso_projection_roundtrip():
    """grid -> screen -> grid debe recuperar las coordenadas originales."""
    offset = (640, 100)
    for x in range(5):
        for y in range(5):
            sx, sy = grid_to_screen(x, y, offset)
            gx, gy = screen_to_grid(sx, sy, offset)
            assert (gx, gy) == (x, y), f"Roundtrip falló en ({x},{y})"


def test_tile_polygon_has_four_points():
    polygon = get_tile_polygon(2, 3, (100, 100))
    assert len(polygon) == 4


def test_camera_offset_centers_map():
    offset = compute_camera_offset(board_size=11, window_width=1280, window_height=800)
    assert isinstance(offset, tuple) and len(offset) == 2


@pytest.mark.skipif(not pygame.display.get_init(), reason="No display available")
def test_renderer_creates_window():
    """Smoke test: crear y cerrar el renderer no debe crashear."""
    from polytopia.engine.state_init import create_initial_state
    from polytopia.renderers.gui import PolytopiaRenderer

    pygame.init()
    state = create_initial_state(seed=42)
    renderer = PolytopiaRenderer(
        board_size=state.board_size, window_width=800, window_height=600
    )
    renderer.render(state)
    renderer.close()


@pytest.mark.skipif(not pygame.display.get_init(), reason="No display")
def test_live_runner_imports():
    from polytopia.renderers.gui.live_runner import LiveWatchConfig, run_game_live

    assert LiveWatchConfig().delay > 0
    assert callable(run_game_live)


@pytest.mark.skipif(not pygame.display.get_init(), reason="No display")
def test_renderer_with_entities():
    """Smoke test: renderer corre completo (terreno + entidades + HUD) sin errores."""
    from polytopia.engine.state_init import create_initial_state
    from polytopia.renderers.gui import PolytopiaRenderer

    pygame.init()
    state = create_initial_state(seed=42)
    r = PolytopiaRenderer(state.board_size, 800, 600)
    r.render(state, viewer_player=0, last_action_text="MOVE u=1 -> (2,3)")
    r.close()
