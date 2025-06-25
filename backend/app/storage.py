import json
from pathlib import Path

MEMORY_FILE = Path("backend/app/user_memory.json")

# Load memory from file or return default structure
def load_memory():
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Corrupt or empty file fallback
            return get_default_memory()
    return get_default_memory()

# Save memory to disk
def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Define default memory structure
def get_default_memory():
    return {
        "history": [],
        "traits": {
            "mood": "neutral",
            "common_excuses": [],
            "procrastination_level": 0
        },
        "emotional_state": {
            "mood": "neutral",
            "substance": None,
            "energy": None,
            "intent": None
        },
        "tone_feedback": {},
        "reminder_set": False,
        "nudge_cooldown": False
    }