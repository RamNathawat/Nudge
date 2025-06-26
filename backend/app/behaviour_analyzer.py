import re
from typing import Optional, Dict, List
from .memory import update_trait, get_traits
from .nlp_analysis import detect_emotion

# -------------------------------
# Pattern Definitions
# -------------------------------

COMMON_EXCUSES = [
    "i'll do it later", "i'm tired", "maybe tomorrow", "not in the mood",
    "i'm lazy", "i’m overwhelmed", "i don’t feel ready", "not feeling it",
    "too much going on", "i can't focus"
]

PROCRASTINATION_PATTERNS = [
    r"\b(i'?ll|i will)?\s*do it\s*(later|tomorrow|next time|soon)\b",
    r"\b(can|could|might)?\s*do\s*(this|that|it)?\s*(tomorrow|later)\b",
    r"\b(not now|another time|after some time)\b"
]

EMOTIONAL_PHRASES = {
    "stuck": "feels_stuck",
    "broke my promise": "broke_promise",
    "ashamed": "expresses_shame",
    "shame": "expresses_shame",
    "exhausted": "expresses_exhaustion",
    "hopeless": "expresses_hopelessness",
    "demotivated": "expresses_demotivation",
    "pointless": "expresses_hopelessness"
}

RESISTANCE_KEYWORDS = [
    "stop", "leave me alone", "this isn't working", "i don't care",
    "shut up", "you're annoying", "you're not helping",
    "why do you keep pushing", "let me be", "back off", "stop bothering me"
]

# -------------------------------
# Main Behavior Analysis
# -------------------------------

def analyze_behavior(user_id: str, message: str) -> List[str]:
    """
    Analyzes user message for behavioral patterns and returns a list of flags.
    Also updates relevant user traits in the database.
    """
    lowered_msg = message.lower()
    flags = []
    traits = get_traits(user_id)

    # === Excuse Detection ===
    for excuse in COMMON_EXCUSES:
        if excuse in lowered_msg and excuse not in traits.get("common_excuses_list", []):
            existing_excuses = traits.get("common_excuses_list", [])
            existing_excuses.append(excuse)
            update_trait(user_id, "common_excuses_list", existing_excuses)
            flags.append(f"excuse:{excuse.replace(' ', '_')}")

    # === Procrastination Detection ===
    for pattern in PROCRASTINATION_PATTERNS:
        if re.search(pattern, lowered_msg):
            level = traits.get("procrastination_level", 0) + 1
            update_trait(user_id, "procrastination_level", level)
            flags.append("procrastination")
            break

    # === Emotional State Flags ===
    for phrase, flag in EMOTIONAL_PHRASES.items():
        if phrase in lowered_msg:
            update_trait(user_id, flag, True)
            flags.append(flag)

    # === Resistance Detection ===
    if detect_resistance(lowered_msg):
        retreat_count = traits.get("retreat_count", 0) + 1
        update_trait(user_id, "retreat_count", retreat_count)
        flags.append("resistance")

    # === NLP Detected Mood (Store as Trait) ===
    try:
        mood = detect_emotion(message)
        update_trait(user_id, "last_detected_mood", mood)
    except Exception:
        pass  # NLP failure fallback

    return flags

# -------------------------------
# Resistance Detection
# -------------------------------

def detect_resistance(message: str) -> bool:
    return any(keyword in message for keyword in RESISTANCE_KEYWORDS)

# -------------------------------
# Emotional Relevance Scoring (For Nudging Triggers)
# -------------------------------

def is_emotionally_relevant(message: str, flags: List[str]) -> bool:
    """
    Checks if this message is emotionally charged enough to justify nudging escalation.
    Looks at flags and detected emotion type.
    """
    # Direct emotional flag triggers
    if any(flag in flags for flag in EMOTIONAL_PHRASES.values()):
        return True
    if "resistance" in flags or "procrastination" in flags:
        return True

    # NLP Emotion-based triggers
    emotion = detect_emotion(message)
    return emotion in ["anger", "sadness", "fear", "disgust", "joy", "surprise"]

# -------------------------------
# Debugging Helper (Optional)
# -------------------------------

def explain_behavior_analysis(user_id: str, message: str) -> Dict:
    """
    Returns detailed breakdown of all detected behavioral signals for debugging.
    """
    lowered_msg = message.lower()
    traits = get_traits(user_id)

    return {
        "input_message": message,
        "detected_excuses": [
            excuse for excuse in COMMON_EXCUSES if excuse in lowered_msg
        ],
        "procrastination_matches": [
            p for p in PROCRASTINATION_PATTERNS if re.search(p, lowered_msg)
        ],
        "emotional_phrase_flags": [
            flag for phrase, flag in EMOTIONAL_PHRASES.items() if phrase in lowered_msg
        ],
        "resistance_detected": detect_resistance(lowered_msg),
        "current_traits_snapshot": traits,
        "nlp_detected_emotion": detect_emotion(message),
        "final_behavior_flags": analyze_behavior(user_id, message)
    }
