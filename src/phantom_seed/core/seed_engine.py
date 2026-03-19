"""Seed DNA engine — converts a player seed into initial game parameters."""

from __future__ import annotations

import hashlib


def hash_seed(seed_string: str) -> str:
    """Convert a player-entered string into a deterministic hex hash."""
    return hashlib.sha256(seed_string.encode("utf-8")).hexdigest()


def derive_trait_code(seed_hash: str) -> str:
    """Extract a personality archetype from the seed hash."""
    segment = int(seed_hash[:8], 16)
    archetypes = [
        "COOL",  # 冷酷系
        "YANDERE",  # 病娇系
        "GENKI",  # 元气系
        "KUUDERE",  # 酷系
        "MYSTERIOUS",  # 神秘系
        "GENTLE",  # 温柔系
        "TSUNDERE",  # 傲娇系
        "DANDERE",  # 内向害羞系
    ]
    return archetypes[segment % len(archetypes)]


def derive_initial_atmosphere(seed_hash: str) -> str:
    """Derive the starting atmosphere/setting from the seed."""
    segment = int(seed_hash[8:16], 16)
    settings = [
        "cherry_blossom_campus",
        "sunny_classroom",
        "rooftop_at_sunset",
        "seaside_town",
        "school_library",
        "summer_festival",
        "train_station_platform",
        "quiet_cafe",
    ]
    return settings[segment % len(settings)]
