import re
from typing import Optional, Dict, List
from .memory import update_trait, user_memory
from .nlp_analysis import detect_emotion

# -------------------------
# Configurable Pattern Sets
# -------------------------

COMMON_EXCUSES = [
    "i'll do it later", "i'm tired", "maybe tomorrow", "not in the mood", 
    "i'm lazy", "i’m overwhelmed", "i don’t feel ready"
]

PROCRASTINATION_PATTERNS = [
    r"\b(i'?ll|i will)?\s*do it\s*(later|tomorrow|next time|soon)\b",
    r"\b(can|could|might)?\s*do\s*(this|that|it)?\s*(tomorrow|later)\b"
]

EMOTIONAL_FLAGS = {
    "stuck": "user_feels_stuck",
    "broke my promise": "user_broke_promise",
    "ashamed": "user_expresses_shame",
    "shame": "user_expresses_shame",
    "exhausted": "user_expresses_exhaustion",
    "hopeless": "user_expresses_hopelessness"
}

RESISTANCE_KEYWORDS = [
    "stop", "leave me alone", "this isn't working", "i don't care", 
    "shut up", "you're annoying", "you're not helping", 
    "why do you keep pushing", "let me be"
]

# -------------------------
# Main Behavior Analyzer
# -------------------------

def analyze_behavior(message: str) -> Optional[str]:
    """
    Analyzes user message for behavioral patterns like procrastination, emotional struggle, excuses, or resistance.
    Updates user memory and traits. Returns the detected emotional mood.
    """
    lowered_msg = message.lower()

    # === Excuse Detection ===
    for excuse in COMMON_EXCUSES:
        if excuse in lowered_msg and excuse not in user_memory["traits"]["common_excuses"]:
            user_memory["traits"]["common_excuses"].append(excuse)

    # === Procrastination Detection ===
    for pattern in PROCRASTINATION_PATTERNS:
        if re.search(pattern, lowered_msg):
            user_memory["traits"]["procrastination_level"] += 1
            break

    # === Emotional Trait Flags ===
    for phrase, trait_key in EMOTIONAL_FLAGS.items():
        if phrase in lowered_msg:
            user_memory["traits"][trait_key] = True

    # === Resistance Detection ===
    if detect_resistance(lowered_msg):
        user_memory["traits"]["retreat_count"] += 1

    # === NLP Mood Detection ===
    try:
        emotion = detect_emotion(message)
        update_trait("mood", emotion)
    except Exception:
        emotion = "neutral"  # fallback

    return emotion

# -------------------------
# Resistance Detection Logic
# -------------------------

def detect_resistance(message: str) -> bool:
    """
    Checks for pushback or emotional resistance indicating the user is not receptive.
    Updates `retreat_count` if resistance is found.
    """
    return any(keyword in message for keyword in RESISTANCE_KEYWORDS)

# -------------------------
# Explainable Debug Output (Optional)
# -------------------------

def explain_behavior_analysis(message: str) -> Dict:
    """
    Returns an explainable dictionary of what was detected for debugging or AI monitoring.
    """
    lowered_msg = message.lower()

    return {
        "input": message,
        "detected_excuses": [
            excuse for excuse in COMMON_EXCUSES if excuse in lowered_msg
        ],
        "procrastination_patterns_matched": [
            pattern for pattern in PROCRASTINATION_PATTERNS if re.search(pattern, lowered_msg)
        ],
        "emotional_flags_raised": [
            trait for phrase, trait in EMOTIONAL_FLAGS.items() if phrase in lowered_msg
        ],
        "resistance_detected": detect_resistance(lowered_msg),
        "retreat_count": user_memory["traits"].get("retreat_count", 0),
        "nlp_detected_mood": detect_emotion(message)
    }
