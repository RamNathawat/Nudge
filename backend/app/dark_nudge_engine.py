from typing import Optional, List, Dict
from .memory import user_memory, get_traits, get_recent_history
import random

# Persuasion tactics mapped to triggers
PERSUASION_TACTICS = {
    "avoidance": [
        "You’ve been dodging this. Why?",
        "Later again? Or never?",
        "You know exactly what you’re avoiding — say it.",
    ],
    "self-doubt": [
        "You keep second-guessing yourself. What if you just *did* instead of thinking so much?",
        "You’re better than this indecisive version of you.",
        "If you fail, so what? At least you tried. This? This isn’t even effort."
    ],
    "procrastination": [
        "Another delay? Time’s not waiting for you.",
        "You’ve had this window before. You let it close. Want to repeat that?",
        "Imagine how you'd feel tomorrow if you actually did it today."
    ],
    "weed": [
        "Is this about relaxing, or escaping again?",
        "How many times has weed been the easy out?",
        "You’re not *really* high anymore. Just dulled down."
    ]
}

def detect_relevant_tactic(traits: Dict[str, float], flags: List[str], recent_msgs: List[str]) -> Optional[str]:
    # Rank relevance
    for category, prompts in PERSUASION_TACTICS.items():
        if category in flags or category in traits or any(category in msg.lower() for msg in recent_msgs):
            return random.choice(prompts)
    return None

def generate_dark_nudge(user_input: str, traits: Dict[str, float], flags: List[str]) -> Optional[str]:
    recent_msgs = [msg["text"] for msg in get_recent_history()[-5:] if msg["sender"] == "user"]
    return detect_relevant_tactic(traits, flags, recent_msgs)
