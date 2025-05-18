from transformers import pipeline

# Initialize the emotion classifier
emotion_classifier = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base",
    return_all_scores=False
)

def detect_emotion(text: str) -> str:
    result = emotion_classifier(text)[0]
    return result["label"]

def analyze_emotion_and_intent(text: str) -> dict:
    emotion = detect_emotion(text)

    # Naive intent classification — you can make this smarter later
    if any(phrase in text.lower() for phrase in ["later", "maybe", "i don't want to", "not now", "tired", "lazy"]):
        intent = "avoidance"
    else:
        intent = "engagement"

    return {
        "emotion": emotion.lower(),
        "intent": intent
    }
