import json
from datetime import datetime, timedelta
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
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2, default=str)

def add_to_memory(user_id, message, task_reference=None):
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
        task_reference=task_reference
    ).dict()

    memory.setdefault(user_id, []).append(new_entry)
    save_memory(memory)

def compute_salience(emotion, intensity, message, tags):
    base = len(message) / 50  # longer = more salient
    emotional_bonus = intensity * 2
    topic_bonus = 0.2 * len(tags)
    return round(base + emotional_bonus + topic_bonus, 2)

def compute_repetition_score(user_id, new_message):
    memory = load_memory().get(user_id, [])
    count = sum(1 for m in memory if new_message.strip().lower() in m['content'].strip().lower())
    return round(min(count / 5, 1.0), 2)

def get_relevant_memory(user_id):
    memory = load_memory().get(user_id, [])
    relevant = []
    now = datetime.now()

    for entry in memory:
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
