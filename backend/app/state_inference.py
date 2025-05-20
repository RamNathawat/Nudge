import re
from typing import Dict
from app.task_topic_inference import infer_task_topic

INTENT_KEYWORDS = {
    "productive": ["build", "create", "focus", "learn", "improve", "study"],
    "avoidant": ["skip", "delay", "procrastinate", "later"],
    "recreational": ["relax", "chill", "watch", "hangout"]
}

SUBSTANCE_KEYWORDS = {
    "weed": ["high", "stoned", "smoke weed"],
    "alcohol": ["drunk", "booze", "wine", "beer"],
    "nicotine": ["cigarette", "vape", "nicotine", "smoke"]
}

def infer_from_keywords(text: str, keyword_map: Dict[str, list], default: str = "unknown") -> str:
    text = text.lower()
    for category, keywords in keyword_map.items():
        if any(re.search(rf"\b{kw}\b", text) for kw in keywords):
            return category
    return default

def infer_emotional_state() -> Dict[str, str]:
    return {
        "calm": "Your tone seems relaxed and neutral.",
        "stressed": "You sound overwhelmed or agitated.",
        "motivated": "You're clearly ready to take action.",
        "apathetic": "You don't seem too interested in doing much.",
        "anxious": "You're overthinking or unsure about something."
    }

def infer_user_state(message: str) -> Dict[str, str]:
    return {
        "intent": infer_from_keywords(message, INTENT_KEYWORDS),
        "substance": infer_from_keywords(message, SUBSTANCE_KEYWORDS),
        "task_topic": infer_task_topic(message)
    }