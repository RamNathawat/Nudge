import re
from typing import Dict, List
from .nlp_analysis import detect_emotion
from .memory import update_trait, get_traits, get_recent_history
from .task_topic_inference import infer_task_topic
import json
from transformers import pipeline
from app.user_profile_inference import update_user_profile

# ------------------------------------
# Emotion & Intent Keyword Maps
# ------------------------------------

INTENT_KEYWORDS = {
    "productive": ["build", "create", "focus", "learn", "improve", "study", "work", "finish", "complete"],
    "avoidant": ["skip", "delay", "procrastinate", "later", "lazy", "put off", "not now", "ignore"],
    "recreational": ["relax", "chill", "watch", "hangout", "movie", "game", "fun", "entertain"]
}

SUBSTANCE_KEYWORDS = {
    "weed": ["high", "stoned", "smoke weed", "blunt", "joint", "smoke up"],
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
# Utility: JSON-safe serializer
# ------------------------------------

def serialize_for_json(obj):
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (str, int, float, type(None))):
        return obj
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return str(obj)

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

emotion_classifier = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=None)

def infer_emotional_state(text: str, user_id: str = None) -> Dict[str, float]:
    try:
        output = emotion_classifier(text)
        scores = {item['label'].lower(): item['score'] for item in output[0]}
    except Exception as e:
        print(f"[Emotion Detection Error]: {e}")
        return {"unknown": 1.0}

    # Update user traits if user_id is provided
    if user_id:
        for emotion, score in scores.items():
            trait_name = f"emotion_{emotion}_count"
            existing = get_traits(user_id).get(trait_name, 0)
            update_trait(user_id, trait_name, existing + 1)
            update_trait(user_id, emotion, EMOTION_INTENSITY_MAP.get(emotion, 0.3))

    return scores

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
    from .behaviour_analyzer import analyze_behavior

    flags = analyze_behavior(user_id, message)
    update_user_profile(user_id, message)
    emotions = infer_emotional_state(message, user_id)
    emotion_summary = summary_emotions(emotions)
    traits = get_traits(user_id)
    recent_history = get_recent_history(user_id)[-5:]  # Last 5 messages

    user_name = traits.get("user_name", "user")
    interests = [k.replace("interest_", "") for k, v in traits.items() if k.startswith("interest_") and v]

    personalization = (
        f"User Name: {user_name}\n"
        f"Interests: {', '.join(interests) if interests else 'Not enough data yet'}\n"
        f"Emotional State Summary: {emotion_summary}\n"
        f"Behavioral Flags: {flags}\n"
        f"Recent History: {json.dumps(serialize_for_json(recent_history))}\n"
        f"Full Traits Snapshot: {json.dumps(serialize_for_json(traits))}"
    )

    return personalization, flags, emotions
