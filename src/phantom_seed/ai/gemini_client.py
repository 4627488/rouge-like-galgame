"""OpenRouter text client for story generation (OpenAI-compatible)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from openai import OpenAI

from phantom_seed.ai.prompts import (
    CHARACTER_INIT_PROMPT,
    SCENE_GENERATION_PROMPT,
    SYSTEM_PROMPT,
)
from phantom_seed.ai.protocol import CharacterProfile, SceneData

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class GeminiClient:
    """Text generation via OpenRouter (OpenAI-compatible)."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = OpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key,
        )
        self.model = config.text_model

    def _generate(self, prompt: str, system: str = SYSTEM_PROMPT) -> str:
        """Send a prompt to OpenRouter and return raw text."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.95,
            max_tokens=8192,
            extra_headers={"HTTP-Referer": "https://phantom-seed.game"},
        )
        return response.choices[0].message.content or ""

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from model response, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        return json.loads(text)

    def generate_character(self, seed_hash: str, trait_code: str) -> CharacterProfile:
        """Generate a character profile from a seed."""
        prompt = CHARACTER_INIT_PROMPT.format(
            seed_hash=seed_hash,
            trait_code=trait_code,
        )
        raw = self._generate(
            prompt, system="你是一个角色设计师。请严格按照 JSON 格式输出角色档案。"
        )
        data = self._extract_json(raw)
        return CharacterProfile.model_validate(data)

    def generate_scene(
        self,
        character_profile: CharacterProfile,
        sanity: int,
        favor: int,
        round_number: int,
        history_summary: str,
        last_choice: str,
        random_event: str,
        chapter_beat: str = "",
    ) -> SceneData:
        """Generate the next scene segment."""
        prompt = SCENE_GENERATION_PROMPT.format(
            character_profile=character_profile.model_dump_json(indent=2),
            sanity=sanity,
            favor=favor,
            round_number=round_number,
            history_summary=history_summary or "这是故事的开始，一切从零开始。",
            last_choice=last_choice or "（无）",
            random_event=random_event or "（无特殊事件）",
            chapter_beat=chapter_beat or "序章·相遇",
        )
        raw = self._generate(prompt)
        data = self._extract_json(raw)
        return SceneData.model_validate(data)
