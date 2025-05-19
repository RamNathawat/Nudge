import re

# Sample keywords for inference (can be replaced with NLP model later)
MOOD_KEYWORDS = {
    "happy": ["great", "happy", "awesome", "excited", "joyful", "love"],
    "sad": ["sad", "depressed", "down", "lonely", "miserable"],
    "angry": ["angry", "mad", "furious", "pissed", "annoyed"],
    "anxious": ["anxious", "worried", "stressed", "nervous"],
    "neutral": ["okay", "fine", "meh", "alright"],
}

ENERGY_KEYWORDS = {
    "high": ["energized", "hyped", "buzzing", "motivated"],
    "low": ["tired", "exhausted", "sleepy", "drained", "lethargic"],
    "moderate": ["normal", "balanced", "calm"]
}

INTENT_KEYWORDS = {
    "productive": ["focus", "work", "study", "grind", "create"],
    "avoidant": ["avoid", "skip", "postpone", "later"],
    "recreational": ["chill", "watch", "relax", "vibe"]
}

SUBSTANCE_KEYWORDS = {
    "weed": ["high", "stoned", "blazed", "420"],
    "alcohol": ["drunk", "buzzed", "wasted"],
    "nicotine": ["smoked", "vape", "cigarette"],
}


def infer_from_keywords(text: str, keyword_dict: dict, default: str):
    text = text.lower()
    for category, keywords in keyword_dict.items():
        if any(re.search(rf"\b{kw}\b", text) for kw in keywords):
            return category
    return default


def infer_emotional_state(message: str) -> dict:
    return {
        "mood": infer_from_keywords(message, MOOD_KEYWORDS, "neutral"),
        "energy": infer_from_keywords(message, ENERGY_KEYWORDS, "moderate"),
        "intent": infer_from_keywords(message, INTENT_KEYWORDS, "productive"),
        "substance": infer_from_keywords(message, SUBSTANCE_KEYWORDS, None),
    }


def summary_emotions(emotions: dict) -> str:
    summary = []
    for trait, value in emotions.items():
        if value:
            summary.append(f"{trait}: {value}")
    return " | ".join(summary)


