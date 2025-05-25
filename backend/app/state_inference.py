import re
import time
import json
from datetime import datetime
from typing import Dict, List, Tuple, Union

from .task_topic_inference import infer_task_topic
from .nlp_analysis import detect_emotion

# Keyword maps
INTENT_KEYWORDS = {
    "productive": ["build", "create", "focus", "learn", "improve", "study", "work"],
    "avoidant": ["skip", "delay", "procrastinate", "later", "avoid"],
    "recreational": ["relax", "chill", "watch", "hangout", "game"],
    "health": ["exercise", "yoga", "meditate", "sleep", "rest"]
}

SUBSTANCE_KEYWORDS = {
    "weed": ["high", "stoned", "smoke weed", "cannabis", "THC"],
    "alcohol": ["drunk", "booze", "wine", "beer", "cocktail"],
    "nicotine": ["cigarette", "vape", "nicotine", "smoke", "juul"],
    "caffeine": ["coffee", "energy drink", "caffeine", "espresso"]
}

EMOTION_INTENSITY_MAP = {
    "excitement": 0.9,
    "anxiety": 0.85,
    "frustration": 0.8,
    "overwhelm": 0.9,
    "boredom": 0.7,
    "contentment": 0.75,
    "neutral": 0.3,
    "fatigue": 0.8,
    "self_doubt": 0.85,
    "optimism": 0.75
}

EMOTION_ADVICE = {
    "overwhelm": "Consider breaking tasks into smaller steps.",
    "fatigue": "You might benefit from a short break.",
    "self_doubt": "Try writing down a recent win or progress you made.",
    "anxiety": "Try taking 3 deep breaths and focusing on just one step at a time."
}

MEMORY_FILE = "user_memory.json"


def infer_from_keywords(text: str, keyword_map: Dict[str, List[str]]) -> List[Tuple[str, float]]:
    text = text.lower()
    matches = []
    for category, keywords in keyword_map.items():
        count = sum(bool(re.search(rf"\b{re.escape(kw)}\b", text)) for kw in keywords)
        if count > 0:
            strength = round(count / len(keywords), 2)
            matches.append((category, strength))
    return sorted(matches, key=lambda x: x[1], reverse=True)


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

def analyze_emotions(message: str) -> Tuple[Dict[str, float], str]:
    emotion_label, confidence = detect_emotion(message)
    base_intensity = EMOTION_INTENSITY_MAP.get(emotion_label, 0.5)
    intensity = min(max(base_intensity * (confidence / 0.8), 0.1), 1.0)
    emotions = {emotion_label: round(intensity, 2)}

    summary = (
        f"Strong {emotion_label} detected ({intensity * 100:.0f}% intensity)"
        if intensity > 0.7 else
        f"Moderate {emotion_label} present ({intensity * 100:.0f}% intensity)"
        if intensity > 0.4 else
        "Relatively neutral emotional state"
    )

    if emotion_label in EMOTION_ADVICE and intensity > 0.6:
        summary += f" {EMOTION_ADVICE[emotion_label]}"

    return emotions, summary

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
    
def estimate_complexity(message: str) -> str:
    word_count = len(message.split())
    if word_count > 15:
        return "high"
    if any(kw in message.lower() for kw in ["project", "build", "create", "setup", "integrate"]):
        return "medium"
    return "low"


def estimate_salience(message: str) -> float:
    keywords = ["important", "urgent", "must", "need", "critical"]
    hits = sum(kw in message.lower() for kw in keywords)
    return round(min(1.0, 0.3 + 0.15 * hits), 2)


def tag_message(data: Dict) -> List[str]:
    tags = []
    intent = data["intent"]["primary"]
    if intent != "none":
        tags.append(f"intent:{intent}")

    substance = data["substance"]["type"]
    if substance != "none":
        tags.append(f"substance:{substance}")

    emotion = data["emotions"]["primary_emotion"]
    tags.append(f"emotional_state:{emotion}")

    if data["task"]["salience"] > 0.75:
        tags.append("high_salience")

    tags.append(f"task_topic:{data['task']['topic']}")
    return tags


def save_to_memory(message: str, tags: List[str]):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "tags": tags
    }

    try:
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        memory = []

    memory.append(entry)
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def infer_user_state(message: str) -> Dict[str, Union[str, dict]]:
    start_time = time.time()

    intent_matches = infer_from_keywords(message, INTENT_KEYWORDS)
    substance_matches = infer_from_keywords(message, SUBSTANCE_KEYWORDS)

    intent = intent_matches[0][0] if intent_matches else "none"
    substance = substance_matches[0][0] if substance_matches else "none"

    emotion_scores, emotion_summary = analyze_emotions(message)
    primary_emotion = max(emotion_scores, key=emotion_scores.get)

    substance_context = "neutral"
    if substance != "none":
        if intent == "productive":
            substance_context = "using_substance_to_focus"
        elif intent == "recreational":
            substance_context = "enhancing_leisure"

    task_topic = infer_task_topic(message)
    complexity = estimate_complexity(message)
    salience = estimate_salience(message)

    result = {
        "intent": {
            "primary": intent,
            "alternatives": [i for i, _ in intent_matches[1:]],
            "confidence": round(intent_matches[0][1], 2) if intent_matches else 0.0
        },
        "substance": {
            "type": substance,
            "alternatives": [s for s, _ in substance_matches[1:]],
            "context": substance_context
        },
        "task": {
            "topic": task_topic,
            "complexity": complexity,
            "salience": salience
        },
        "emotions": {
            "scores": emotion_scores,
            "summary": emotion_summary,
            "primary_emotion": primary_emotion
        },
        "metadata": {
            "message_length": len(message),
            "processing_time": f"{round(time.time() - start_time, 3)}s"
        }
    }

    tags = tag_message(result)
    save_to_memory(message, tags)
    return result
