"""Prompt templates for AI generation."""

from phantom_seed.ai.prompts.character import CHARACTER_PROMPT
from phantom_seed.ai.prompts.scene import SCENE_PROMPT
from phantom_seed.ai.prompts.system import (
    CHARACTER_SYSTEM_MESSAGE,
    SYSTEM_MESSAGE,
)
from phantom_seed.ai.prompts.visual import (
    BACKGROUND_PROMPT_TEMPLATE,
    CG_PROMPT_TEMPLATE,
    VISUAL_PROMPT_TEMPLATE,
)

__all__ = [
    "BACKGROUND_PROMPT_TEMPLATE",
    "CG_PROMPT_TEMPLATE",
    "CHARACTER_PROMPT",
    "CHARACTER_SYSTEM_MESSAGE",
    "SCENE_PROMPT",
    "SYSTEM_MESSAGE",
    "VISUAL_PROMPT_TEMPLATE",
]
