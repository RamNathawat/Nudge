import re
from .memory import update_trait, user_memory
from .nlp_analysis import detect_emotion  # Uses transformer-based emotion detection


def analyze_behavior(message: str) -> str:
    message = message.lower()

    # === Excuses Detection ===
    excuses = [
        "i'll do it later",
        "i'm tired",
        "maybe tomorrow",
        "not in the mood",
        "i’m lazy"
    ]
    for excuse in excuses:
        if excuse in message and excuse not in user_memory["traits"]["common_excuses"]:
            user_memory["traits"]["common_excuses"].append(excuse)

    # === Procrastination Detection ===
    if re.search(r"\b(do it (later|tomorrow|next time))\b", message):
        user_memory["traits"]["procrastination_level"] += 1

    # === NLP-powered Mood Detection ===
    emotion = detect_emotion(message)  # e.g., "joy", "sadness", "anger", etc.
    update_trait("mood", emotion)

    return emotion  # Return for use in chat flow


def is_emotionally_relevant(message: str, emotion: str) -> bool:
    """
    Decide whether the message contains emotional or behavioral cues
    that warrant a switch to persuasive/dark nudging mode.
    """

    # Emotional trigger words or states
    negative_emotions = {"sadness", "anger", "fear", "disgust", "frustration", "shame"}
    behavior_flags = user_memory["traits"]

    # Trigger conditions
    has_negative_emotion = emotion in negative_emotions
    has_repeated_procrastination = behavior_flags["procrastination_level"] >= 2
    made_multiple_excuses = len(behavior_flags["common_excuses"]) >= 2

    return has_negative_emotion or has_repeated_procrastination or made_multiple_excuses


if __name__ == "__main__":
    test_msgs = [
        "I'll do it later",
        "I'm super excited about this!",
        "Not in the mood today",
        "Maybe tomorrow",
        "I'm really angry at everything"
    ]

    for msg in test_msgs:
        detected_emotion = analyze_behavior(msg)
        relevance = is_emotionally_relevant(msg, detected_emotion)
        print(f"[{msg}] → Emotion: {detected_emotion}, Trigger Persuasion? {relevance}")
