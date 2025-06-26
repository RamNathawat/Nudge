# app/nudge_scoring.py

from typing import Dict, List, Any

# Emotion weight multipliers (psychological impact level)
EMOTION_WEIGHTS = {
    "anxiety": 1.2,
    "guilt": 1.5,
    "shame": 1.5,
    "frustration": 1.3,
    "sadness": 1.1,
    "anger": 1.4,
    "hopelessness": 1.7,
    "avoidance": 1.3,
    "boredom": 0.9,
    "confidence": -0.5,    # Reduces nudge need
    "motivation": -1.0,    # High motivation = Less nudge
    "joy": -0.3,
    "optimism": -0.4,
}

# Behavior flag multipliers (trigger factors)
FLAG_WEIGHTS = {
    "procrastination": 1.2,
    "avoidance": 1.3,
    "guilt-tripping": 1.0,
    "resistance": 1.5,
    "disengagement": 1.4,
    "stuck": 1.3,
    "ego-defensive": 1.1,
    "self-deception": 1.6,
    "excuse": 1.1,  # General excuse flag if present
}

# Personality trait weights (chronic patterns)
TRAIT_WEIGHTS = {
    "avoidant": 1.2,
    "perfectionist": 1.1,
    "insecure": 1.4,
    "self-critical": 1.3,
    "retreat_count": 0.5,       # Escalate nudge if user keeps backing off
    "procrastination_level": 0.6,
}

def calculate_nudging_score(
    emotions: Dict[str, float],
    flags: List[str],
    traits: Dict[str, Any] = {}
) -> int:
    """
    Calculates a nudging intensity score between 1–5.

    Factors considered:
    - Emotional state (weighted by psychological impact)
    - Detected behavioral flags (contextual triggers)
    - Long-term user traits (chronic tendencies)
    """

    # -------- Emotion Weighting --------
    emotion_score = 0.0
    for emotion, intensity in emotions.items():
        weight = EMOTION_WEIGHTS.get(emotion, 0.8)  # Default small influence if unseen
        emotion_score += intensity * weight

    # -------- Behavior Flag Influence --------
    flag_score = 0.0
    for flag in flags:
        # Handle dynamic flags like excuse:xxx
        if flag.startswith("excuse:"):
            flag_score += FLAG_WEIGHTS.get("excuse", 0.8)
        else:
            flag_score += FLAG_WEIGHTS.get(flag, 0.8)

    # -------- Trait Influence --------
    trait_score = 0.0
    for trait, trait_value in traits.items():
        weight = TRAIT_WEIGHTS.get(trait)
        if weight:
            # Treat count-based traits like retreat_count or procrastination_level proportionally
            if isinstance(trait_value, (int, float)):
                trait_score += trait_value * weight

    # -------- Total Raw Score --------
    raw_score = emotion_score + flag_score + trait_score

    # -------- Normalization and Capping --------
    if raw_score <= 2:
        return 1  # No nudge needed
    elif raw_score <= 5:
        return 2  # Soft encouragement
    elif raw_score <= 8:
        return 3  # Gentle push
    elif raw_score <= 11:
        return 4  # Firm nudge or mild confrontation
    else:
        return 5  # Strongest intervention (e.g., challenge, confrontation)

def explain_score_breakdown(
    emotions: Dict[str, float],
    flags: List[str],
    traits: Dict[str, Any] = {}
) -> Dict[str, Any]:
    """
    Detailed breakdown of what contributed to the final nudge score.
    Useful for debugging and AI self-monitoring.
    """
    emotion_breakdown = {}
    for emotion, intensity in emotions.items():
        weight = EMOTION_WEIGHTS.get(emotion, 0.8)
        emotion_breakdown[emotion] = round(intensity * weight, 2)

    flag_breakdown = {}
    for flag in flags:
        if flag.startswith("excuse:"):
            flag_breakdown[flag] = FLAG_WEIGHTS.get("excuse", 0.8)
        else:
            flag_breakdown[flag] = FLAG_WEIGHTS.get(flag, 0.8)

    trait_breakdown = {}
    for trait, value in traits.items():
        weight = TRAIT_WEIGHTS.get(trait)
        if weight and isinstance(value, (int, float)):
            trait_breakdown[trait] = round(value * weight, 2)

    final_score = calculate_nudging_score(emotions, flags, traits)

    return {
        "final_score": final_score,
        "emotions": emotion_breakdown,
        "flags": flag_breakdown,
        "traits": trait_breakdown,
        "raw_sum": round(
            sum(emotion_breakdown.values()) + sum(flag_breakdown.values()) + sum(trait_breakdown.values()),
            2
        )
    }
