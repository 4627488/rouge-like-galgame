"""Configuration and settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env file from project root into os.environ."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


# Load .env on import
_load_dotenv()


@dataclass
class Config:
    """Global configuration for Phantom Seed."""

    # Paths
    project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )
    assets_dir: Path = field(init=False)
    cache_dir: Path = field(init=False)

    # Window
    screen_width: int = 1280
    screen_height: int = 720
    fps: int = 60
    title: str = "Phantom Seed"

    # Gemini API
    gemini_api_key: str = field(
        default_factory=lambda: os.environ.get("GEMINI_API_KEY", "")
    )
    text_model: str = "gemini-3.1-pro-preview"
    image_model: str = "gemini-3.1-flash-image-preview"

    # Game defaults
    initial_affection: int = 0

    # Generation
    prefetch_count: int = 1
    generation_timeout: float = 30.0

    # Settings (user-configurable, persisted to settings.json)
    text_speed_ms: int = 30
    auto_play_ms: int = 1500
    fullscreen: bool = False

    def __post_init__(self) -> None:
        self.assets_dir = self.project_root / "assets"
        self.cache_dir = self.project_root / ".cache" / "images"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.load_settings()

    @property
    def _settings_path(self) -> Path:
        return self.project_root / "settings.json"

    def save_settings(self) -> None:
        """Persist user-configurable settings to settings.json."""
        data = {
            "text_speed_ms": self.text_speed_ms,
            "auto_play_ms": self.auto_play_ms,
            "fullscreen": self.fullscreen,
        }
        self._settings_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_settings(self) -> None:
        """Load user settings from settings.json if it exists."""
        if not self._settings_path.exists():
            return
        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            if "text_speed_ms" in data:
                self.text_speed_ms = int(data["text_speed_ms"])
            if "auto_play_ms" in data:
                self.auto_play_ms = int(data["auto_play_ms"])
            if "fullscreen" in data:
                self.fullscreen = bool(data["fullscreen"])
        except Exception:
            pass  # ignore corrupt settings
