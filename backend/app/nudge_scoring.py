# app/core/nudge_scoring.py

from typing import Dict, List

# Optional: Weighted importance of emotions
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
    "confidence": -0.5,   # reduces nudge intensity
    "motivation": -1.0,   # high motivation = less nudge needed
}

# Optional: Behavior flags that require stronger nudging
FLAG_WEIGHTS = {
    "procrastination": 1.2,
    "avoidance": 1.3,
    "guilt-tripping": 1.0,
    "resistance": 1.5,
    "disengagement": 1.4,
    "stuck": 1.3,
    "ego-defensive": 1.1,
    "self-deception": 1.6,
}

# Optional: Trait-based bonus
TRAIT_WEIGHTS = {
    "avoidant": 1.2,
    "perfectionist": 1.1,
    "insecure": 1.4,
    "self-critical": 1.3,
}


def calculate_nudging_score(
    emotions: Dict[str, float],
    flags: List[str],
    traits: Dict[str, float] = {}
) -> int:
    """
    Computes a nudging score (1–5) based on:
    - Emotion intensity (weighted)
    - Behavioral flags
    - Persistent traits

    Score Meaning:
    1 → No nudge needed
    2 → Very soft nudge
    3 → Gentle push
    4 → Strong nudge or challenge
    5 → Maximum intervention
    """

    # Emotion score
    emotion_score = sum(
        emotions.get(emotion, 0.0) * weight
        for emotion, weight in EMOTION_WEIGHTS.items()
    )

    # Behavior flag score
    flag_score = sum(FLAG_WEIGHTS.get(flag, 0.8) for flag in flags)

    # Trait bonus (if passed)
    trait_score = sum(
        traits.get(trait, 0.0) * weight
        for trait, weight in TRAIT_WEIGHTS.items()
    ) if traits else 0.0

    # Aggregate raw score
    raw_score = emotion_score + flag_score + trait_score

    # Normalize and clamp to 1–5
    if raw_score < 3:
        return 1
    elif raw_score < 6:
        return 2
    elif raw_score < 9:
        return 3
    elif raw_score < 12:
        return 4
    else:
        return 5


# Optional: Debug trace
def explain_score_breakdown(
    emotions: Dict[str, float],
    flags: List[str],
    traits: Dict[str, float] = {}
) -> Dict[str, any]:
    emotion_breakdown = {
        k: round(emotions.get(k, 0.0) * v, 2)
        for k, v in EMOTION_WEIGHTS.items()
        if emotions.get(k)
    }

    flag_breakdown = {
        k: FLAG_WEIGHTS.get(k, 0.8)
        for k in flags
    }

    trait_breakdown = {
        k: round(traits.get(k, 0.0) * v, 2)
        for k, v in TRAIT_WEIGHTS.items()
        if traits.get(k)
    }

    final_score = calculate_nudging_score(emotions, flags, traits)

    return {
        "score": final_score,
        "emotions": emotion_breakdown,
        "flags": flag_breakdown,
        "traits": trait_breakdown
    }
