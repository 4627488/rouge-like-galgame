"""Save / Load / Backlog overlay UI for Phantom Seed."""

from __future__ import annotations

import base64
import io
import logging
from enum import Enum, auto
from typing import TYPE_CHECKING

import pygame

from phantom_seed.core.save_system import SLOT_NAMES, BacklogEntry
from phantom_seed.ui.fonts import get_font

if TYPE_CHECKING:
    from phantom_seed.core.save_system import SaveSystem

log = logging.getLogger(__name__)


class OverlayMode(Enum):
    NONE = auto()
    SAVE = auto()
    LOAD = auto()
    BACKLOG = auto()
    CONTEXT_MENU = auto()


class SaveMenuOverlay:
    """Handles SAVE / LOAD / BACKLOG / context-menu overlays."""

    def __init__(self, screen_w: int, screen_h: int, save_system: SaveSystem) -> None:
        self.sw = screen_w
        self.sh = screen_h
        self.save_system = save_system
        self.mode = OverlayMode.NONE

        # fonts (lazy)
        self._font_title: pygame.font.Font | None = None
        self._font_body: pygame.font.Font | None = None
        self._font_small: pygame.font.Font | None = None
        self._font_hint: pygame.font.Font | None = None

        # slot info cache (refreshed each open)
        self._slot_infos: dict[str, dict | None] = {}
        self._slot_rects: list[tuple[str, pygame.Rect]] = []
        self._thumbnails: dict[str, pygame.Surface] = {}

        # backlog
        self._backlog: list[BacklogEntry] = []
        self._backlog_scroll = 0  # pixel offset from top
        self._backlog_line_h = 0  # computed once

        # context menu
        self._ctx_pos = (0, 0)
        self._ctx_items: list[tuple[str, str]] = []  # (label, action)
        self._ctx_rects: list[tuple[str, pygame.Rect]] = []
        self._ctx_hover = -1

        # hover
        self._slot_hover = -1

    # ── Public API ──────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self.mode != OverlayMode.NONE

    def open_save(self) -> None:
        self._refresh_slots()
        self.mode = OverlayMode.SAVE
        self._slot_hover = -1

    def open_load(self) -> None:
        self._refresh_slots()
        self.mode = OverlayMode.LOAD
        self._slot_hover = -1

    def open_backlog(self, backlog: list[BacklogEntry]) -> None:
        self._backlog = backlog
        self._backlog_scroll = max(0, self._get_backlog_total_h() - self.sh + 100)
        self.mode = OverlayMode.BACKLOG

    def open_context(self, pos: tuple[int, int], in_game: bool) -> None:
        self._ctx_pos = pos
        self._ctx_items = []
        if in_game:
            self._ctx_items = [
                ("F5  快速存档", "qsave"),
                ("F9  快速读档", "qload"),
                ("S   存档", "save"),
                ("L   读档", "load"),
                ("B   回放日志", "backlog"),
            ]
        else:
            self._ctx_items = [
                ("F9  快速读档", "qload"),
                ("L   读档", "load"),
            ]
        self.mode = OverlayMode.CONTEXT_MENU
        self._ctx_hover = -1
        self._build_ctx_rects()

    def close(self) -> None:
        self.mode = OverlayMode.NONE

    # ── Event handling ──────────────────────────────────────────

    def handle_event(
        self,
        event: pygame.event.Event,
    ) -> str | None:
        """Process an event.  Returns an action string or None.
        Actions: 'save:<slot>', 'load:<slot>', 'close', 'qsave', 'qload'
        """
        if self.mode == OverlayMode.NONE:
            return None

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return "close"

        if self.mode in (OverlayMode.SAVE, OverlayMode.LOAD):
            return self._handle_slot_event(event)
        elif self.mode == OverlayMode.BACKLOG:
            return self._handle_backlog_event(event)
        elif self.mode == OverlayMode.CONTEXT_MENU:
            return self._handle_ctx_event(event)
        return None

    def _handle_slot_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.MOUSEMOTION:
            self._slot_hover = -1
            for i, (slot, rect) in enumerate(self._slot_rects):
                if rect.collidepoint(event.pos):
                    self._slot_hover = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for slot, rect in self._slot_rects:
                if rect.collidepoint(event.pos):
                    action = "save" if self.mode == OverlayMode.SAVE else "load"
                    self.close()
                    return f"{action}:{slot}"
            # clicked outside → close
            self.close()
            return "close"
        return None

    def _handle_backlog_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.MOUSEWHEEL:
            self._backlog_scroll = max(
                0,
                min(
                    self._backlog_scroll - event.y * 40,
                    max(0, self._get_backlog_total_h() - self.sh + 100),
                ),
            )
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.close()
            return "close"
        elif event.type == pygame.KEYDOWN and event.key in (
            pygame.K_UP,
            pygame.K_DOWN,
            pygame.K_PAGEUP,
            pygame.K_PAGEDOWN,
        ):
            step = 120 if event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN) else 40
            direction = -1 if event.key in (pygame.K_UP, pygame.K_PAGEUP) else 1
            self._backlog_scroll = max(
                0,
                min(
                    self._backlog_scroll + direction * step,
                    max(0, self._get_backlog_total_h() - self.sh + 100),
                ),
            )
        return None

    def _handle_ctx_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.MOUSEMOTION:
            self._ctx_hover = -1
            for i, (action, rect) in enumerate(self._ctx_rects):
                if rect.collidepoint(event.pos):
                    self._ctx_hover = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for action, rect in self._ctx_rects:
                if rect.collidepoint(event.pos):
                    self.close()
                    return action
            self.close()
            return "close"
        return None

    # ── Rendering ───────────────────────────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        if self.mode == OverlayMode.SAVE:
            self._render_slot_panel(screen, is_save=True)
        elif self.mode == OverlayMode.LOAD:
            self._render_slot_panel(screen, is_save=False)
        elif self.mode == OverlayMode.BACKLOG:
            self._render_backlog(screen)
        elif self.mode == OverlayMode.CONTEXT_MENU:
            self._render_context(screen)

    def _render_slot_panel(self, screen: pygame.Surface, *, is_save: bool) -> None:
        assert self._font_title and self._font_body and self._font_small

        # Dim background
        dim = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        screen.blit(dim, (0, 0))

        # Panel
        pw, ph = 860, 520
        px = (self.sw - pw) // 2
        py = (self.sh - ph) // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((18, 12, 32, 245))
        screen.blit(panel, (px, py))
        pygame.draw.rect(screen, (130, 90, 200), (px, py, pw, ph), 2)

        # Title
        title_text = "─── 存  档 ───" if is_save else "─── 读  档 ───"
        t = self._font_title.render(title_text, True, (200, 160, 255))
        screen.blit(t, (px + (pw - t.get_width()) // 2, py + 18))

        # Hint
        hint = self._font_small.render("ESC 关闭", True, (90, 80, 110))
        screen.blit(hint, (px + pw - hint.get_width() - 16, py + 22))

        # Slots
        slot_h = 88
        slot_margin = 12
        start_y = py + 72
        self._slot_rects = []

        for i, slot in enumerate(SLOT_NAMES):
            sy = start_y + i * (slot_h + slot_margin)
            rect = pygame.Rect(px + 24, sy, pw - 48, slot_h)
            self._slot_rects.append((slot, rect))

            hover = i == self._slot_hover
            bg = (40, 25, 65, 220) if hover else (25, 16, 42, 200)
            border = (180, 130, 255) if hover else (70, 50, 100)

            slot_surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            slot_surf.fill(bg)
            screen.blit(slot_surf, rect.topleft)
            pygame.draw.rect(screen, border, rect, 2 if hover else 1)

            info = self._slot_infos.get(slot)
            slot_label = "QUICK" if slot == "QUICK" else f"SLOT {slot}"

            # Slot label
            lbl = self._font_body.render(
                slot_label, True, (160, 120, 220) if not info else (220, 190, 255)
            )
            screen.blit(lbl, (rect.x + 12, rect.y + 8))

            if info is None:
                empty = self._font_small.render("─── 空存档 ───", True, (80, 70, 100))
                screen.blit(empty, (rect.x + 12, rect.y + 42))
            else:
                # Thumbnail
                thumb = self._thumbnails.get(slot)
                if thumb:
                    screen.blit(thumb, (rect.x + 12, rect.y + 8))
                    tx_off = 12 + thumb.get_width() + 16
                else:
                    tx_off = 12

                # Meta info
                ts = self._font_small.render(info["timestamp"], True, (160, 150, 180))
                screen.blit(ts, (rect.x + tx_off, rect.y + 6))

                char_name = self._font_body.render(info["char"], True, (230, 210, 255))
                screen.blit(char_name, (rect.x + tx_off, rect.y + 28))

                meta = self._font_small.render(
                    f"第 {info['round']} 幕   SAN {info['sanity']}   FAV {info['favor']}",
                    True,
                    (140, 130, 160),
                )
                screen.blit(meta, (rect.x + tx_off, rect.y + 56))

    def _render_backlog(self, screen: pygame.Surface) -> None:
        assert self._font_body and self._font_small

        # Full-screen dark bg
        bg = pygame.Surface((self.sw, self.sh), pygame.SRCALPHA)
        bg.fill((8, 5, 18, 235))
        screen.blit(bg, (0, 0))

        # Title bar
        pygame.draw.rect(screen, (25, 15, 45), (0, 0, self.sw, 44))
        t = self._font_body.render("回 放 日 志", True, (200, 160, 255))
        screen.blit(t, ((self.sw - t.get_width()) // 2, 10))
        hint = self._font_small.render(
            "↑↓ / 滚轮 滚动   点击任意处关闭", True, (90, 80, 110)
        )
        screen.blit(hint, (self.sw - hint.get_width() - 20, 14))

        # Clip to content area
        clip_rect = pygame.Rect(0, 48, self.sw, self.sh - 48)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        lh = 26  # speaker line
        ih = 22  # inner monologue line
        margin = 60
        y = 56 - self._backlog_scroll
        line_w = self.sw - margin * 2

        for entry in self._backlog:
            if y + lh + ih > 48 and y < self.sh:
                # Speaker + dialogue
                spk_color = (180, 140, 240)
                txt_color = (220, 215, 235)
                imono_color = (120, 110, 150)

                # Wrap long text
                words = self._wrap_text(entry.text, self._font_body, line_w - 80)  # type: ignore[arg-type]
                for wi, line in enumerate(words):
                    ly = y + wi * lh
                    if 48 <= ly < self.sh:
                        if wi == 0:
                            spk = self._font_small.render(f"【{entry.speaker}】", True, spk_color)  # type: ignore[union-attr]
                            screen.blit(spk, (margin, ly))
                        txt = self._font_body.render(line, True, txt_color)  # type: ignore[union-attr]
                        screen.blit(txt, (margin + 90, ly))

                total_lines = max(1, len(words))
                y += total_lines * lh

                if entry.inner_monologue:
                    wrapped_im = self._wrap_text(entry.inner_monologue, self._font_small, line_w - 60)  # type: ignore[arg-type]
                    for line in wrapped_im:
                        if 48 <= y < self.sh:
                            im_surf = self._font_small.render(  # type: ignore[union-attr]
                                f"（{line}）", True, imono_color
                            )
                            screen.blit(im_surf, (margin + 30, y))
                        y += ih
                y += 8  # between entries
            else:
                # Estimate height and skip
                lines_est = max(1, len(entry.text) // 30 + 1)
                y += lines_est * lh + 8
                if entry.inner_monologue:
                    im_lines = max(1, len(entry.inner_monologue) // 40 + 1)
                    y += im_lines * ih

        screen.set_clip(old_clip)

        # Scrollbar
        total_h = self._get_backlog_total_h()
        visible_h = self.sh - 48
        if total_h > visible_h:
            bar_h = max(30, int(visible_h * visible_h / total_h))
            bar_y = 48 + int(
                self._backlog_scroll / max(1, total_h - visible_h) * (visible_h - bar_h)
            )
            pygame.draw.rect(screen, (60, 45, 90), (self.sw - 8, 48, 6, visible_h))
            pygame.draw.rect(screen, (160, 120, 220), (self.sw - 8, bar_y, 6, bar_h))

    def _render_context(self, screen: pygame.Surface) -> None:
        assert self._font_body and self._font_small
        if not self._ctx_rects:
            return
        # Shadow
        iw = 210
        total_h = len(self._ctx_rects) * 38 + 8
        mx, my = self._ctx_pos
        mx = min(mx, self.sw - iw - 4)
        my = min(my, self.sh - total_h - 4)

        panel = pygame.Surface((iw, total_h), pygame.SRCALPHA)
        panel.fill((18, 12, 32, 240))
        screen.blit(panel, (mx, my))
        pygame.draw.rect(screen, (120, 80, 180), (mx, my, iw, total_h), 1)

        for i, (action, _) in enumerate(self._ctx_rects):
            label = self._ctx_items[i][0]
            item_rect = pygame.Rect(mx + 2, my + 4 + i * 38, iw - 4, 34)
            if i == self._ctx_hover:
                pygame.draw.rect(screen, (55, 30, 90), item_rect)
            color = (230, 210, 255) if i == self._ctx_hover else (170, 150, 200)
            txt = self._font_body.render(label, True, color)
            screen.blit(txt, (item_rect.x + 12, item_rect.y + 7))

    # ── Helpers ─────────────────────────────────────────────────

    def _ensure_fonts(self) -> None:
        if self._font_title is None:
            self._font_title = get_font(26, bold=True)
            self._font_body = get_font(20)
            self._font_small = get_font(17)
            self._font_hint = get_font(15)
            self._backlog_line_h = 26

    def _refresh_slots(self) -> None:
        self._slot_infos = {}
        self._thumbnails = {}
        for slot in SLOT_NAMES:
            info = self.save_system.slot_info(slot)
            self._slot_infos[slot] = info
            if info and info.get("thumbnail_b64"):
                try:
                    raw = base64.b64decode(info["thumbnail_b64"])
                    import pygame

                    surf = pygame.image.load(io.BytesIO(raw))
                    self._thumbnails[slot] = pygame.transform.smoothscale(
                        surf, (120, 68)
                    )
                except Exception:
                    pass

    def _build_ctx_rects(self) -> None:
        mx, my = self._ctx_pos
        iw = 210
        mx = min(mx, self.sw - iw - 4)
        my = min(my, self.sh - len(self._ctx_items) * 38 - 12)
        self._ctx_rects = [
            (action, pygame.Rect(mx + 2, my + 4 + i * 38, iw - 4, 34))
            for i, (label, action) in enumerate(self._ctx_items)
        ]

    def _get_backlog_total_h(self) -> int:
        lh, ih = 26, 22
        total = 0
        for entry in self._backlog:
            lines = max(1, len(entry.text) // 30 + 1)
            total += lines * lh + 8
            if entry.inner_monologue:
                total += max(1, len(entry.inner_monologue) // 40 + 1) * ih
        return total + 20

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        """Simple greedy word/character wrap."""
        lines: list[str] = []
        current = ""
        for ch in text:
            test = current + ch
            if font.size(test)[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines or [""]
