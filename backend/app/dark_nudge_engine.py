import random
from typing import Optional, List, Dict
from datetime import datetime
from .memory import user_memory, get_traits, get_recent_history
from .behaviour_analyzer import detect_resistance
from .task_nudging import infer_ongoing_tasks, generate_task_nudge
from .nlp_analysis import is_task_like_message

# ---------------------------------------------
# Config
# ---------------------------------------------

MAX_DARK_NUDGES = 3
DARK_NUDGE_HISTORY_KEY = "dark_nudge_count"

PERSUASION_TACTICS = {
    "soft": {
        "procrastination": [
            "Let’s start small — maybe just 2 minutes?",
            "You’ve done hard things before, remember?",
        ],
        "encouragement": [
            "You’re way more capable than you feel right now.",
            "Momentum starts with a single step.",
        ],
    },
    "hard": {
        "procrastination": [
            "You keep putting it off — when’s it going to change?",
            "Let’s stop pretending you’re stuck. You’re stalling.",
        ],
        "ego-challenging": [
            "You said you were better than this — were you lying?",
            "Talk is cheap. Prove it now.",
        ],
    },
    "dark": {
        "guilt-tripping": [
            "You promised yourself you'd do this. Are you letting yourself down?",
            "Imagine explaining this excuse to your future self.",
        ],
        "reverse-psychology": [
            "Maybe you shouldn’t even try — it's probably too hard for you.",
            "You probably can’t finish this anyway, right?",
        ],
        "existential": [
            "You think time is infinite? It’s not. Every delay costs you something.",
            "If you don’t act now, what version of you will exist next year?",
        ]
    }
}

# ---------------------------------------------
# Core Nudge Selector
# ---------------------------------------------

def detect_relevant_tactic(
    traits: Dict[str, float],
    flags: List[str],
    recent_msgs: List[str],
    mode: str = "soft"
) -> Optional[str]:
    if mode not in PERSUASION_TACTICS:
        raise ValueError(f"Invalid mode: {mode}. Choose from: {', '.join(PERSUASION_TACTICS.keys())}")
    
    mode_tactics = PERSUASION_TACTICS[mode]
    for category, prompts in mode_tactics.items():
        score = 0
        if category in flags:
            score += 3
        if traits.get(category, 0) > 0.5:
            score += 2
        if any(category in msg.lower() for msg in recent_msgs):
            score += 1
        if score >= 2:
            return random.choice(prompts)
    return None

# ---------------------------------------------
# Task Nudge + Dark Strategy Orchestrator
# ---------------------------------------------

def generate_dark_nudge(user_input: str, traits: Dict[str, float], flags: List[str], user_id: str) -> Optional[str]:
    recent_msgs = [
        msg["text"] for msg in get_recent_history(user_id)[-5:]
        if msg.get("sender") == "user" and "text" in msg
    ]

    # === 1. Resistance Check ===
    if detect_resistance(user_input):
        user_memory[user_id]["traits"]["retreat_count"] = user_memory[user_id]["traits"].get("retreat_count", 0) + 1
        if user_memory[user_id]["traits"]["retreat_count"] < 2:
            return "Alright, I hear you. Let's not force this right now."
        else:
            return None

    # === 2. Task Nudging First ===
    if is_task_like_message(user_input):
        tasks = infer_ongoing_tasks(user_id)
        if tasks:
            task_nudge = generate_task_nudge(tasks[0])
            return task_nudge + " Want me to check back in 2 days?"

    # === 3. Dark Nudge Throttle Check ===
    dark_count = user_memory[user_id]["traits"].get(DARK_NUDGE_HISTORY_KEY, 0)
    if dark_count >= MAX_DARK_NUDGES:
        return detect_relevant_tactic(traits, flags, recent_msgs, mode="soft")

    # === 4. Run Dark Nudge ===
    nudge = detect_relevant_tactic(traits, flags, recent_msgs, mode="dark")
    if nudge:
        user_memory[user_id]["traits"][DARK_NUDGE_HISTORY_KEY] = dark_count + 1
    return nudge

# ---------------------------------------------
# Optional: Explain Logic Internally
# ---------------------------------------------

def explain_nudge_decision(
    user_input: str,
    user_id: str,
    traits: Optional[Dict[str, float]] = None,
    flags: Optional[List[str]] = None,
    mode: str = "soft"
) -> Dict[str, any]:
    traits = traits or get_traits(user_id)
    flags = flags or []
    recent_msgs = [
        msg["text"] for msg in get_recent_history(user_id)[-5:]
        if msg.get("sender") == "user" and "text" in msg
    ]
    selected_nudge = detect_relevant_tactic(traits, flags, recent_msgs, mode)
    resistance = detect_resistance(user_input)
    retreat_count = user_memory[user_id]["traits"].get("retreat_count", 0)

    return {
        "mode": mode,
        "user_input": user_input,
        "resistance_detected": resistance,
        "retreat_count": retreat_count,
        "dark_nudge_count": user_memory[user_id]["traits"].get(DARK_NUDGE_HISTORY_KEY, 0),
        "traits_used": traits,
        "flags_used": flags,
        "recent_user_messages": recent_msgs,
        "selected_nudge": selected_nudge or "fallback"
    }

# ---------------------------------------------
# Future: Dynamic Mode Selection
# ---------------------------------------------

def nudge_mode_controller(user_id: str) -> str:
    return "dark"  # Will later depend on emotion, fatigue, frequency, tone adaptation