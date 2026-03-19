"""Choice menu rendering."""

from __future__ import annotations

import pygame

from phantom_seed.ai.protocol import Choice
from phantom_seed.ui.fonts import get_font


class ChoiceMenu:
    """Renders interactive choice buttons."""

    def __init__(self, screen_width: int, screen_height: int) -> None:
        self.screen_w = screen_width
        self.screen_h = screen_height
        self.font: pygame.font.Font | None = None
        self.choices: list[Choice] = []
        self.hovered: int = -1
        self.selected: int = -1
        self._rects: list[pygame.Rect] = []
        self.visible = False

    def _ensure_font(self) -> None:
        if self.font is None:
            self.font = get_font(22)

    def show(self, choices: list[Choice]) -> None:
        """Display a set of choices."""
        self.choices = choices
        self.hovered = -1
        self.selected = -1
        self.visible = True
        self._build_rects()

    def hide(self) -> None:
        self.visible = False
        self.choices = []
        self._rects = []

    def _build_rects(self) -> None:
        self._ensure_font()
        btn_w = min(600, self.screen_w - 200)
        btn_h = 50
        spacing = 12
        total_h = len(self.choices) * btn_h + (len(self.choices) - 1) * spacing
        start_y = (self.screen_h - total_h) // 2
        start_x = (self.screen_w - btn_w) // 2

        self._rects = []
        for i in range(len(self.choices)):
            y = start_y + i * (btn_h + spacing)
            self._rects.append(pygame.Rect(start_x, y, btn_w, btn_h))

    def handle_mouse_move(self, pos: tuple[int, int]) -> None:
        if not self.visible:
            return
        self.hovered = -1
        for i, rect in enumerate(self._rects):
            if rect.collidepoint(pos):
                self.hovered = i
                break

    def handle_click(self, pos: tuple[int, int]) -> Choice | None:
        """Handle a click. Returns the selected Choice or None."""
        if not self.visible:
            return None
        for i, rect in enumerate(self._rects):
            if rect.collidepoint(pos):
                self.selected = i
                return self.choices[i]
        return None

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible or not self.choices:
            return
        self._ensure_font()
        assert self.font is not None

        # Dim overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        screen.blit(overlay, (0, 0))

        for i, (choice, rect) in enumerate(zip(self.choices, self._rects)):
            is_hover = i == self.hovered

            # Button background
            bg_color = (120, 70, 100, 220) if is_hover else (70, 45, 65, 200)
            border_color = (220, 170, 200) if is_hover else (140, 100, 130)

            btn_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            btn_surf.fill(bg_color)
            screen.blit(btn_surf, rect.topleft)
            pygame.draw.rect(screen, border_color, rect, 2)

            # Text
            text_color = (255, 240, 245) if is_hover else (220, 210, 220)
            text_surf = self.font.render(choice.text, True, text_color)
            text_x = rect.x + (rect.w - text_surf.get_width()) // 2
            text_y = rect.y + (rect.h - text_surf.get_height()) // 2
            screen.blit(text_surf, (text_x, text_y))

            # Stat delta hint
            if choice.target_state_delta:
                hints = []
                for stat, val in choice.target_state_delta.items():
                    sign = "+" if val > 0 else ""
                    label_name = "好感度" if stat == "affection" else stat
                    hints.append(f"{label_name} {sign}{val}")
                hint_text = " | ".join(hints)
                hint_surf = self.font.render(hint_text, True, (180, 140, 160))
                screen.blit(hint_surf, (rect.right - hint_surf.get_width() - 12, rect.y + 4))
