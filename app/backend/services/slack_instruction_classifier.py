from __future__ import annotations

import re
from typing import Any


class SlackInstructionClassifier:
    """Deterministic, no-cost routing before an AgentTask enters the shared queue."""

    CANCEL = {"cancel", "cancel current task", "cancel this task", "stop", "stop this", "stop this task"}

    def classify(self, instruction: str) -> dict[str, Any]:
        text = " ".join(instruction.strip().split())
        lower = text.lower().strip(" .!")
        if lower in self.CANCEL:
            return self._plan("cancel_task", 1.0)
        if re.fullmatch(r"(?:please\s+)?approve(?:\s+(?:it|this|the comic))?", lower):
            return self._plan("approve", 0.99)
        if re.fullmatch(r"(?:please\s+)?(?:pass|reject)(?:\s+(?:it|this|the comic))?", lower):
            return self._plan("pass", 0.99)
        if re.fullmatch(r"(?:please\s+)?(?:fix|repair)(?:\s+(?:it|this|the comic|the issues))?", lower):
            return self._plan("repair_comic", 0.95)
        if any(phrase in lower for phrase in ("what have you learned", "what did you learn", "what is waiting", "what are you working")):
            return self._plan("brain_query", 0.96)
        if any(phrase in lower for phrase in ("i like", "i love", "more like this", "remember that", "stop giving", "less of")):
            return self._plan("feedback", 0.94)
        if re.search(r"\b(concepts?|ideas?)\b", lower) and re.search(r"\b(make|create|generate|give|new)\b", lower):
            count = self._count(lower)
            return self._plan("generate_concepts", 0.97, {"requested_count": count} if count else {})

        pair = self._title_pair(text)
        comic_intent = bool(re.search(r"\b(comic|make|create|generate)\b", lower))
        if pair and comic_intent:
            left, right = pair
            return self._plan(
                "generate_comic",
                0.98,
                {
                    "left_title": left,
                    "right_title": right,
                    "format": "x_with_you",
                    "story_brief": self._story_brief(left, right),
                },
            )
        if pair:
            left, right = pair
            return self._plan(
                "generate_comic",
                0.94,
                {
                    "left_title": left,
                    "right_title": right,
                    "format": "x_with_you",
                    "story_brief": self._story_brief(left, right),
                },
            )
        if re.search(r"\b(comic|make|create|generate)\b", lower):
            return self._plan(
                "unknown",
                0.35,
                clarification="What ordinary moment should the comic compare with that same moment shared together?",
            )
        return self._plan("unknown", 0.2, clarification="Would you like a comic, new concepts, a repair, or a Brain update?")

    @staticmethod
    def _plan(task_type: str, confidence: float, context: dict[str, Any] | None = None, clarification: str | None = None) -> dict[str, Any]:
        return {"task_type": task_type, "confidence": confidence, "context": context or {}, "clarification": clarification}

    @classmethod
    def _title_pair(cls, text: str) -> tuple[str, str] | None:
        value = re.sub(r"\s+", " ", text.strip())
        value = re.sub(
            r"^(?:please\s+)?(?:create|make|generate)(?:\s+me)?(?:\s+(?:a|the))?(?:\s+comic)?(?:\s+(?:of|about|for))?\s+",
            "",
            value,
            flags=re.I,
        )
        value = re.sub(r"^the\s+", "", value, flags=re.I)
        value = re.sub(r"\s+one$", "", value, flags=re.I)
        match = re.match(
            r"^(?P<left>.+?)\s*(?:/|\bvs\.?\b|\bversus\b|\bcompared\s+to\b|\band\b)\s*(?P<right>.+?\s+with\s+you)\s*[.!?]*$",
            value,
            flags=re.I,
        )
        if match:
            left = cls._clean_title(match.group("left"))
            right = cls._clean_title(match.group("right"))
            return (left, right) if left and right else None
        # Story Library-style shorthand: “create the farmers market one”.
        if value and len(value.split()) <= 8 and not re.search(r"\b(comic|concept|idea)\b", value, flags=re.I):
            left = cls._clean_title(value)
            return (left, cls._clean_title(f"{value} with you"))
        return None

    @staticmethod
    def _clean_title(value: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9&' -]", "", value).strip(" -.")
        return f"{clean.upper()}." if clean else ""

    @staticmethod
    def _count(lower: str) -> int | None:
        digit = re.search(r"\b(\d{1,2})\b", lower)
        if digit:
            return max(1, min(int(digit.group(1)), 30))
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "thirty": 30}
        return next((count for word, count in words.items() if re.search(rf"\b{word}\b", lower)), None)

    @staticmethod
    def _story_brief(left: str, right: str) -> dict[str, Any]:
        activity = left.rstrip(".").lower()
        gerund = activity.split()[0].endswith("ing") if activity else False
        left_action = f"Dinko is {activity} alone." if gerund else f"Dinko has {activity} alone."
        right_action = f"Dinko and Dinka are {activity} together." if gerund else f"Dinko and Dinka share {activity} together."
        setting, props = SlackInstructionClassifier._scene(activity)
        return {
            "format": "x-with-you",
            "title_left": left,
            "title_right": right,
            "left_character": "boy",
            "left_action": left_action,
            "left_setting": setting,
            "left_props": props[:2],
            "left_emotion": "Neutral, bored, or gently sad—never happy.",
            "right_characters": ["boy", "girl"],
            "right_action": right_action,
            "right_setting": f"the same {setting}",
            "right_props": props,
            "right_emotion": "Warm, playful, and connected because the ordinary moment is shared.",
            "shared_environment": f"One continuous pastel background across both panels in the same {setting}.",
            "environmental_contrast": "The activity stays ordinary; companionship changes the feeling.",
            "background_color": "warm cream",
            "accent_color": "muted terracotta",
            "camera_angle": "medium straight-on",
            "execution_risks": ["Keep both characters equal size and all props subordinate to them."],
            "emotional_insight": f"{activity.capitalize()} feels better when it is shared with your person.",
        }

    @staticmethod
    def _scene(activity: str) -> tuple[str, list[str]]:
        if "wing" in activity:
            return "simple rounded casual dining nook", ["rounded table", "two chairs", "basket of wings", "napkin holder"]
        if "coffee" in activity:
            return "simple rounded cafe nook", ["small cafe table", "two chairs", "coffee machine", "proportional mugs"]
        if "shopping" in activity:
            return "minimal rounded shop aisle", ["low product shelf", "shopping basket", "checkout counter"]
        if "farmers market" in activity:
            return "minimal outdoor market stall", ["wooden produce stand", "two market baskets", "small canopy"]
        if "party" in activity:
            return "simple rounded living room party scene", ["snack table", "two chairs", "small speaker"]
        return "simple rounded everyday setting", ["small table", "two chairs", "one activity-specific prop"]
