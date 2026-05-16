TILE_WIDTH = 64
TILE_HEIGHT = 32


def grid_to_screen(
    grid_x: int,
    grid_y: int,
    camera_offset: tuple[int, int],
) -> tuple[int, int]:
    """Convierte coordenadas de tablero a coordenadas de pantalla isométricas.

    Fórmula:
        screen_x = (grid_x - grid_y) * (TILE_WIDTH / 2) + camera_offset[0]
        screen_y = (grid_x + grid_y) * (TILE_HEIGHT / 2) + camera_offset[1]
    """
    sx = (grid_x - grid_y) * (TILE_WIDTH // 2) + camera_offset[0]
    sy = (grid_x + grid_y) * (TILE_HEIGHT // 2) + camera_offset[1]
    return (sx, sy)


def screen_to_grid(
    screen_x: int,
    screen_y: int,
    camera_offset: tuple[int, int],
) -> tuple[int, int]:
    """Inversa de grid_to_screen. Útil para detectar tile bajo el mouse."""
    dx = screen_x - camera_offset[0]
    dy = screen_y - camera_offset[1]
    gx = dx / TILE_WIDTH + dy / TILE_HEIGHT
    gy = dy / TILE_HEIGHT - dx / TILE_WIDTH
    return (int(round(gx)), int(round(gy)))


def get_tile_polygon(
    grid_x: int,
    grid_y: int,
    camera_offset: tuple[int, int],
) -> list[tuple[int, int]]:
    """Cuatro vértices del diamante del tile en orden top, right, bottom, left."""
    cx, cy = grid_to_screen(grid_x, grid_y, camera_offset)
    half_w = TILE_WIDTH // 2
    half_h = TILE_HEIGHT // 2
    return [
        (cx, cy - half_h),
        (cx + half_w, cy),
        (cx, cy + half_h),
        (cx - half_w, cy),
    ]


def compute_camera_offset(
    board_size: int,
    window_width: int,
    window_height: int,
) -> tuple[int, int]:
    """Centra el mapa isométrico en la ventana."""
    map_pixel_height = board_size * TILE_HEIGHT
    ox = window_width // 2
    oy = (window_height - map_pixel_height) // 2 + TILE_HEIGHT // 2
    return (ox, oy)
