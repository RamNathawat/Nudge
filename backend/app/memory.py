import json
from datetime import datetime, timedelta
# Assuming models.py and nlp_analysis.py are correctly defined elsewhere
from .models import MemoryEntry
from .nlp_analysis import extract_topic_tags, estimate_emotion

MEMORY_FILE = "user_memory.json"
MEMORY_DECAY_DAYS = 15  # How long before memory starts fading

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_memory(memory):
    # Ensure datetime objects are serialized correctly
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2, default=serialize_datetime)

def add_message_to_memory(user_id, message, sender="user", task_reference=None):
    memory = load_memory()

    emotion, intensity = estimate_emotion(message)
    topic_tags = extract_topic_tags(message)

    timestamp = datetime.now()
    salience = compute_salience(emotion, intensity, message, topic_tags)
    repetition_score = compute_repetition_score(user_id, message)

    new_entry = MemoryEntry(
        user_id=user_id,
        content=message,
        emotion=emotion,
        emotional_intensity=intensity,
        timestamp=timestamp,
        salience=salience,
        repetition_score=repetition_score,
        topic_tags=topic_tags,
        task_reference=task_reference,
        sender=sender # Store sender as well
    ).dict()

    # Ensure user_id has a structure for entries and _traits
    if user_id not in memory:
        memory[user_id] = {"entries": [], "_traits": {}}

    memory[user_id]["entries"].append(new_entry)
    save_memory(memory)

def compute_salience(emotion, intensity, message, tags):
    base = len(message) / 50  # longer = more salient
    emotional_bonus = intensity * 2
    topic_bonus = 0.2 * len(tags)
    return round(base + emotional_bonus + topic_bonus, 2)

def compute_repetition_score(user_id, new_message):
    memory = load_memory().get(user_id, {})
    user_entries = memory.get("entries", []) # Access entries for the specific user
    count = sum(1 for m in user_entries if new_message.strip().lower() in m['content'].strip().lower())
    return round(min(count / 5, 1.0), 2)

def get_relevant_memory(user_id):
    memory = load_memory().get(user_id, {})
    user_entries = memory.get("entries", [])
    relevant = []
    now = datetime.now()

    for entry in user_entries:
        # Convert timestamp string back to datetime object for calculations
        entry_time = datetime.fromisoformat(entry["timestamp"])
        days_old = (now - entry_time).days
        decay = max(0.0, 1.0 - days_old / MEMORY_DECAY_DAYS)

        weight = (
            entry["salience"] * 0.4 +
            entry["emotional_intensity"] * 0.4 +
            entry["repetition_score"] * 0.2
        ) * decay

        if weight > 0.25:
            relevant.append((weight, entry))

    relevant.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in relevant]

def get_user_memory(user_id):
    """Returns all raw memory entries for a given user."""
    memory = load_memory().get(user_id, {})
    return memory.get("entries", [])

def get_recent_history(user_id):
    """Returns the content of the most recent 5 relevant memory entries for a user."""
    relevant_memories = get_relevant_memory(user_id)
    # Return content of the last 5 relevant memories
    return [entry['content'] for entry in relevant_memories[:5]]

def update_trait(user_id, trait_name, value):
    """Updates a specific trait for a user. Traits are stored in a special '_traits' key."""
    memory = load_memory()
    if user_id not in memory:
        memory[user_id] = {"entries": [], "_traits": {}} # Ensure structure exists

    if "_traits" not in memory[user_id]: # Defensive check
        memory[user_id]["_traits"] = {}

    memory[user_id]["_traits"][trait_name] = value
    save_memory(memory)

def get_traits(user_id):
    """Returns all traits for a user."""
    memory = load_memory().get(user_id, {})
    return memory.get("_traits", {}) # Return the traits dictionary