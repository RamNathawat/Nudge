from .storage import save_memory, load_memory

# Load saved memory or initialize defaults safely
user_memory = load_memory()

# Ensure user_memory is a dictionary
if not isinstance(user_memory, dict):
    user_memory = {}

# Ensure history exists
if "history" not in user_memory or not isinstance(user_memory["history"], list):
    user_memory["history"] = []

# Ensure traits exist and have all required fields
if "traits" not in user_memory or not isinstance(user_memory["traits"], dict):
    user_memory["traits"] = {}

traits = user_memory["traits"]

if "mood" not in traits:
    traits["mood"] = "neutral"
if "common_excuses" not in traits:
    traits["common_excuses"] = []
if "procrastination_level" not in traits:
    traits["procrastination_level"] = 0

# ✅ Ensure emotional_state exists
if "emotional_state" not in user_memory or not isinstance(user_memory["emotional_state"], dict):
    user_memory["emotional_state"] = {
        "mood": "neutral",
        "substance": None,
        "energy": None,
        "intent": None
    }


def add_message_to_memory(message, sender):
    user_memory["history"].append({"sender": sender, "text": message})

    # Optional: Limit memory size
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


# ✅ New functions: Emotional State
def update_emotional_state(mood=None, substance=None, energy=None, intent=None):
    if "emotional_state" not in user_memory:
        user_memory["emotional_state"] = {}
    
    if mood:
        user_memory["emotional_state"]["mood"] = mood
    if substance:
        user_memory["emotional_state"]["substance"] = substance
    if energy:
        user_memory["emotional_state"]["energy"] = energy
    if intent:
        user_memory["emotional_state"]["intent"] = intent

    save_memory(user_memory)


def get_emotional_state():
    return user_memory.get("emotional_state", {})
