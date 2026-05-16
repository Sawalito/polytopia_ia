import pygame

from polytopia.interfaces import GameState
from polytopia.renderers.gui import colors


def render_hud(
    surface: pygame.Surface,
    state: GameState,
    window_size: tuple[int, int],
    font_small: pygame.font.Font,
    font_medium: pygame.font.Font,
    font_large: pygame.font.Font,
    last_action_text: str | None = None,
    viewer_player: int | None = None,
) -> None:
    """HUD: top bar con turno y stats, bottom bar con la última acción,
    overlay de game over si aplica."""
    width, height = window_size

    top_bar_h = 60
    pygame.draw.rect(surface, colors.HUD_BG, (0, 0, width, top_bar_h))
    pygame.draw.line(
        surface, colors.HUD_BORDER, (0, top_bar_h), (width, top_bar_h), 2
    )

    turn_text = font_large.render(
        f"Turn {state.turn}/{state.max_turns}", True, colors.TEXT_PRIMARY
    )
    surface.blit(turn_text, (20, 15))

    p0_stars = state.stars[0]
    p0_cities = sum(1 for c in state.cities.values() if c.owner == 0)
    p0_units = sum(1 for u in state.units.values() if u.owner == 0 and u.is_alive)
    p0_text = font_medium.render(
        f"P0  stars {p0_stars}   cities {p0_cities}   units {p0_units}",
        True,
        colors.PLAYER_0,
    )
    surface.blit(p0_text, (width // 2 - 240, 20))

    p1_stars = state.stars[1]
    p1_cities = sum(1 for c in state.cities.values() if c.owner == 1)
    p1_units = sum(1 for u in state.units.values() if u.owner == 1 and u.is_alive)
    p1_text = font_medium.render(
        f"P1  stars {p1_stars}   cities {p1_cities}   units {p1_units}",
        True,
        colors.PLAYER_1,
    )
    surface.blit(p1_text, (width // 2 + 60, 20))

    if not state.game_over:
        cp = state.current_player
        cp_color = colors.PLAYER_0 if cp == 0 else colors.PLAYER_1
        cp_text = font_small.render(f"Turno de P{cp}", True, cp_color)
        surface.blit(cp_text, (width - 150, 20))

    if last_action_text is not None:
        bot_bar_h = 40
        bot_y = height - bot_bar_h
        pygame.draw.rect(surface, colors.HUD_BG, (0, bot_y, width, bot_bar_h))
        pygame.draw.line(
            surface, colors.HUD_BORDER, (0, bot_y), (width, bot_y), 2
        )
        action_text = font_medium.render(
            last_action_text, True, colors.TEXT_PRIMARY
        )
        surface.blit(action_text, (20, bot_y + 8))

    if state.game_over:
        overlay = pygame.Surface(window_size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        if state.winner is not None:
            win_color = colors.PLAYER_0 if state.winner == 0 else colors.PLAYER_1
            text = font_large.render(f"Ganador: P{state.winner}", True, win_color)
        else:
            text = font_large.render("Empate", True, colors.STAR_GOLD)
        text_rect = text.get_rect(center=(width // 2, height // 2))
        surface.blit(text, text_rect)
