"""GameCoordinator — orchestrates AI generation, state, and game flow."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from phantom_seed.ai.gemini_client import GeminiClient
from phantom_seed.ai.imagen_client import ImagenClient
from phantom_seed.ai.protocol import (
    FALLBACK_SCENE,
    CharacterProfile,
    SceneData,
    VisualType,
)
from phantom_seed.core.roguelike import generate_memory_fragment, roll_random_event
from phantom_seed.core.seed_engine import (
    derive_initial_atmosphere,
    derive_trait_code,
    hash_seed,
)
from phantom_seed.core.state import GameState

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class GameCoordinator:
    """Central coordinator that drives the game loop."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.gemini = GeminiClient(config)
        self.imagen = ImagenClient(config)
        self.state = GameState(
            sanity=config.initial_sanity,
            favor=config.initial_affection,
        )
        self.character: CharacterProfile | None = None
        self.seed_hash: str = ""
        self.atmosphere: str = ""
        self.current_scene: SceneData | None = None
        self.character_sprite_path: Path | None = None
        # Background description → generated image path (reuse across scenes)
        self._bg_cache: dict[str, str] = {}
        self._bg_lock = threading.Lock()

    def _bg_key(self, desc: str) -> str:
        """Normalize a background description into a cache key."""
        return desc.lower().strip()[:80]

    def _get_or_generate_bg(self, desc: str, *, is_cg: bool = False) -> str | None:
        """Return cached bg path or generate a new one. Thread-safe."""
        key = self._bg_key(desc)
        with self._bg_lock:
            if key in self._bg_cache:
                log.debug("BG cache hit for: %s", key[:40])
                return self._bg_cache[key]
        # Generate outside the lock so we don't block other threads
        try:
            if is_cg:
                path = self.imagen.generate_cg(desc)
            else:
                path = self.imagen.generate_background(desc)
            if path:
                with self._bg_lock:
                    self._bg_cache[key] = str(path)
                return str(path)
        except Exception:
            log.exception("Background generation failed for: %s", desc[:60])
        return None

    def _generate_transition_bgs_async(self, scene: SceneData) -> None:
        """Fire-and-forget: pre-generate backgrounds for all scene_transitions."""
        descs = set()
        for line in scene.script:
            if line.scene_transition:
                descs.add(line.scene_transition)
        for desc in descs:
            key = self._bg_key(desc)
            with self._bg_lock:
                if key in self._bg_cache:
                    continue
            t = threading.Thread(
                target=self._get_or_generate_bg,
                args=(desc,),
                daemon=True,
            )
            t.start()

    def get_cached_bg(self, desc: str) -> str | None:
        """Return a cached background path if available (non-blocking)."""
        key = self._bg_key(desc)
        with self._bg_lock:
            return self._bg_cache.get(key)

    def init_game(self, seed_string: str) -> SceneData:
        """Initialize a new game run from a seed string."""
        self.seed_hash = hash_seed(seed_string)
        trait_code = derive_trait_code(self.seed_hash)
        self.atmosphere = derive_initial_atmosphere(self.seed_hash)

        # Generate character
        try:
            self.character = self.gemini.generate_character(self.seed_hash, trait_code)
            log.info("Character generated: %s", self.character.name)
        except Exception:
            log.exception("Failed to generate character")
            self.character = CharacterProfile(
                name="???",
                personality="神秘而不可捉摸",
                speech_pattern="说话断断续续，偶尔会沉默",
                visual_description="a mysterious figure with silver hair and red eyes, dark school uniform",
            )

        # Generate sprite
        try:
            self.character_sprite_path = self.imagen.generate_character_sprite(
                self.character.visual_description
            )
        except Exception:
            log.exception("Failed to generate character sprite")

        # Generate first scene
        return self.get_next_scene()

    def get_next_scene(
        self, player_choice: str = "", choice_delta: dict[str, int] | None = None
    ) -> SceneData:
        """Generate the next scene, applying any choice effects."""
        if choice_delta:
            self.state.apply_delta(choice_delta)

        if self.state.is_game_over:
            fragment = generate_memory_fragment(
                self.state.history, self.state.round_number
            )
            self.state.memory_fragments.append(fragment)
            return self._game_over_scene()

        self.state.advance_round()
        random_event = roll_random_event(self.state.round_number, self.state.sanity)

        try:
            assert self.character is not None
            scene = self.gemini.generate_scene(
                character_profile=self.character,
                sanity=self.state.sanity,
                favor=self.state.favor,
                round_number=self.state.round_number,
                history_summary=self.state.get_history_summary(),
                last_choice=player_choice,
                random_event=random_event,
                chapter_beat=self.state.chapter_beat,
            )
        except Exception:
            log.exception("Scene generation failed, using fallback")
            scene = FALLBACK_SCENE

        if scene.game_state_update.is_ending:
            self.state.is_ending = True

        # Record history (multiple lines for longer scenes)
        if scene.script:
            speakers = set(
                l.speaker for l in scene.script if l.speaker not in ("旁白", "系统")
            )
            summary = f"[场景{self.state.round_number}] {', '.join(speakers)} — {scene.script[0].text[:40]}"
            self.state.add_history(summary)

        # Generate main background (or CG)
        if scene.visual_type == VisualType.CINEMATIC_CG and scene.climax_cg_prompt:
            path = self._get_or_generate_bg(scene.climax_cg_prompt, is_cg=True)
            if path:
                scene.background = path
        elif scene.background:
            path = self._get_or_generate_bg(scene.background)
            if path:
                scene.background = path

        # Pre-generate transition backgrounds in background threads (non-blocking)
        self._generate_transition_bgs_async(scene)

        self.current_scene = scene
        return scene

    def _game_over_scene(self) -> SceneData:
        return SceneData(
            scene_id="game_over",
            background="deep void, endless darkness, faint glowing particles",
            script=[
                {
                    "speaker": "系统",
                    "text": "你的意识沉入了黑暗之中......",
                    "inner_monologue": "一切都结束了。但是，似乎有什么残留了下来。",
                }
            ],
            choices=[
                {"text": "重新开始", "target_state_delta": {}},
            ],
            game_state_update={"is_climax": False, "is_ending": True},
        )

        """Initialize a new game run from a seed string.

        1. Hash the seed
        2. Generate character profile via Gemini
        3. Generate character base sprite via Imagen
        4. Generate the first scene
        """
        self.seed_hash = hash_seed(seed_string)
        trait_code = derive_trait_code(self.seed_hash)
        self.atmosphere = derive_initial_atmosphere(self.seed_hash)

        # Generate character
        try:
            self.character = self.gemini.generate_character(self.seed_hash, trait_code)
            log.info("Character generated: %s", self.character.name)
        except Exception:
            log.exception("Failed to generate character")
            self.character = CharacterProfile(
                name="???",
                personality="神秘而不可捉摸",
                speech_pattern="说话断断续续，偶尔会沉默",
                visual_description="a mysterious figure with silver hair and red eyes, dark school uniform",
            )

        # Generate sprite
        try:
            self.character_sprite_path = self.imagen.generate_character_sprite(
                self.character.visual_description
            )
        except Exception:
            log.exception("Failed to generate character sprite")

        # Generate first scene
        return self.get_next_scene()

    def get_next_scene(
        self, player_choice: str = "", choice_delta: dict[str, int] | None = None
    ) -> SceneData:
        """Generate the next scene, applying any choice effects."""
        if choice_delta:
            self.state.apply_delta(choice_delta)

        if self.state.is_game_over:
            fragment = generate_memory_fragment(
                self.state.history, self.state.round_number
            )
            self.state.memory_fragments.append(fragment)
            return self._game_over_scene()

        self.state.advance_round()

        # Roll for random event
        random_event = roll_random_event(self.state.round_number, self.state.sanity)

        try:
            assert self.character is not None
            scene = self.gemini.generate_scene(
                character_profile=self.character,
                sanity=self.state.sanity,
                favor=self.state.favor,
                round_number=self.state.round_number,
                history_summary=self.state.get_history_summary(),
                last_choice=player_choice,
                random_event=random_event,
            )
        except Exception:
            log.exception("Scene generation failed, using fallback")
            scene = FALLBACK_SCENE

        # Check for ending
        if scene.game_state_update.is_ending:
            self.state.is_ending = True

        # Record history
        if scene.script:
            first_line = scene.script[0]
            self.state.add_history(f"[{first_line.speaker}] {first_line.text[:40]}")

        # Generate CG or background image
        if scene.visual_type == VisualType.CINEMATIC_CG and scene.climax_cg_prompt:
            try:
                cg_path = self.imagen.generate_cg(scene.climax_cg_prompt)
                if cg_path:
                    scene.background = str(cg_path)
            except Exception:
                log.exception("CG generation failed")
        else:
            # Generate background from the scene's background description
            if scene.background:
                try:
                    bg_path = self.imagen.generate_background(scene.background)
                    if bg_path:
                        scene.background = str(bg_path)
                        log.info("Background generated: %s", bg_path)
                except Exception:
                    log.exception("Background generation failed")

        self.current_scene = scene
        return scene

    def _game_over_scene(self) -> SceneData:
        return SceneData(
            scene_id="game_over",
            background="void",
            script=[
                {
                    "speaker": "系统",
                    "text": "你的意识沉入了黑暗之中......",
                    "inner_monologue": "一切都结束了。但是，似乎有什么残留了下来。",
                }
            ],
            choices=[
                {"text": "重新开始", "target_state_delta": {}},
            ],
            game_state_update={"is_climax": False, "is_ending": True},
        )
