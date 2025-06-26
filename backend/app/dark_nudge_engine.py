import random
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from .memory import update_trait, get_recent_history
from .behaviour_analyzer import detect_resistance
from .nlp_analysis import detect_emotion, is_task_like_message
from .task_nudging import infer_ongoing_tasks, generate_task_nudge

# ----------------------------------
# Nudge Tone Templates
# ----------------------------------

PERSUASION_TACTICS = {
    "soft": [
        "Let's start small, just 2 minutes?",
        "You’ve done harder things before, remember?",
        "Tiny action > endless thinking.",
    ],
    "hard": [
        "You keep putting it off… when’s it going to change?",
        "Let’s stop pretending you’re stuck. You’re stalling.",
        "Another excuse? Classic.",
    ],
    "dark": [
        "You promised yourself you'd do this. Are you breaking that promise again?",
        "Imagine explaining this excuse to your future self.",
        "Time is finite. Every delay costs you something.",
    ],
    "teasing": [
        "Oh come on, scared of a little challenge?",
        "Didn’t expect you to flake… but here we are 😏",
        "Go ahead, procrastinate. It’s your thing, right?",
    ],
    "existential": [
        "If you don’t act now, who will you become?",
        "Every choice you make… makes you. What does this one say?",
    ],
}

# ----------------------------------
# Configs / Limits
# ----------------------------------

MAX_DARK_NUDGES_PER_DAY = 3
NUDGE_COOLDOWN_MINUTES = 10
FATIGUE_RECOVERY_TIME = timedelta(minutes=30)

# ----------------------------------
# Dark Nudge Engine (Main)
# ----------------------------------

def generate_dark_nudge(user_id: str, user_input: str, traits: dict, flags: List[str]) -> Optional[str]:
    recent_msgs = get_recent_history(user_id)[-5:]

    # ✅ 1. Resistance Handling
    if detect_resistance(user_input):
        update_retreat(user_id, traits)
        if traits.get("retreat_count", 0) >= 2:
            return None
        return "Okay, I’ll back off for now."

    # ✅ 2. Cooldown / Fatigue Check
    if in_nudge_cooldown(traits):
        return None

    # ✅ 3. Task-Linked Nudging Priority
    if is_task_like_message(user_input):
        tasks = infer_ongoing_tasks(user_id)
        if tasks:
            nudge = generate_task_nudge(tasks[0])
            return shorten_nudge_if_needed(nudge, user_input)

    # ✅ 4. Emotion & Behavior-Based Tone Selection
    dominant_emotion = detect_emotion(user_input).lower()
    tone = select_nudge_tone(traits, dominant_emotion, flags)

    # ✅ 5. Daily Dark Limit Enforcement
    if tone == "dark" and exceeded_daily_dark_limit(traits):
        tone = "hard"

    # ✅ 6. Generate Final Nudge Text
    selected_nudge = random.choice(PERSUASION_TACTICS[tone])

    # ✅ 7. Track Nudge History & Fatigue
    track_nudge_sent(user_id, tone, traits)

    return shorten_nudge_if_needed(selected_nudge, user_input)

# ----------------------------------
# Tone Selection Logic
# ----------------------------------

def select_nudge_tone(traits: dict, emotion: str, flags: List[str]) -> str:
    preference = traits.get("preferred_nudge_tone", "soft")
    fatigue = traits.get("nudge_fatigue_level", 0)

    if fatigue >= 3:
        return "soft"
    if emotion in ["sadness", "anxiety", "grief", "fear"]:
        return "soft"
    elif emotion in ["frustration", "anger"]:
        return "hard"
    elif emotion in ["boredom", "neutral"] and "procrastination" in flags:
        return "teasing"
    elif emotion in ["guilt", "shame"]:
        return "dark"
    elif emotion == "unknown":
        return preference
    else:
        return preference

# ----------------------------------
# Cooldown & Fatigue Management
# ----------------------------------

def in_nudge_cooldown(traits: dict) -> bool:
    last_time = traits.get("last_nudge_time")
    if last_time:
        try:
            last_dt = datetime.fromisoformat(last_time)
            return datetime.utcnow() - last_dt < timedelta(minutes=NUDGE_COOLDOWN_MINUTES)
        except Exception:
            pass
    return False

def track_nudge_sent(user_id: str, tone: str, traits: dict):
    now = datetime.utcnow().isoformat()
    update_trait(user_id, "last_nudge_time", now)

    fatigue = traits.get("nudge_fatigue_level", 0)
    update_trait(user_id, "nudge_fatigue_level", fatigue + 1)

    tone_key = f"nudge_tone_count_{tone}"
    tone_count = traits.get(tone_key, 0)
    update_trait(user_id, tone_key, tone_count + 1)

    fatigue_reset(user_id, traits)

def fatigue_reset(user_id: str, traits: dict):
    last_time = traits.get("last_nudge_time")
    if last_time:
        try:
            last_dt = datetime.fromisoformat(last_time)
            if datetime.utcnow() - last_dt > FATIGUE_RECOVERY_TIME:
                update_trait(user_id, "nudge_fatigue_level", 0)
        except Exception:
            pass

def update_retreat(user_id: str, traits: dict):
    retreat = traits.get("retreat_count", 0)
    update_trait(user_id, "retreat_count", retreat + 1)

def exceeded_daily_dark_limit(traits: dict) -> bool:
    dark_count = traits.get("daily_dark_nudges", 0)
    return dark_count >= MAX_DARK_NUDGES_PER_DAY

# ----------------------------------
# Length Control
# ----------------------------------

def shorten_nudge_if_needed(nudge: str, user_input: str) -> str:
    if len(user_input.split()) <= 6 and len(nudge) > 60:
        return nudge.split(".")[0] + "."
    return nudge

# ----------------------------------
# Debugging / Explainability
# ----------------------------------

def explain_nudge_decision(user_id: str, user_input: str, traits: dict, flags: Optional[List[str]] = None) -> Dict:
    dominant_emotion = detect_emotion(user_input).lower()
    tone = select_nudge_tone(traits, dominant_emotion, flags or [])
    return {
        "user_input": user_input,
        "dominant_emotion": dominant_emotion,
        "user_traits": traits,
        "chosen_tone": tone,
        "fatigue_level": traits.get("nudge_fatigue_level", 0),
        "dark_nudge_count_today": traits.get("daily_dark_nudges", 0),
        "in_cooldown": in_nudge_cooldown(traits)
    }
