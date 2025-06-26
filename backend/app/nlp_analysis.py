from functools import lru_cache
from transformers import pipeline, Pipeline
from keybert import KeyBERT
from typing import Dict, List, Tuple
import re

from .task_topic_inference import infer_task_topic

# ---------------------
# Emotion Detection
# ---------------------

@lru_cache(maxsize=1)
def get_emotion_classifier() -> Pipeline:
    return pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        tokenizer="j-hartmann/emotion-english-distilroberta-base",
        return_all_scores=False,
        truncation=True,
        max_length=512
    )

def detect_emotion(text: str) -> str:
    """
    Returns the dominant emotion label for the given text.
    Falls back to 'neutral' or 'unknown' on error.
    """
    if not text or not text.strip():
        return "neutral"

    try:
        classifier = get_emotion_classifier()
        result = classifier(text[:512])[0]
        return result.get("label", "unknown").lower()
    except Exception as e:
        print(f"[Emotion Detection Error]: {e}")
        return "unknown"

def estimate_emotion(text: str) -> Tuple[str, float]:
    """
    Estimates emotion label + intensity score (for salience, storage, or memory).
    """
    emotion = detect_emotion(text)

    intensity_map = {
        "joy": 0.9,
        "happy": 0.8,
        "anger": 0.9,
        "sadness": 0.8,
        "fear": 0.7,
        "disgust": 0.6,
        "surprise": 0.6,
        "neutral": 0.3,
        "unknown": 0.2,
    }

    return emotion, intensity_map.get(emotion, 0.4)

# ---------------------
# Topic Extraction
# ---------------------

_kw_model = KeyBERT(model="all-MiniLM-L6-v2")

def extract_topic_tags(text: str, top_n: int = 5) -> List[str]:
    """
    Extract key topic tags using KeyBERT.
    """
    if not text or not text.strip():
        return []

    try:
        keywords = _kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            use_maxsum=True,
            top_n=top_n
        )
        return [kw[0] for kw in keywords]
    except Exception as e:
        print(f"[Keyword Extraction Error]: {e}")
        return []

# ---------------------
# Intent and Substance Keyword Inference
# ---------------------

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

def infer_from_keywords(text: str, keyword_map: Dict[str, List[str]], default: str = "unknown") -> str:
    """
    Infers category (like intent or substance) based on presence of keywords.
    """
    text = text.lower()
    for category, keywords in keyword_map.items():
        if any(re.search(rf"\b{kw}\b", text) for kw in keywords):
            return category
    return default

def infer_user_state(message: str) -> Dict[str, str]:
    """
    Infers user's intent, possible substance use, and task topic.
    """
    return {
        "intent": infer_from_keywords(message, INTENT_KEYWORDS),
        "substance": infer_from_keywords(message, SUBSTANCE_KEYWORDS),
        "task_topic": infer_task_topic(message)
    }
def is_task_like_message(text: str) -> bool:
    """
    Simple heuristic: Checks if the message looks like a task or goal statement.
    """
    task_keywords = [
        "need to", "have to", "should", "must", "plan to", "goal", "target", "want to", "finish", "start", "complete"
    ]
    lower = text.lower()
    return any(kw in lower for kw in task_keywords)