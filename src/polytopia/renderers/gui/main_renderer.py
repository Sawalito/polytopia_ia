import pygame

from polytopia.interfaces import FogState, GameState, Position
from polytopia.renderers.gui import colors
from polytopia.renderers.gui.iso_projection import compute_camera_offset
from polytopia.renderers.gui.terrain_renderer import render_tile


class PolytopiaRenderer:
    """Renderer pygame del estado del juego."""

    def __init__(
        self,
        board_size: int,
        window_width: int = 1280,
        window_height: int = 800,
        title: str = "Polytopia AI",
    ):
        pygame.init()
        self.screen = pygame.display.set_mode((window_width, window_height))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.board_size = board_size
        self.window_size = (window_width, window_height)
        self.camera_offset = compute_camera_offset(
            board_size, window_width, window_height
        )
        self.font_small = pygame.font.SysFont("Arial", 14)
        self.font_medium = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 28, bold=True)

    def render(self, state: GameState, viewer_player: int | None = None) -> None:
        """Renderiza el estado completo en la ventana."""
        self.screen.fill(colors.BACKGROUND)
        self._render_terrain(state, viewer_player)
        pygame.display.flip()

    def _render_terrain(
        self, state: GameState, viewer_player: int | None
    ) -> None:
        """Itera tiles de arriba a abajo, izquierda a derecha para que los
        cercanos al observador se pinten sobre los lejanos."""
        for y in range(self.board_size):
            for x in range(self.board_size):
                pos = Position(x, y)
                tile = state.tile_at(pos)
                if tile is None:
                    continue
                fog_state = (
                    state.fog[viewer_player][pos]
                    if viewer_player is not None
                    else FogState.VISIBLE
                )
                render_tile(
                    self.screen,
                    pos,
                    tile.terrain,
                    tile.resource,
                    fog_state,
                    self.camera_offset,
                )

    def handle_quit(self) -> bool:
        """Procesa eventos. True si el usuario cerró la ventana o pulsó ESC."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return True
        return False

    def close(self) -> None:
        pygame.quit()


def demo_main() -> None:
    """Renderiza un estado inicial y mantiene la ventana abierta hasta cerrar."""
    from polytopia.engine.state_init import create_initial_state

    state = create_initial_state(seed=42)
    renderer = PolytopiaRenderer(board_size=state.board_size)
    running = True
    while running:
        renderer.render(state, viewer_player=None)
        running = not renderer.handle_quit()
        renderer.clock.tick(30)
    renderer.close()


if __name__ == "__main__":
    demo_main()
