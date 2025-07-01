# app/dark_nudge_engine.py
import random
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from .memory import update_trait, get_recent_history, get_traits # Ensure get_traits is also imported
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
# Helper Functions for Nudging Logic (Moved/Implemented here for clarity)
# ----------------------------------

def update_retreat(user_id: str, traits: Dict):
    """Increments the retreat count for the user."""
    retreat_count = traits.get("retreat_count", 0) + 1
    update_trait(user_id, "retreat_count", retreat_count)

def in_nudge_cooldown(traits: Dict) -> bool:
    """Checks if the user is currently in a nudge cooldown period."""
    last_nudge_sent_at = traits.get("last_nudge_sent_at")
    if last_nudge_sent_at:
        if isinstance(last_nudge_sent_at, str):
            try:
                last_nudge_sent_at = datetime.fromisoformat(last_nudge_sent_at)
            except ValueError:
                return False # Invalid format means no valid cooldown time
        
        return (datetime.now() - last_nudge_sent_at) < timedelta(minutes=NUDGE_COOLDOWN_MINUTES)
    return False

def exceeded_daily_dark_limit(traits: Dict) -> bool:
    """Checks if the user has exceeded the daily dark nudge limit."""
    today = datetime.now().date().isoformat()
    daily_count_key = f"daily_dark_nudge_count_{today}"
    return traits.get(daily_count_key, 0) >= MAX_DARK_NUDGES_PER_DAY

def track_nudge_sent(user_id: str, tone: str, traits: Dict):
    """Tracks the last nudge sent time and daily dark nudge count."""
    update_trait(user_id, "last_nudge_sent_at", datetime.now().isoformat())
    
    if tone == "dark":
        today = datetime.now().date().isoformat()
        daily_count_key = f"daily_dark_nudge_count_{today}"
        current_count = traits.get(daily_count_key, 0)
        update_trait(user_id, daily_count_key, current_count + 1)

def shorten_nudge_if_needed(nudge_text: str, user_input: str) -> str:
    """A placeholder for a function that shortens nudges if they are too long."""
    # Implement actual shortening logic based on desired length or context
    # For now, simply returns the original text
    return nudge_text

# ----------------------------------
# Dark Nudge Engine (Main)
# ----------------------------------
def generate_dark_nudge(user_id: str, user_input: str, traits: dict, flags: List[str]) -> Optional[str]:
    recent_msgs = get_recent_history(user_id)[-5:] # Fetches recent 5 messages

    # ✅ 1. Resistance Handling
    if detect_resistance(user_input):
        update_retreat(user_id, traits) # Call the implemented helper function
        if traits.get("retreat_count", 0) >= 2:
            return None
        return "Okay, I’ll back off for now."

    # ✅ 2. Cooldown / Fatigue Check
    if in_nudge_cooldown(traits): # Call the implemented helper function
        return None

    # ✅ 3. Task-Linked Nudging Priority
    if is_task_like_message(user_input):
        tasks = infer_ongoing_tasks(user_id)
        if tasks:
            nudge = generate_task_nudge(tasks[0])
            return shorten_nudge_if_needed(nudge, user_input)

    # ✅ 4. Emotion & Behavior-Based Tone Selection
    dominant_emotion = detect_emotion(user_input).lower()
    tone = select_nudge_tone(traits, dominant_emotion, flags) # select_nudge_tone should be defined in this file

    # ✅ 5. Daily Dark Limit Enforcement
    if tone == "dark" and exceeded_daily_dark_limit(traits): # Call the implemented helper function
        tone = "hard"

    # ✅ 6. Generate Final Nudge Text
    selected_nudge = random.choice(PERSUASION_TACTICS[tone])

    # ✅ 7. Track Nudge History & Fatigue
    track_nudge_sent(user_id, tone, traits) # Call the implemented helper function
    return shorten_nudge_if_needed(selected_nudge, user_input)

# ----------------------------------
# Tone Selection Logic (Placeholder, ensure this function is defined)
# ----------------------------------
def select_nudge_tone(traits: Dict, dominant_emotion: str, flags: List[str]) -> str:
    """
    Selects the appropriate nudge tone based on user traits, emotion, and flags.
    This is a placeholder and needs to be implemented with actual logic.
    """
    # Example logic (customize heavily)
    if traits.get("procrastination_level", 0) > 3 or "procrastination" in flags:
        return "dark"
    if "resistance" in flags:
        return "teasing"
    if dominant_emotion in ["sadness", "fear"]:
        return "soft"
    if traits.get("retreat_count", 0) > 0:
        return "hard"
    return "soft" # Default tone