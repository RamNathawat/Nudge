import re
from typing import Dict, List
from .task_topic_inference import infer_task_topic
from .nlp_analysis import detect_emotion # Import detect_emotion

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

def infer_emotional_state(message: str) -> Dict[str, float]:
    """
    Infers emotional state from the message using the NLP model and assigns intensity.
    Returns a dictionary of emotions and their intensities.
    """
    emotion_label = detect_emotion(message)
    # This is a simplification; a real system might get scores for multiple emotions
    # from the NLP model. Here, we map the single detected emotion to an intensity.

    intensity_map = {
        "joy": {"joy": 0.9},
        "sadness": {"sadness": 0.8},
        "anger": {"anger": 0.9},
        "fear": {"fear": 0.7},
        "disgust": {"disgust": 0.6},
        "surprise": {"surprise": 0.6},
        "neutral": {"neutral": 0.3},
        "optimism": {"optimism": 0.7}, # Added from common emotion labels
        "love": {"love": 0.8},
        "embarrassment": {"embarrassment": 0.7},
        "remorse": {"remorse": 0.7},
        "grief": {"grief": 0.9},
        "anxiety": {"anxiety": 0.8},
        "guilt": {"guilt": 0.8},
        "frustration": {"frustration": 0.7},
        "boredom": {"boredom": 0.5},
        "exhaustion": {"exhaustion": 0.6}, # Custom mapping for exhaustion
        "stuck": {"stuck": 0.7}, # Custom mapping for stuck state
        "unknown": {"unknown": 0.2},
    }
    return intensity_map.get(emotion_label, {"neutral": 0.3})

def summary_emotions(emotions: Dict[str, float]) -> str:
    """
    Creates a human-readable summary of the inferred emotional state.
    """
    if not emotions:
        return "No specific emotions detected."

    # Find the most prominent emotion
    most_prominent_emotion = max(emotions, key=emotions.get)
    intensity = emotions[most_prominent_emotion]

    if most_prominent_emotion == "neutral" and intensity < 0.5:
        return "Your emotional state seems neutral."
    elif most_prominent_emotion in ["joy", "optimism", "love", "surprise"]:
        return f"You seem to be feeling {most_prominent_emotion} with intensity {intensity:.1f}."
    else: # Assume other emotions are typically negative or indicate a challenge
        return f"There are signs of {most_prominent_emotion} with intensity {intensity:.1f}."

def infer_user_state(message: str) -> Dict[str, str]:
    return {
        "intent": infer_from_keywords(message, INTENT_KEYWORDS),
        "substance": infer_from_keywords(message, SUBSTANCE_KEYWORDS),
        "task_topic": infer_task_topic(message)
    }