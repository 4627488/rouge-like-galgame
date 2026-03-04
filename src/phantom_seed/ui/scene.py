"""Scene rendering — backgrounds and character sprites."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pygame

from phantom_seed.ai.protocol import Position, SceneData, StageAction, StageCommand
from phantom_seed.ui.assets import create_placeholder, load_image


class CharacterSprite:
    """Tracks a character's on-screen position and animation."""

    def __init__(self, char_id: str, sprite_path: Path | None = None) -> None:
        self.char_id = char_id
        self.sprite_path = sprite_path
        self.target_x = 0.0
        self.current_x = 0.0
        self.y = 0
        self.alpha = 255
        self.visible = False
        self.surface: pygame.Surface | None = None
        self.shake_timer = 0

    def load(self, screen_h: int) -> None:
        if self.surface is not None:
            return  # already loaded, skip
        if self.sprite_path:
            # Load at original resolution to get true aspect ratio
            orig = load_image(self.sprite_path)
            if orig:
                target_h = int(screen_h * 0.78)
                orig_w, orig_h = orig.get_size()
                target_w = (
                    int(orig_w * target_h / orig_h)
                    if orig_h > 0
                    else int(target_h * 0.55)
                )
                self.surface = pygame.transform.smoothscale(orig, (target_w, target_h))
        if self.surface is None:
            # Unique silhouette color per character based on their ID hash
            h_val = int(hashlib.md5(self.char_id.encode()).hexdigest()[:6], 16)
            r = 30 + (h_val >> 16 & 0xFF) % 80
            g = 15 + (h_val >> 8 & 0xFF) % 50
            b = 50 + (h_val & 0xFF) % 100
            self.surface = create_placeholder(200, int(screen_h * 0.6), (r, g, b))

    def set_position(self, pos: Position, screen_w: int) -> None:
        positions = {
            Position.LEFT: screen_w * 0.2,
            Position.CENTER: screen_w * 0.5,
            Position.RIGHT: screen_w * 0.8,
        }
        self.target_x = positions.get(pos, screen_w * 0.5)

    def update(self, dt_ms: int) -> None:
        # Smooth movement
        speed = 0.008 * dt_ms
        diff = self.target_x - self.current_x
        if abs(diff) > 1:
            self.current_x += diff * speed
        else:
            self.current_x = self.target_x

        # Shake effect
        if self.shake_timer > 0:
            self.shake_timer = max(0, self.shake_timer - dt_ms)

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible or self.surface is None:
            return
        x = int(self.current_x - self.surface.get_width() / 2)
        y = self.y

        # Apply shake
        if self.shake_timer > 0:
            import random

            x += random.randint(-3, 3)
            y += random.randint(-2, 2)

        if self.alpha < 255:
            temp = self.surface.copy()
            temp.set_alpha(self.alpha)
            screen.blit(temp, (x, y))
        else:
            screen.blit(self.surface, (x, y))


class SceneRenderer:
    """Manages background and character sprite rendering for a scene."""

    def __init__(self, screen_w: int, screen_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.characters: dict[str, CharacterSprite] = {}
        self.background: pygame.Surface | None = None
        # When True (CG scenes), character sprites are suppressed
        self.hide_sprites: bool = False
        self.bg_path: str = ""
        # Main character sprite path — used as fallback for any unregistered ID
        self._main_sprite_path: Path | None = None
        self._main_char_id: str = ""

    def set_character_sprite_path(self, char_id: str, path: Path | None) -> None:
        """Register a character's sprite image path (and record as main character)."""
        self._main_sprite_path = path
        self._main_char_id = char_id
        if char_id not in self.characters:
            self.characters[char_id] = CharacterSprite(char_id, path)
        else:
            sprite = self.characters[char_id]
            sprite.sprite_path = path
            sprite.surface = None  # force reload with correct aspect ratio

    def _resolve_sprite_path(self, char_id: str) -> Path | None:
        """Return the best known sprite path for this char_id.
        Falls back to the main character sprite if no exact match.
        """
        # Exact match first
        if char_id in self.characters and self.characters[char_id].sprite_path:
            return self.characters[char_id].sprite_path
        # Substring / case-insensitive match against registered names
        cid_low = char_id.lower().replace(" ", "")
        for registered_id, sprite in self.characters.items():
            reg_low = registered_id.lower().replace(" ", "")
            if cid_low in reg_low or reg_low in cid_low:
                return sprite.sprite_path
        # Final fallback: main character sprite
        return self._main_sprite_path

    def apply_scene(self, scene: SceneData) -> None:
        """Apply a scene's stage commands."""
        # Hide character sprites for cinematic CG scenes
        from phantom_seed.ai.protocol import VisualType
        self.hide_sprites = (scene.visual_type == VisualType.CINEMATIC_CG)

        # Update background — only load real image files (AI-generated paths)
        if scene.background and scene.background != self.bg_path:
            self.bg_path = scene.background
            bg_path = Path(scene.background)
            if bg_path.suffix and bg_path.exists():
                bg = load_image(scene.background, (self.screen_w, self.screen_h))
                self.background = bg  # None if load fails, will show black fill
            else:
                self.background = None  # No image available yet — use black fill

        # Process stage commands
        for cmd in scene.stage_commands:
            self._execute_command(cmd)

    def _execute_command(self, cmd: StageCommand) -> None:
        char_id = cmd.character
        if char_id not in self.characters:
            # Resolve sprite path (fuzzy match or main character fallback)
            resolved_path = self._resolve_sprite_path(char_id)
            self.characters[char_id] = CharacterSprite(char_id, resolved_path)

        sprite = self.characters[char_id]
        # If sprite was previously created without a path but we now have one, update it
        if sprite.sprite_path is None and self._main_sprite_path:
            sprite.sprite_path = self._resolve_sprite_path(char_id)

        if cmd.action == StageAction.ENTER:
            sprite.load(self.screen_h)
            sprite.visible = True
            sprite.set_position(cmd.pos, self.screen_w)
            sprite.current_x = sprite.target_x
            sprite.y = (
                self.screen_h
                - (sprite.surface.get_height() if sprite.surface else 400)
                - 20
            )

        elif cmd.action == StageAction.LEAVE:
            sprite.visible = False

        elif cmd.action == StageAction.MOVE:
            sprite.set_position(cmd.pos, self.screen_w)

    def update(self, dt_ms: int) -> None:
        for sprite in self.characters.values():
            sprite.update(dt_ms)

    def render(self, screen: pygame.Surface) -> None:
        # Background
        if self.background:
            screen.blit(self.background, (0, 0))
        else:
            screen.fill((12, 8, 22))

        # Sprites hidden for CG scenes (CG image covers the full canvas)
        if not self.hide_sprites:
            visible = [s for s in self.characters.values() if s.visible]
            visible.sort(key=lambda s: s.current_x)
            for sprite in visible:
                sprite.render(screen)
