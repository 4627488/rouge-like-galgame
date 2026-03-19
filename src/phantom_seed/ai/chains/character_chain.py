"""CharacterProfile generation chain."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from phantom_seed.ai.llm import create_llm
from phantom_seed.ai.prompts.character import CHARACTER_PROMPT
from phantom_seed.ai.protocol import CharacterProfile

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class CharacterChain:
    """Generates a CharacterProfile from a seed via LangChain LCEL."""

    def __init__(self, config: Config) -> None:
        llm = create_llm(config)
        structured_llm = llm.with_structured_output(
            CharacterProfile, method="json_mode"
        )
        self._chain = (CHARACTER_PROMPT | structured_llm).with_retry(
            stop_after_attempt=3, wait_exponential_jitter=True
        )

    def invoke(self, seed_hash: str, trait_code: str) -> CharacterProfile:
        """Generate a character profile from seed parameters."""
        result = self._chain.invoke({
            "seed_hash": seed_hash,
            "trait_code": trait_code,
        })
        log.info("Character generated: %s", result.name)
        return result
