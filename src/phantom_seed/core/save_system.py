"""Save / Load system for Phantom Seed.

Each save slot is a single JSON file stored in  <project_root>/.saves/
containing the *complete* reconstructible game state:
  - GameState (sanity, favor, round, history, memory_fragments)
  - CharacterProfile
  - All local asset paths (sprite + bg_cache)
  - Current SceneData + dialogue index
  - Full dialogue backlog
  - Small base64 thumbnail screenshot
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pygame

    from phantom_seed.core.coordinator import GameCoordinator

log = logging.getLogger(__name__)

SAVE_VERSION = "1.0"
SLOT_NAMES = ["QUICK", "1", "2", "3"]


@dataclass
class BacklogEntry:
    speaker: str
    text: str
    inner_monologue: str = ""
    scene_id: str = ""


@dataclass
class SaveData:
    version: str
    slot: str
    timestamp: str
    seed_hash: str
    atmosphere: str
    # GameState
    sanity: int
    favor: int
    round_number: int
    history: list[str]
    memory_fragments: list[str]
    is_ending: bool
    # Character
    character_data: dict[str, Any]
    character_sprite_path: str | None
    # Assets
    bg_cache: dict[str, str]
    # Scene
    current_scene_data: dict[str, Any] | None
    dialogue_index: int
    # Backlog of every line seen
    backlog: list[dict[str, str]]
    # Thumbnail (base64 PNG ~160×90)
    thumbnail_b64: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(text: str) -> SaveData:
        d = json.loads(text)
        return SaveData(**d)


class SaveSystem:
    """Manages serialisation and persistence of save slots."""

    def __init__(self, project_root: Path) -> None:
        self.save_dir = project_root / ".saves"
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, slot: str) -> Path:
        return self.save_dir / f"slot_{slot}.json"

    # ── Save ────────────────────────────────────────────────────

    def save(
        self,
        slot: str,
        coordinator: GameCoordinator,
        dialogue_index: int,
        backlog: list[BacklogEntry],
        screenshot: pygame.Surface | None = None,
    ) -> None:
        """Serialise the full game state to a slot file."""
        from phantom_seed.ai.protocol import SceneData

        st = coordinator.state
        char = coordinator.character

        thumbnail_b64: str | None = None
        if screenshot is not None:
            try:
                import pygame

                small = pygame.transform.smoothscale(screenshot, (240, 135))
                buf = io.BytesIO()
                pygame.image.save(small, buf, "PNG")
                thumbnail_b64 = base64.b64encode(buf.getvalue()).decode()
            except Exception:
                log.debug("Thumbnail capture failed", exc_info=True)

        current_scene = coordinator.current_scene
        save = SaveData(
            version=SAVE_VERSION,
            slot=slot,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            seed_hash=coordinator.seed_hash,
            atmosphere=coordinator.atmosphere,
            sanity=st.sanity,
            favor=st.favor,
            round_number=st.round_number,
            history=list(st.history),
            memory_fragments=list(st.memory_fragments),
            is_ending=st.is_ending,
            character_data=char.model_dump() if char else {},
            character_sprite_path=(
                str(coordinator.character_sprite_path)
                if coordinator.character_sprite_path
                else None
            ),
            bg_cache=dict(coordinator._bg_cache),
            current_scene_data=current_scene.model_dump() if current_scene else None,
            dialogue_index=dialogue_index,
            backlog=[asdict(e) for e in backlog],
            thumbnail_b64=thumbnail_b64,
        )

        path = self._slot_path(slot)
        path.write_text(save.to_json(), encoding="utf-8")
        log.info("Saved to slot %s: %s", slot, path)

    # ── Load ────────────────────────────────────────────────────

    def load(self, slot: str) -> SaveData | None:
        """Deserialise a save slot. Returns None if not found."""
        path = self._slot_path(slot)
        if not path.exists():
            log.warning("Save slot %s not found: %s", slot, path)
            return None
        try:
            return SaveData.from_json(path.read_text(encoding="utf-8"))
        except Exception:
            log.exception("Failed to load save slot %s", slot)
            return None

    def slot_info(self, slot: str) -> dict[str, str] | None:
        """Return lightweight info dict for displaying in the menu."""
        path = self._slot_path(slot)
        if not path.exists():
            return None
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return {
                "slot": slot,
                "timestamp": d.get("timestamp", ""),
                "round": str(d.get("round_number", 0)),
                "sanity": str(d.get("sanity", 0)),
                "favor": str(d.get("favor", 0)),
                "char": d.get("character_data", {}).get("name", "???"),
                "thumbnail_b64": d.get("thumbnail_b64") or "",
            }
        except Exception:
            return None

    def restore_coordinator(self, data: SaveData, coordinator: GameCoordinator) -> None:
        """Push all fields from SaveData back into a GameCoordinator."""
        from phantom_seed.ai.protocol import CharacterProfile, SceneData
        from phantom_seed.core.state import GameState

        # Restore state
        coordinator.seed_hash = data.seed_hash
        coordinator.atmosphere = data.atmosphere
        st = coordinator.state
        st.sanity = data.sanity
        st.favor = data.favor
        st.round_number = data.round_number
        st.history = list(data.history)
        st.memory_fragments = list(data.memory_fragments)
        st.is_ending = data.is_ending
        st.is_game_over = False

        # Restore character
        if data.character_data:
            coordinator.character = CharacterProfile.model_validate(data.character_data)
        coordinator.character_sprite_path = (
            Path(data.character_sprite_path) if data.character_sprite_path else None
        )

        # Restore bg cache
        import threading

        coordinator._bg_cache = dict(data.bg_cache)
        if not hasattr(coordinator, "_bg_lock") or coordinator._bg_lock is None:
            coordinator._bg_lock = threading.Lock()

        # Restore current scene
        if data.current_scene_data:
            coordinator.current_scene = SceneData.model_validate(
                data.current_scene_data
            )
