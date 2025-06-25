from functools import lru_cache
from transformers import pipeline, Pipeline
from transformers.pipelines.pt_utils import KeyDataset
from keybert import KeyBERT

@lru_cache(maxsize=1)
def get_emotion_classifier() -> Pipeline:
    return pipeline(
        "text-classification",
        model="j-hartmann/emotion-english-distilroberta-base",
        tokenizer="j-hartmann/emotion-english-distilroberta-base",
        return_all_scores=False,
        truncation=True,       # ✅ Ensures long inputs are safely truncated
        max_length=512         # ✅ Limit to model max token limit
    )

def detect_emotion(text: str) -> str:
    """
    Returns the top emotion label for a given piece of text.
    Handles truncation to avoid tensor size mismatches.
    """
    if not text or not text.strip():
        return "neutral"

    try:
        classifier = get_emotion_classifier()
        result = classifier(text[:512])[0]  # Extra truncation safeguard
        return result["label"]
    except Exception as e:
        print(f"[Emotion Detection Error]: {e}")
        return "unknown"

def analyze_emotion_and_intent(text: str) -> dict:
    """
    Returns emotion + intent flags for context scoring.
    """
    emotion = detect_emotion(text)

    # Very basic avoidance intent detection
    if any(phrase in text.lower() for phrase in ["later", "maybe", "i don't want to", "not now", "tired", "lazy"]):
        intent = "avoidance"
    else:
        intent = "engagement"

    return {
        "emotion": emotion.lower(),
        "intent": intent
    }

def estimate_emotion(text: str) -> tuple[str, float]:
    """
    Adapter function for memory systems — returns (emotion, intensity).
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

# Load once and cache
_kw_model = KeyBERT(model="all-MiniLM-L6-v2")

def extract_topic_tags(text: str, top_n: int = 5) -> list[str]:
    """
    Extracts meaningful topic tags using KeyBERT.
    Returns a list of keywords from the input text.
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