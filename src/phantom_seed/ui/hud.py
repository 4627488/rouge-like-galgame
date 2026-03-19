"""HUD — Affection status bar."""

from __future__ import annotations

import pygame

from phantom_seed.ui.fonts import get_font


class HUD:
    """Renders the top-left affection status bar."""

    def __init__(self, screen_width: int) -> None:
        self.x = 20
        self.y = 16
        self.bar_width = 180
        self.bar_height = 18
        self.spacing = 8
        self.font: pygame.font.Font | None = None
        self._screen_width = screen_width

    def _ensure_font(self) -> None:
        if self.font is None:
            self.font = get_font(16)

    def render(self, screen: pygame.Surface, affection: int) -> None:
        self._ensure_font()
        assert self.font is not None

        # Background panel
        panel_w = self.bar_width + 120
        panel_h = self.bar_height + self.spacing * 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 140))
        screen.blit(panel, (self.x - 8, self.y - 4))

        y = self.y
        self._draw_bar(
            screen, "好感度", affection, 100, y,
            (255, 150, 180), (100, 50, 70),
        )

    def _draw_bar(
        self,
        screen: pygame.Surface,
        label: str,
        value: int,
        max_value: int,
        y: int,
        fill_color: tuple[int, int, int],
        bg_color: tuple[int, int, int],
    ) -> None:
        assert self.font is not None

        # Label
        label_surf = self.font.render(f"{label}", True, (220, 220, 220))
        screen.blit(label_surf, (self.x, y))

        bar_x = self.x + 70
        ratio = max(0, min(1, value / max_value))

        # Background bar
        pygame.draw.rect(screen, bg_color, (bar_x, y + 2, self.bar_width, self.bar_height - 4))
        # Fill bar
        fill_w = int(self.bar_width * ratio)
        if fill_w > 0:
            pygame.draw.rect(screen, fill_color, (bar_x, y + 2, fill_w, self.bar_height - 4))
        # Border
        pygame.draw.rect(screen, (100, 100, 100), (bar_x, y + 2, self.bar_width, self.bar_height - 4), 1)

        # Value text
        val_surf = self.font.render(f"{value}", True, (255, 255, 255))
        screen.blit(val_surf, (bar_x + self.bar_width + 8, y))
