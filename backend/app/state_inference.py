import re
from typing import Dict, List
from .nlp_analysis import detect_emotion
from .memory import update_trait, get_traits, get_recent_history
from .task_topic_inference import infer_task_topic
import json

# ------------------------------------
# Emotion & Intent Keyword Maps
# ------------------------------------

INTENT_KEYWORDS = {
    "productive": ["build", "create", "focus", "learn", "improve", "study", "work", "finish", "complete"],
    "avoidant": ["skip", "delay", "procrastinate", "later", "lazy", "put off", "not now", "ignore"],
    "recreational": ["relax", "chill", "watch", "hangout", "movie", "game", "fun", "entertain"]
}

SUBSTANCE_KEYWORDS = {
    "weed": ["high", "stoned", "smoke weed", "blunt", "joint"],
    "alcohol": ["drunk", "booze", "wine", "beer", "vodka"],
    "nicotine": ["cigarette", "vape", "nicotine", "smoke"]
}

EMOTION_INTENSITY_MAP = {
    "joy": 0.9,
    "sadness": 0.8,
    "anger": 0.9,
    "fear": 0.7,
    "disgust": 0.6,
    "surprise": 0.6,
    "neutral": 0.3,
    "optimism": 0.7,
    "love": 0.8,
    "embarrassment": 0.7,
    "remorse": 0.7,
    "grief": 0.9,
    "anxiety": 0.8,
    "guilt": 0.8,
    "frustration": 0.7,
    "boredom": 0.5,
    "exhaustion": 0.6,
    "stuck": 0.7,
    "unknown": 0.2,
}

# ------------------------------------
# Keyword-Based State Detection
# ------------------------------------

def infer_from_keywords(text: str, keyword_map: Dict[str, list], default: str = "unknown") -> str:
    text = text.lower()
    for category, keywords in keyword_map.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords):
            return category
    return default

# ------------------------------------
# Emotion Detection + Trait Update
# ------------------------------------

def infer_emotional_state(message: str, user_id: str = None) -> Dict[str, float]:
    emotion_label = detect_emotion(message)
    intensity = EMOTION_INTENSITY_MAP.get(emotion_label, 0.3)

    # ✅ Optional: Track running emotional trends for the user
    if user_id and emotion_label != "unknown":
        trait_name = f"emotion_{emotion_label}_count"
        existing = get_traits(user_id).get(trait_name, 0)
        update_trait(user_id, trait_name, existing + 1)
        update_trait(user_id, emotion_label, intensity)

    return {emotion_label: intensity}

# ------------------------------------
# Human-Like Emotion Summary
# ------------------------------------

def summary_emotions(emotions: Dict[str, float]) -> str:
    if not emotions:
        return "No clear emotional signals detected."

    dominant = max(emotions, key=emotions.get)
    score = emotions[dominant]

    tone = {
        "joy": "You're sounding upbeat.",
        "anger": "There’s frustration in your tone.",
        "sadness": "You seem down.",
        "fear": "There's anxiety in your words.",
        "guilt": "You sound regretful.",
        "boredom": "You seem disinterested.",
        "optimism": "You're sounding hopeful.",
        "exhaustion": "You seem tired.",
        "unknown": "Your mood's a bit unclear.",
    }

    return tone.get(dominant, f"Emotion detected: {dominant} ({score:.1f})")

# ------------------------------------
# User Intent + Topic Summary
# ------------------------------------

def infer_user_state(message: str) -> Dict[str, str]:
    return {
        "intent": infer_from_keywords(message, INTENT_KEYWORDS),
        "substance": infer_from_keywords(message, SUBSTANCE_KEYWORDS),
        "task_topic": infer_task_topic(message)
    }

# ------------------------------------
# Full Context Injection for Gemini
# ------------------------------------

def inject_context(message: str, user_id: str):
    from .behaviour_analyzer import analyze_behavior  # Lazy import
    flags = analyze_behavior(user_id, message)
    emotions = infer_emotional_state(message, user_id)
    emotion_summary = summary_emotions(emotions)
    recent_history = get_recent_history(user_id)
    traits = get_traits(user_id)

    # ✅ Generate a cleaner, LLM-readable context string:
    context_str = (
        f"User Emotional State: {emotion_summary}\n"
        f"User Traits: {json.dumps(traits)}\n"
        f"Recent History Snippets: {json.dumps(recent_history[-5:])}\n"
        f"Behavioral Flags: {flags}"
    )

    return context_str, flags, emotions
