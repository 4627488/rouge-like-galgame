"""Romance event mechanics — random encounters and memory fragments."""

from __future__ import annotations

import random


# Random romance encounters injected into scene generation
RANDOM_EVENTS = [
    "突然下起了小雨，只有一把伞。",
    "在自动贩卖机前偶遇，两人同时按了同一个按钮。",
    "对方带了两份便当，害羞地递过来一份。",
    "放学后一起值日，阳光从窗户洒进来。",
    "在图书馆不小心碰到了对方的手。",
    "体育课后在走廊偶遇，对方递来一瓶冰水。",
    "放学路上看到了很美的夕阳。",
    "学园祭的准备工作中，两人被分到了同一组。",
    "在天台上发现了对方一个人在看风景。",
    "下课铃响后，对方在教室门口等着你。",
]


def roll_random_event(round_number: int, affection: int) -> str:
    """Roll for a random romance encounter.

    Higher rounds and higher affection increase event probability.
    """
    base_chance = 0.2
    affection_bonus = affection / 400  # up to +0.25 at affection=100
    round_bonus = min(round_number * 0.02, 0.15)  # up to +0.15

    if random.random() < base_chance + affection_bonus + round_bonus:
        return random.choice(RANDOM_EVENTS)
    return ""


def generate_memory_fragment(history: list[str], round_number: int) -> str:
    """Generate a memory fragment for meta-progression."""
    if not history:
        return f"第{round_number}幕：一段朦胧的回忆，温暖而模糊。"
    last = history[-1] if history else ""
    return f"第{round_number}幕的记忆：{last[:50]}..."
