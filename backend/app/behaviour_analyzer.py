import re
from typing import Optional, Dict, List
from .memory import update_trait, get_traits # Import get_traits to read traits
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

EMOTIONAL_PHRASES = { # Renamed to avoid confusion with behavior flags
    "stuck": "feels_stuck",
    "broke my promise": "broke_promise",
    "ashamed": "expresses_shame",
    "shame": "expresses_shame",
    "exhausted": "expresses_exhaustion",
    "hopeless": "expresses_hopelessness"
}

RESISTANCE_KEYWORDS = [
    "stop", "leave me alone", "this isn't working", "i don't care",
    "shut up", "you're annoying", "you're not helping",
    "why do you keep pushing", "let me be"
]

# -------------------------
# Main Behavior Analyzer
# -------------------------

def analyze_behavior(user_id: str, message: str) -> List[str]: # Now accepts user_id, returns list of flags
    """
    Analyzes user message for behavioral patterns and returns a list of flags.
    Updates user traits directly via update_trait.
    """
    lowered_msg = message.lower()
    detected_flags = []

    # === Excuse Detection ===
    current_user_traits = get_traits(user_id) # Get current traits to check
    for excuse in COMMON_EXCUSES:
        # Check if the excuse is new for this user before marking it
        if excuse in lowered_msg and excuse not in current_user_traits.get("common_excuses_list", []):
            # Store common excuses in a list within traits
            existing_excuses = current_user_traits.get("common_excuses_list", [])
            existing_excuses.append(excuse)
            update_trait(user_id, "common_excuses_list", existing_excuses)
            detected_flags.append(f"excuse:{excuse.replace(' ', '_')}") # Flag for the specific excuse

    # === Procrastination Detection ===
    for pattern in PROCRASTINATION_PATTERNS:
        if re.search(pattern, lowered_msg):
            # Increment procrastination level
            current_procrastination_level = current_user_traits.get("procrastination_level", 0)
            update_trait(user_id, "procrastination_level", current_procrastination_level + 1)
            detected_flags.append("procrastination")
            break # Only flag once per message

    # === Emotional Trait Flags ===
    for phrase, flag_key in EMOTIONAL_PHRASES.items():
        if phrase in lowered_msg:
            # Set the emotional flag to True
            update_trait(user_id, flag_key, True)
            detected_flags.append(flag_key)

    # === Resistance Detection ===
    if detect_resistance(lowered_msg):
        current_retreat_count = current_user_traits.get("retreat_count", 0)
        update_trait(user_id, "retreat_count", current_retreat_count + 1)
        detected_flags.append("resistance")

    # NLP Mood Detection (trait update, not a direct flag for nudging calculation usually)
    try:
        emotion = detect_emotion(message)
        update_trait(user_id, "last_detected_mood", emotion) # Store last detected mood as a trait
    except Exception:
        pass # Fallback handled by NLP module

    return detected_flags # Return the list of detected flags


# -------------------------
# Resistance Detection Logic
# -------------------------

def detect_resistance(message: str) -> bool:
    """
    Checks for pushback or emotional resistance indicating the user is not receptive.
    """
    return any(keyword in message for keyword in RESISTANCE_KEYWORDS)

# -------------------------
# New function for emotional relevance
# -------------------------

def is_emotionally_relevant(message: str, flags: List[str]) -> bool:
    """
    Determines if a message is emotionally relevant enough to potentially shift tone.
    Considers flags and emotion detection.
    """
    # Check for direct emotional phrases from EMOTIONAL_PHRASES
    if any(flag_key in flags for flag_key in EMOTIONAL_PHRASES.values()):
        return True

    # Check for resistance
    if "resistance" in flags:
        return True

    # Check for procrastination
    if "procrastination" in flags:
        return True

    # Check if the detected emotion is negative or strong positive (e.g., anger, sadness, joy)
    # This requires running detect_emotion directly or getting it from a previous step
    emotion = detect_emotion(message)
    if emotion in ["anger", "sadness", "fear", "disgust", "joy", "surprise"]:
        return True

    return False

# -------------------------
# Explainable Debug Output (Optional)
# -------------------------

def explain_behavior_analysis(user_id: str, message: str) -> Dict:
    """
    Returns an explainable dictionary of what was detected for debugging or AI monitoring.
    """
    lowered_msg = message.lower()
    current_user_traits = get_traits(user_id) # Get current traits for explanation

    return {
        "input": message,
        "detected_excuses": [
            excuse for excuse in COMMON_EXCUSES if excuse in lowered_msg
        ],
        "procrastination_patterns_matched": [
            pattern for pattern in PROCRASTINATION_PATTERNS if re.search(pattern, lowered_msg)
        ],
        "emotional_phrases_detected": [ # Renamed to avoid confusion
            flag for phrase, flag in EMOTIONAL_PHRASES.items() if phrase in lowered_msg
        ],
        "resistance_detected": detect_resistance(lowered_msg),
        "current_retreat_count": current_user_traits.get("retreat_count", 0),
        "current_procrastination_level": current_user_traits.get("procrastination_level", 0),
        "nlp_detected_mood": detect_emotion(message),
        "all_detected_flags": analyze_behavior(user_id, message) # Re-run to get flags
    }