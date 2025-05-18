import json
from pathlib import Path

MEMORY_FILE = Path("backend/app/user_memory.json")

# Load saved memory or initialize fresh memory
def load_memory():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {
        "history": [],
        "traits": {
            "mood": "neutral",
            "common_excuses": [],
            "procrastination_level": 0
        }
    }

# Save memory to disk
def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Memory state (persistent)
user_memory = load_memory()

def add_message_to_memory(message, sender, emotion=None):
    entry = {"sender": sender, "text": message}
    if emotion:
        entry["emotion"] = emotion
    user_memory["history"].append(entry)

    # Limit history length
    if len(user_memory["history"]) > 100:
        user_memory["history"] = user_memory["history"][-100:]

    save_memory(user_memory)

def get_recent_history():
    return user_memory["history"][-10:]

def update_trait(trait, value):
    user_memory["traits"][trait] = value
    save_memory(user_memory)

def get_traits():
    return user_memory["traits"]
