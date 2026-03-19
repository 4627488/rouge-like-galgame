"""Game state management."""

from __future__ import annotations

from dataclasses import dataclass, field

# Chapter beats — romance narrative arc
CHAPTER_BEATS = [
    "序章·邂逅（命运般的相遇，建立第一印象）",
    "第一幕·接近（日常互动增多，逐渐熟悉彼此）",
    "第二幕·心动（不经意间的心跳加速，暧昧的气氛）",
    "第三幕·波澜（误会或小冲突，考验两人的关系）",
    "第四幕·坦诚（敞开心扉，分享内心深处的想法）",
    "第五幕·告白（鼓起勇气表达心意，命运的抉择）",
    "终章·结局（故事走向各自的结局）",
]


@dataclass
class GameState:
    """Tracks all mutable game state for the current run."""

    affection: int = 0
    round_number: int = 0
    history: list[str] = field(default_factory=list)
    memory_fragments: list[str] = field(default_factory=list)  # meta-progression
    is_ending: bool = False

    @property
    def chapter_beat(self) -> str:
        idx = min(self.round_number, len(CHAPTER_BEATS) - 1)
        return CHAPTER_BEATS[idx]

    def apply_delta(self, delta: dict[str, int]) -> None:
        """Apply stat changes from a choice."""
        self.affection = max(0, min(100, self.affection + delta.get("affection", 0)))

    def advance_round(self) -> None:
        self.round_number += 1

    def add_history(self, summary: str) -> None:
        self.history.append(summary)
        # Keep history compact — only last 15 entries
        if len(self.history) > 15:
            self.history = self.history[-15:]

    def get_history_summary(self) -> str:
        if not self.history:
            return "这是故事的开始，一切从零开始。"
        return "\n".join(f"- {h}" for h in self.history)

    def reset_for_new_run(self) -> None:
        """Reset for a new run, keeping meta-progression."""
        fragments = self.memory_fragments.copy()
        self.affection = 0
        self.round_number = 0
        self.history.clear()
        self.is_ending = False
        self.memory_fragments = fragments
