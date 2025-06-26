import re
from typing import Dict

def infer_task_topic(text: str) -> str:
    """
    Infer the user's current task or topic area from text.
    Supports broader slang, synonyms, and casual language patterns.
    """
    lower = text.lower()

    topic_patterns = {
        "health": [
            r"\b(gym|workout|work out|fitness|diet|calorie|body|exercise|run|cardio|lift|training)\b"
        ],
        "finance": [
            r"\b(money|spend|saving|save|budget|income|salary|paycheck|debt|bills|invest)\b"
        ],
        "career": [
            r"\b(project|code|coding|build|app|website|startup|deploy|feature|job|work|deliverable|launch)\b"
        ],
        "relationship": [
            r"\b(relationship|crush|girlfriend|boyfriend|talk to|texting|love|feelings|date|romantic)\b"
        ],
        "education": [
            r"\b(study|exam|assignment|homework|college|test|school|lecture|revision|syllabus)\b"
        ],
        "creative": [
            r"\b(write|draw|paint|music|song|creative|design|art|poem|lyrics|sketch)\b"
        ],
        "chores": [
            r"\b(clean|dishes|laundry|groceries|housework|organize|cook|shopping)\b"
        ],
    }

    for topic, patterns in topic_patterns.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                return topic

    return "unknown"

def infer_user_state(text: str) -> Dict[str, str]:
    """
    Infer user intent, substance usage, and task topic from text.
    Uses loose matching for casual language.
    """

    lower = text.lower()

    # Substance Use Detection
    substance = "none"
    if any(kw in lower for kw in ["weed", "joint", "high", "stoned", "blunt", "pot"]):
        substance = "weed"
    elif any(kw in lower for kw in ["alcohol", "drunk", "booze", "beer", "vodka", "whiskey", "wine", "shots"]):
        substance = "alcohol"
    elif any(kw in lower for kw in ["cigarette", "nicotine", "smoke", "vape", "puff", "hookah"]):
        substance = "nicotine"

    # Intent Detection
    intent = "unknown"
    if any(kw in lower for kw in ["procrastinate", "delay", "skip", "avoid", "put off", "later", "postpone"]):
        intent = "avoidant"
    elif any(kw in lower for kw in ["finish", "complete", "get done", "start working", "begin", "knock this out", "focus", "grind"]):
        intent = "productive"
    elif any(kw in lower for kw in ["chill", "relax", "watch", "binge", "game", "movie", "hangout", "scroll", "waste time"]):
        intent = "recreational"

    return {
        "intent": intent,
        "substance": substance,
        "task_topic": infer_task_topic(text)
    }
