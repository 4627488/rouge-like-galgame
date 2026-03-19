"""Gemini image client for image generation via google-genai SDK."""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from google import genai
from google.genai import types
from PIL import Image

from phantom_seed.ai.prompts.visual import (
    BACKGROUND_PROMPT_TEMPLATE,
    CG_PROMPT_TEMPLATE,
    VISUAL_PROMPT_TEMPLATE,
)

if TYPE_CHECKING:
    from phantom_seed.config import Config

log = logging.getLogger(__name__)


class ImagenClient:
    """Image generation via Gemini API using google-genai SDK."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.model = config.image_model
        self.cache_dir = config.cache_dir

    def _cache_path(self, prompt: str) -> Path:
        h = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.png"

    def _request_image(self, full_prompt: str) -> Image.Image | None:
        """Send one image generation request and return a PIL Image or None."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
            ),
        )

        if not response.candidates:
            log.warning("No candidates in image response")
            return None

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img = Image.open(io.BytesIO(part.inline_data.data))
                return img

        log.warning("No image part found in response")
        return None

    @staticmethod
    def _remove_white_bg(
        img: Image.Image, threshold: int = 240, tolerance: int = 30
    ) -> Image.Image:
        """Remove white/near-white background using corner flood-fill, returning RGBA image."""
        rgba = img.convert("RGBA")
        w, h = rgba.size
        pixels = rgba.load()

        # Determine background color by sampling the 4 corners
        corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
        bg_samples = [pixels[x, y][:3] for x, y in corners]
        # Use the most common corner color as background reference
        from collections import Counter

        bg_color = Counter(
            tuple(min(255, max(0, c)) for c in s) for s in bg_samples
        ).most_common(1)[0][0]

        # Only run removal if background is light (likely white)
        if not all(c >= threshold for c in bg_color):
            return rgba

        visited = [[False] * h for _ in range(w)]
        queue: list[tuple[int, int]] = list(corners)
        for cx, cy in corners:
            visited[cx][cy] = True

        while queue:
            x, y = queue.pop()
            r, g, b, a = pixels[x, y]
            # Is this pixel close to the background color?
            if (
                abs(r - bg_color[0]) <= tolerance
                and abs(g - bg_color[1]) <= tolerance
                and abs(b - bg_color[2]) <= tolerance
            ):
                pixels[x, y] = (r, g, b, 0)  # make transparent
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
                        visited[nx][ny] = True
                        queue.append((nx, ny))
        return rgba

    def generate_image(
        self,
        prompt: str,
        *,
        is_cg: bool = False,
        template: str | None = None,
    ) -> Path | None:
        """Generate an image and return its local path, or None on failure."""
        if template is None:
            template = CG_PROMPT_TEMPLATE if is_cg else VISUAL_PROMPT_TEMPLATE
        full_prompt = template.format(description=prompt)

        cached = self._cache_path(full_prompt)
        if cached.exists():
            log.debug("Cache hit: %s", cached)
            return cached

        try:
            img = self._request_image(full_prompt)
            if img:
                # For character sprites (not CG/background): remove white background
                if template is VISUAL_PROMPT_TEMPLATE:
                    img = self._remove_white_bg(img)
                    log.debug("White background removed from sprite")
                img.save(cached, "PNG")
                log.info("Generated image saved: %s", cached)
                return cached
            log.warning("No image in response for prompt: %s", full_prompt[:80])
        except Exception:
            log.exception("Image generation failed for prompt: %s", full_prompt[:80])

        return None

    def generate_character_sprite(self, visual_description: str) -> Path | None:
        return self.generate_image(visual_description, is_cg=False)

    def generate_background(self, description: str) -> Path | None:
        """Generate a background illustration."""
        return self.generate_image(
            description, template=BACKGROUND_PROMPT_TEMPLATE
        )

    def generate_cg(self, cg_prompt: str) -> Path | None:
        return self.generate_image(cg_prompt, is_cg=True)
