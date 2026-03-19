"""Main menu UI for Phantom Seed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from phantom_seed.ui.fonts import get_font

if TYPE_CHECKING:
    from phantom_seed.core.save_system import SaveSystem


class MainMenu:
    """Renders the main menu with buttons."""

    BUTTONS = [
        ("开始游戏", "new_game"),
        ("继续游戏", "continue"),
        ("读取存档", "load"),
        ("设置", "settings"),
        ("退出", "exit"),
    ]

    def __init__(
        self, screen_w: int, screen_h: int, save_system: SaveSystem
    ) -> None:
        self.sw = screen_w
        self.sh = screen_h
        self.save_system = save_system

        self._title_font: pygame.font.Font | None = None
        self._btn_font: pygame.font.Font | None = None
        self._hint_font: pygame.font.Font | None = None

        self._rects: list[pygame.Rect] = []
        self._hovered = -1

    def _ensure_fonts(self) -> None:
        if self._title_font is None:
            self._title_font = get_font(52, bold=True)
            self._btn_font = get_font(24)
            self._hint_font = get_font(16)

    def _has_quick_save(self) -> bool:
        return self.save_system.slot_info("QUICK") is not None

    def _build_rects(self) -> None:
        btn_w, btn_h = 280, 48
        spacing = 14
        total_h = len(self.BUTTONS) * btn_h + (len(self.BUTTONS) - 1) * spacing
        start_y = self.sh // 2 + 20
        start_x = (self.sw - btn_w) // 2
        self._rects = [
            pygame.Rect(start_x, start_y + i * (btn_h + spacing), btn_w, btn_h)
            for i in range(len(self.BUTTONS))
        ]

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Returns action string or None."""
        if not self._rects:
            self._build_rects()

        if event.type == pygame.MOUSEMOTION:
            self._hovered = -1
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    self._hovered = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if rect.collidepoint(event.pos):
                    action = self.BUTTONS[i][1]
                    # "continue" is disabled if no quick save
                    if action == "continue" and not self._has_quick_save():
                        return None
                    return action
        return None

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        assert self._title_font is not None
        assert self._btn_font is not None
        assert self._hint_font is not None

        if not self._rects:
            self._build_rects()

        # Background
        screen.fill((50, 40, 55))

        # Title
        title = self._title_font.render("Phantom Seed", True, (255, 210, 230))
        tx = (self.sw - title.get_width()) // 2
        screen.blit(title, (tx, self.sh // 2 - 140))

        # Subtitle
        sub = self._hint_font.render(
            "— 命运的种子，恋爱的物语 —", True, (200, 170, 190)
        )
        sx = (self.sw - sub.get_width()) // 2
        screen.blit(sub, (sx, self.sh // 2 - 70))

        has_quick = self._has_quick_save()

        for i, ((label, action), rect) in enumerate(
            zip(self.BUTTONS, self._rects)
        ):
            is_hover = i == self._hovered
            disabled = action == "continue" and not has_quick

            if disabled:
                bg_color = (50, 40, 48, 120)
                border_color = (80, 70, 75)
                text_color = (100, 90, 95)
            elif is_hover:
                bg_color = (120, 70, 100, 220)
                border_color = (230, 170, 200)
                text_color = (255, 240, 245)
            else:
                bg_color = (70, 45, 65, 200)
                border_color = (150, 110, 140)
                text_color = (220, 200, 215)

            btn_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            btn_surf.fill(bg_color)
            screen.blit(btn_surf, rect.topleft)
            pygame.draw.rect(screen, border_color, rect, 2)

            text_surf = self._btn_font.render(label, True, text_color)
            text_x = rect.x + (rect.w - text_surf.get_width()) // 2
            text_y = rect.y + (rect.h - text_surf.get_height()) // 2
            screen.blit(text_surf, (text_x, text_y))
