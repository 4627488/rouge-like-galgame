"""SceneData generation chain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phantom_seed.ai.llm import create_llm
from phantom_seed.ai.prompts.scene import SCENE_PROMPT
from phantom_seed.ai.protocol import CharacterProfile, SceneData

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class SceneChain:
    """Generates a SceneData segment via LangChain LCEL."""

    def __init__(self, config: Config) -> None:
        llm = create_llm(config)
        structured_llm = llm.with_structured_output(
            SceneData, method="json_mode"
        )
        self._chain = (SCENE_PROMPT | structured_llm).with_retry(
            stop_after_attempt=2, wait_exponential_jitter=True
        )

    def invoke(
        self,
        character_profile: CharacterProfile,
        affection: int,
        round_number: int,
        history_summary: str,
        last_choice: str,
        random_event: str,
        chapter_beat: str = "",
    ) -> SceneData:
        """Generate the next scene segment."""
        result = self._chain.invoke({
            "character_profile": character_profile.model_dump_json(indent=2),
            "affection": str(affection),
            "round_number": str(round_number),
            "chapter_beat": chapter_beat or "序章·邂逅",
            "history_summary": history_summary or "这是故事的开始，一切从零开始。",
            "last_choice": last_choice or "（无）",
            "random_event": random_event or "（无特殊事件）",
        })
        log.info("Scene generated: %s", result.scene_id)
        return result
