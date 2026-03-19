"""Visual prompt templates for image generation (plain strings, not LangChain)."""

VISUAL_PROMPT_TEMPLATE = """\
ONE SINGLE ILLUSTRATION, ONE COMPLETE GIRL ONLY. anime style, beautiful adult woman, full body, \
standing pose facing front, neutral expression, {description}, \
pure white background, no bg elements, NO CHARACTER SHEETS, NO VARIATIONS, NO OTHER PEOPLE, \
NO MULTIPLE POSES, NO MULTIPLE EXPRESSIONS, NO GRID LAYOUT, SINGLE IMAGE ONLY,\
high quality line art, soft lighting, pastel colors\
"""

CG_PROMPT_TEMPLATE = """\
anime style CG illustration, beautiful adult woman, {description}, \
warm lighting, cinematic composition, \
high detail, emotional scene, visual novel style, pastel tones\
"""

BACKGROUND_PROMPT_TEMPLATE = """\
anime visual novel background illustration, no characters, no people, {description}, \
detailed environment art, warm lighting, soft colors, inviting atmosphere, \
painterly style, high quality background art\
"""
