"""Settings overlay UI for Phantom Seed."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from phantom_seed.ui.fonts import get_font

if TYPE_CHECKING:
    from phantom_seed.config import Config


class SettingsOverlay:
    """Renders and handles the settings overlay."""

    TEXT_SPEED_OPTIONS = [
        ("慢速", 60),
        ("普通", 30),
        ("快速", 15),
        ("瞬间", 0),
    ]

    AUTO_PLAY_OPTIONS = [
        ("慢速", 3000),
        ("普通", 1500),
        ("快速", 800),
    ]

    FULLSCREEN_OPTIONS = [
        ("窗口", False),
        ("全屏", True),
    ]

    def __init__(self, screen_w: int, screen_h: int, config: Config) -> None:
        self.sw = screen_w
        self.sh = screen_h
        self.config = config
        self.active = False

        self._title_font: pygame.font.Font | None = None
        self._label_font: pygame.font.Font | None = None
        self._opt_font: pygame.font.Font | None = None
        self._hint_font: pygame.font.Font | None = None

        self._option_rects: list[list[pygame.Rect]] = []  # per-setting option rects
        self._hovered: tuple[int, int] = (-1, -1)  # (setting_idx, option_idx)

    def _ensure_fonts(self) -> None:
        if self._title_font is None:
            self._title_font = get_font(26, bold=True)
            self._label_font = get_font(20)
            self._opt_font = get_font(18)
            self._hint_font = get_font(15)

    def open(self) -> None:
        self.active = True
        self._hovered = (-1, -1)

    def close(self) -> None:
        self.active = False
        self.config.save_settings()

    def _current_indices(self) -> list[int]:
        """Return currently selected index for each setting."""
        # Text speed
        ts_idx = 1  # default "普通"
        for i, (_, val) in enumerate(self.TEXT_SPEED_OPTIONS):
            if val == self.config.text_speed_ms:
                ts_idx = i
                break

        # Auto play
        ap_idx = 1
        for i, (_, val) in enumerate(self.AUTO_PLAY_OPTIONS):
            if val == self.config.auto_play_ms:
                ap_idx = i
                break

        # Fullscreen
        fs_idx = 1 if self.config.fullscreen else 0

        return [ts_idx, ap_idx, fs_idx]

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Returns 'close' when overlay should close, else None."""
        if not self.active:
            return None

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return "close"

        if event.type == pygame.MOUSEMOTION:
            self._hovered = (-1, -1)
            for si, row in enumerate(self._option_rects):
                for oi, rect in enumerate(row):
                    if rect.collidepoint(event.pos):
                        self._hovered = (si, oi)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for si, row in enumerate(self._option_rects):
                for oi, rect in enumerate(row):
                    if rect.collidepoint(event.pos):
                        self._apply_selection(si, oi)
                        return None
            # Click outside panel → close
            pw, ph = 500, 320
            px = (self.sw - pw) // 2
            py = (self.sh - ph) // 2
            panel_rect = pygame.Rect(px, py, pw, ph)
            if not panel_rect.collidepoint(event.pos):
                self.close()
                return "close"

        return None

    def _apply_selection(self, setting_idx: int, option_idx: int) -> None:
        if setting_idx == 0:  # Text speed
            self.config.text_speed_ms = self.TEXT_SPEED_OPTIONS[option_idx][1]
        elif setting_idx == 1:  # Auto play
            self.config.auto_play_ms = self.AUTO_PLAY_OPTIONS[option_idx][1]
        elif setting_idx == 2:  # Fullscreen
            self.config.fullscreen = self.FULLSCREEN_OPTIONS[option_idx][1]

    def render(self, screen: pygame.Surface) -> None:
        if not self.active:
            return
        self._ensure_fonts()
        assert self._title_font and self._label_font and self._opt_font and self._hint_font

        # Dim background
        dim = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        screen.blit(dim, (0, 0))

        # Panel
        pw, ph = 500, 320
        px = (self.sw - pw) // 2
        py = (self.sh - ph) // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((50, 38, 55, 245))
        screen.blit(panel, (px, py))
        pygame.draw.rect(screen, (200, 150, 180), (px, py, pw, ph), 2)

        # Title
        t = self._title_font.render("─── 设  置 ───", True, (255, 210, 230))
        screen.blit(t, (px + (pw - t.get_width()) // 2, py + 18))

        # Hint
        hint = self._hint_font.render("ESC 关闭", True, (140, 120, 140))
        screen.blit(hint, (px + pw - hint.get_width() - 16, py + 22))

        current = self._current_indices()
        self._option_rects = []

        settings = [
            ("文字速度", [l for l, _ in self.TEXT_SPEED_OPTIONS]),
            ("自动播放", [l for l, _ in self.AUTO_PLAY_OPTIONS]),
            ("显示模式", [l for l, _ in self.FULLSCREEN_OPTIONS]),
        ]

        start_y = py + 70
        for si, (label, options) in enumerate(settings):
            row_y = start_y + si * 70

            # Label
            lbl = self._label_font.render(label, True, (220, 200, 215))
            screen.blit(lbl, (px + 30, row_y + 6))

            # Option buttons
            opt_x = px + 170
            opt_w = 70
            opt_h = 34
            opt_spacing = 10
            row_rects: list[pygame.Rect] = []

            for oi, opt_label in enumerate(options):
                r = pygame.Rect(opt_x + oi * (opt_w + opt_spacing), row_y, opt_w, opt_h)
                row_rects.append(r)

                is_selected = oi == current[si]
                is_hover = self._hovered == (si, oi)

                if is_selected:
                    bg = (160, 90, 130, 240)
                    border = (240, 170, 200)
                    color = (255, 245, 250)
                elif is_hover:
                    bg = (100, 60, 85, 200)
                    border = (200, 150, 175)
                    color = (240, 230, 240)
                else:
                    bg = (60, 40, 55, 180)
                    border = (120, 90, 110)
                    color = (180, 165, 180)

                btn = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                btn.fill(bg)
                screen.blit(btn, r.topleft)
                pygame.draw.rect(screen, border, r, 2 if is_selected or is_hover else 1)

                txt = self._opt_font.render(opt_label, True, color)
                screen.blit(
                    txt, (r.x + (r.w - txt.get_width()) // 2, r.y + (r.h - txt.get_height()) // 2)
                )

            self._option_rects.append(row_rects)
