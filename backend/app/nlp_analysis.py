from functools import lru_cache
from transformers import pipeline

@lru_cache(maxsize=1)
def get_emotion_classifier():
    return pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        return_all_scores=False
    )

def detect_emotion(text: str) -> str:
    if not text or not text.strip():
        return "neutral"
    try:
        classifier = get_emotion_classifier()
        result = classifier(text)[0]
        return result["label"]
    except Exception as e:
        print(f"[Emotion Detection Error]: {e}")
        return "unknown"

def analyze_emotion_and_intent(text: str) -> dict:
    emotion = detect_emotion(text)

    if any(phrase in text.lower() for phrase in ["later", "maybe", "i don't want to", "not now", "tired", "lazy"]):
        intent = "avoidance"
    else:
        intent = "engagement"

    return {
        "emotion": emotion.lower(),
        "intent": intent
    }

def estimate_emotion(text: str):
    """
    Adapter function for use in memory.py.
    Returns (emotion, intensity).
    """
    analysis = analyze_emotion_and_intent(text)
    emotion = analysis.get("emotion", "neutral")

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
    intensity = intensity_map.get(emotion, 0.4)
    return emotion, intensity

def extract_topic_tags(text: str) -> list[str]:
    # TODO: Replace this with actual NLP-based keyword extraction
    return ["productivity", "emotion", "motivation"]
