from .storage import save_memory, load_memory

# Load saved memory or initialize default
user_memory = load_memory() or {
    "history": [],
    "traits": {
        "mood": "neutral",
        "common_excuses": [],
        "procrastination_level": 0
    }
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
