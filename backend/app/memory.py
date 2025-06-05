from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from .models import MemoryEntry
from .nlp_analysis import extract_topic_tags, estimate_emotion
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["nudge_db"]
entries_collection = db["entries"]
traits_collection = db["traits"]

MEMORY_DECAY_DAYS = 15

def add_message_to_memory(user_id, message, sender="user", task_reference=None):
    emotion, intensity = estimate_emotion(message)
    topic_tags = extract_topic_tags(message)

    timestamp = datetime.utcnow()
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
        sender=sender
    ).dict()

    entries_collection.insert_one(new_entry)

def compute_salience(emotion, intensity, message, tags):
    return round(len(message) / 50 + intensity * 2 + 0.2 * len(tags), 2)

def compute_repetition_score(user_id, new_message):
    user_entries = list(entries_collection.find({"user_id": user_id}))
    count = sum(1 for m in user_entries if new_message.strip().lower() in m['content'].strip().lower())
    return round(min(count / 5, 1.0), 2)

def get_relevant_memory(user_id):
    from datetime import datetime
    user_entries = list(entries_collection.find({"user_id": user_id}))
    relevant = []
    now = datetime.utcnow()

    for entry in user_entries:
        days_old = (now - entry["timestamp"]).days
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
    return list(entries_collection.find({"user_id": user_id}))

def get_recent_history(user_id):
    return [e["content"] for e in get_relevant_memory(user_id)[:5]]

def update_trait(user_id, trait_name, value):
    traits_doc = traits_collection.find_one({"user_id": user_id})
    if traits_doc:
        traits_doc["traits"][trait_name] = value
        traits_collection.update_one(
            {"user_id": user_id},
            {"$set": {"traits": traits_doc["traits"]}}
        )
    else:
        traits_collection.insert_one({"user_id": user_id, "traits": {trait_name: value}})

def get_traits(user_id):
    doc = traits_collection.find_one({"user_id": user_id})
    return doc.get("traits", {}) if doc else {}
