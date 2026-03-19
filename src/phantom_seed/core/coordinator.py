"""GameCoordinator — orchestrates AI generation, state, and game flow."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from phantom_seed.ai.chains import CharacterChain, SceneChain
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

ProgressCallback = Callable[[int, int, str], None]


class GameCoordinator:
    """Central coordinator that drives the game loop."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.character_chain = CharacterChain(config)
        self.scene_chain = SceneChain(config)
        self.imagen = ImagenClient(config)
        self.state = GameState(
            affection=config.initial_affection,
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

    @staticmethod
    def _emit_progress(
        progress_cb: ProgressCallback | None,
        step: int,
        total: int,
        message: str,
    ) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(step, total, message)
        except Exception:
            log.debug("Progress callback failed", exc_info=True)

    def init_game(
        self,
        seed_string: str,
        *,
        progress_cb: ProgressCallback | None = None,
    ) -> SceneData:
        """Initialize a new game run from a seed string."""
        self._emit_progress(progress_cb, 1, 5, "解析种子")
        self.seed_hash = hash_seed(seed_string)
        trait_code = derive_trait_code(self.seed_hash)
        self.atmosphere = derive_initial_atmosphere(self.seed_hash)

        # Generate character
        self._emit_progress(progress_cb, 2, 5, "生成人设")
        try:
            self.character = self.character_chain.invoke(self.seed_hash, trait_code)
            log.info("Character generated: %s", self.character.name)
        except Exception:
            log.exception("Failed to generate character")
            self.character = CharacterProfile(
                name="???",
                personality="温柔而神秘，让人忍不住想要了解更多",
                speech_pattern="说话轻声细语，偶尔会害羞地低下头",
                visual_description="an attractive adult university student woman with long pink hair and blue eyes, casual stylish outfit, gentle smile",
            )

        # Generate sprite
        self._emit_progress(progress_cb, 3, 5, "生成角色立绘")
        try:
            self.character_sprite_path = self.imagen.generate_character_sprite(
                self.character.visual_description
            )
        except Exception:
            log.exception("Failed to generate character sprite")

        # Generate first scene
        self._emit_progress(progress_cb, 4, 5, "生成首个场景")
        scene = self.get_next_scene(progress_cb=progress_cb)
        self._emit_progress(progress_cb, 5, 5, "初始化完成")
        return scene

    def get_next_scene(
        self,
        player_choice: str = "",
        choice_delta: dict[str, int] | None = None,
        *,
        progress_cb: ProgressCallback | None = None,
    ) -> SceneData:
        """Generate the next scene, applying any choice effects."""
        self._emit_progress(progress_cb, 1, 6, "应用状态")
        if choice_delta:
            self.state.apply_delta(choice_delta)

        self.state.advance_round()
        random_event = roll_random_event(self.state.round_number, self.state.affection)

        self._emit_progress(progress_cb, 2, 6, "生成剧情")
        try:
            assert self.character is not None
            scene = self.scene_chain.invoke(
                character_profile=self.character,
                affection=self.state.affection,
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
        self._emit_progress(progress_cb, 3, 6, "整理状态")
        if scene.script:
            speakers = set(
                l.speaker for l in scene.script if l.speaker not in ("旁白", "系统")
            )
            summary = f"[场景{self.state.round_number}] {', '.join(speakers)} — {scene.script[0].text[:40]}"
            self.state.add_history(summary)

        # Generate main background (or CG)
        self._emit_progress(progress_cb, 4, 6, "生成主视觉")
        if scene.visual_type == VisualType.CINEMATIC_CG and scene.climax_cg_prompt:
            path = self._get_or_generate_bg(scene.climax_cg_prompt, is_cg=True)
            if path:
                scene.background = path
        elif scene.background:
            path = self._get_or_generate_bg(scene.background)
            if path:
                scene.background = path

        # Pre-generate transition backgrounds in background threads (non-blocking)
        self._emit_progress(progress_cb, 5, 6, "预取转场背景")
        self._generate_transition_bgs_async(scene)

        self.current_scene = scene
        self._emit_progress(progress_cb, 6, 6, "场景完成")
        return scene

    def _ending_scene(self) -> SceneData:
        return SceneData(
            scene_id="ending",
            background="beautiful sunset over school rooftop, warm golden light, cherry blossoms",
            script=[
                {
                    "speaker": "旁白",
                    "text": "这段故事，终于画上了句号。",
                    "inner_monologue": "夕阳的余晖洒落，心中满是温暖的回忆。",
                }
            ],
            choices=[
                {"text": "回到主菜单", "target_state_delta": {}},
            ],
            game_state_update={"is_climax": False, "is_ending": True},
        )
