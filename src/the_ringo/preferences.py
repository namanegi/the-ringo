from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class LearnerPreferences:
    daily_items: int = 10
    new_content_ratio: float = 0.25
    explanation_style: str = "concise"

    def __post_init__(self) -> None:
        if isinstance(self.daily_items, bool) or not isinstance(self.daily_items, int):
            raise ValueError("daily_items must be an integer")
        if not 1 <= self.daily_items <= 100:
            raise ValueError("daily_items must be between 1 and 100")
        if isinstance(self.new_content_ratio, bool) or not isinstance(
            self.new_content_ratio, (int, float)
        ):
            raise ValueError("new_content_ratio must be a number")
        if not isfinite(self.new_content_ratio):
            raise ValueError("new_content_ratio must be finite")
        if not 0 <= self.new_content_ratio <= 1:
            raise ValueError("new_content_ratio must be between 0 and 1")
        if not isinstance(self.explanation_style, str):
            raise ValueError("explanation_style must be text")
        explanation_style = self.explanation_style.strip()
        if not explanation_style:
            raise ValueError("explanation_style must not be empty")
        if len(explanation_style) > 120:
            raise ValueError("explanation_style must be at most 120 characters")
        object.__setattr__(self, "explanation_style", explanation_style)
