"""Dialogue box rendering with typewriter effect."""

from __future__ import annotations

import pygame

from phantom_seed.ui.fonts import get_font


class DialogueBox:
    """Renders the dialogue box at the bottom of the screen."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_w = screen_width
        self.screen_h = screen_height

        # Box dimensions
        self.margin = 40
        self.box_height = 200
        self.box_y = screen_height - self.box_height - 20
        self.box_w = screen_width - self.margin * 2

        # Text
        self.name_font: pygame.font.Font | None = None
        self.text_font: pygame.font.Font | None = None
        self.mono_font: pygame.font.Font | None = None

        # Typewriter state
        self.full_text = ""
        self.inner_text = ""
        self.speaker = ""
        self.char_index = 0
        self.chars_per_tick = 1
        self.tick_timer = 0
        self.tick_interval_ms = 30
        self.finished = False

    def _ensure_fonts(self) -> None:
        if self.name_font is None:
            self.name_font = get_font(22, bold=True)
            self.text_font = get_font(20)
            self.mono_font = get_font(18, italic=True)

    def set_dialogue(self, speaker: str, text: str, inner_monologue: str = "") -> None:
        """Set new dialogue to display with typewriter effect."""
        self.speaker = speaker
        self.full_text = text
        self.inner_text = inner_monologue
        self.char_index = 0
        self.tick_timer = 0
        self.finished = False

    def skip(self) -> None:
        """Skip typewriter and show full text immediately."""
        self.char_index = len(self.full_text)
        self.finished = True

    def update(self, dt_ms: int) -> None:
        """Advance the typewriter effect."""
        if self.finished:
            return
        self.tick_timer += dt_ms
        while self.tick_timer >= self.tick_interval_ms:
            self.tick_timer -= self.tick_interval_ms
            self.char_index = min(self.char_index + self.chars_per_tick, len(self.full_text))
        if self.char_index >= len(self.full_text):
            self.finished = True

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        assert self.text_font is not None
        assert self.name_font is not None
        assert self.mono_font is not None

        # Semi-transparent box
        box_surf = pygame.Surface((self.box_w, self.box_height), pygame.SRCALPHA)
        box_surf.fill((10, 10, 30, 200))
        pygame.draw.rect(box_surf, (100, 100, 140, 180), (0, 0, self.box_w, self.box_height), 2)
        screen.blit(box_surf, (self.margin, self.box_y))

        # Speaker name
        if self.speaker:
            name_bg = pygame.Surface((len(self.speaker) * 20 + 24, 30), pygame.SRCALPHA)
            name_bg.fill((40, 20, 60, 220))
            screen.blit(name_bg, (self.margin + 16, self.box_y - 15))

            name_surf = self.name_font.render(self.speaker, True, (240, 200, 255))
            screen.blit(name_surf, (self.margin + 28, self.box_y - 12))

        # Main text (typewriter)
        visible_text = self.full_text[: self.char_index]
        self._render_wrapped_text(
            screen,
            visible_text,
            self.text_font,
            (230, 230, 240),
            self.margin + 24,
            self.box_y + 24,
            self.box_w - 48,
        )

        # Click indicator
        if self.finished:
            indicator_x = self.margin + self.box_w - 40
            indicator_y = self.box_y + self.box_height - 30
            tick = pygame.time.get_ticks()
            if (tick // 500) % 2 == 0:
                points = [
                    (indicator_x, indicator_y),
                    (indicator_x + 12, indicator_y + 8),
                    (indicator_x + 24, indicator_y),
                ]
                pygame.draw.polygon(screen, (200, 200, 220), points)

    def _render_wrapped_text(
        self,
        screen: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: tuple[int, int, int],
        x: int,
        y: int,
        max_width: int,
    ) -> None:
        """Render text with word wrapping (handles CJK characters)."""
        line_height = font.get_linesize() + 2
        current_x = x
        current_y = y

        for char in text:
            char_surf = font.render(char, True, color)
            char_w = char_surf.get_width()

            if char == "\n":
                current_x = x
                current_y += line_height
                continue

            if current_x + char_w > x + max_width:
                current_x = x
                current_y += line_height

            screen.blit(char_surf, (current_x, current_y))
            current_x += char_w
