from datetime import datetime, timezone # ADDED: timezone import
from pymongo import MongoClient
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
import os
import json
from typing import List, Dict

from .models import MemoryEntry
from .nlp_analysis import extract_topic_tags, estimate_emotion
from .utils import safe_bson_date

load_dotenv()

# ------------------------
# MongoDB Setup
# ------------------------

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI not set in .env")

client = MongoClient(MONGO_URI)
db = client["nudge_db"]
entries_collection = db["entries"]
traits_collection = db["traits"]

# ------------------------
# Constants
# ------------------------

MEMORY_DECAY_DAYS = 15

# ------------------------
# Core Memory Functions
# ------------------------

def add_message_to_memory(user_id, message, sender="user", task_reference=None, reply_to_id=None):
    sender = "user" if str(sender).lower() == "user" else "ai"
    emotion, intensity = estimate_emotion(message)
    topic_tags = extract_topic_tags(message)
    timestamp = datetime.now(timezone.utc) # CORRECTED LINE: Using timezone-aware UTC datetime
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
        sender=sender,
        reply_to_id=reply_to_id
    ).dict()

    result = entries_collection.insert_one(new_entry)
    return str(result.inserted_id)

def compute_salience(emotion, intensity, message, tags):
    return round(len(message) / 50 + intensity * 2 + 0.2 * len(tags), 2)

def compute_repetition_score(user_id, new_message):
    user_entries = list(entries_collection.find({"user_id": user_id}))
    count = sum(1 for m in user_entries if new_message.strip().lower() in m["content"].strip().lower())
    return round(min(count / 5, 1.0), 2)

def get_relevant_memory(user_id):
    now = datetime.now(timezone.utc) # CORRECTED LINE: Using timezone-aware UTC datetime
    user_entries = list(entries_collection.find({"user_id": user_id}))
    relevant = []

    for entry in user_entries:
        # Using safe_bson_date from .utils module
        entry_ts = safe_bson_date(entry.get("timestamp"))
        
        # Ensure entry_ts is a datetime object before calculating days_old
        # Also ensure comparison is with timezone-aware objects if entry_ts is timezone-aware
        if entry_ts:
            # If entry_ts is naive, make it timezone-aware UTC for consistent comparison
            if entry_ts.tzinfo is None:
                entry_ts = entry_ts.replace(tzinfo=timezone.utc)
            days_old = (now - entry_ts).days
        else:
            days_old = MEMORY_DECAY_DAYS # Fallback if timestamp is missing or invalid

        decay = max(0.0, 1.0 - days_old / MEMORY_DECAY_DAYS)
        weight = (
            entry.get("salience", 0) * 0.4 +
            entry.get("emotional_intensity", 0) * 0.4 +
            entry.get("repetition_score", 0) * 0.2
        ) * decay
        if weight > 0.25:
            relevant.append((weight, entry))

    relevant.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in relevant]

def get_user_memory(user_id, offset=0, limit=20):
    print(f"DEBUG: get_user_memory called for user_id: {user_id}, offset: {offset}, limit: {limit}")
    total_count = entries_collection.count_documents({"user_id": user_id})
    print(f"DEBUG: Total documents found for user {user_id}: {total_count}")

    raw_cursor = entries_collection.find({"user_id": user_id}) \
        .sort("timestamp", -1) \
        .skip(offset) \
        .limit(limit)

    entries = []
    for entry in raw_cursor:
        entries.append({
            **entry,
            "_id": str(entry["_id"]),
            "timestamp": entry.get("timestamp").isoformat() + "Z" if entry.get("timestamp") else None,
        })
    print(f"DEBUG: First 3 entries being returned by get_user_memory: {entries[:3]}")
    has_more = (offset + len(entries)) < total_count
    print(f"DEBUG: hasMore: {has_more}")

    return {
        "messages": entries,
        "hasMore": has_more,
        "totalMessages": total_count
    }
    total_count = entries_collection.count_documents({"user_id": user_id})

    raw_cursor = entries_collection.find({"user_id": user_id}) \
        .sort("timestamp", -1) \
        .skip(offset) \
        .limit(limit)

    entries = []
    for entry in raw_cursor:
        entries.append({
            **entry,
            "_id": str(entry["_id"]),
            "timestamp": entry.get("timestamp").isoformat() + "Z" if entry.get("timestamp") else None,
        })

    has_more = (offset + len(entries)) < total_count

    return {
        "messages": entries,
        "hasMore": has_more,
        "totalMessages": total_count
    }

def get_recent_history(user_id: str, limit: int = 50):
    cursor = entries_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    history = []
    for doc in cursor:
        history.append({
            "content": doc.get("content", ""),
            "sender": doc.get("sender", ""),
            "timestamp": doc.get("timestamp").isoformat() + "Z" if doc.get("timestamp") else None,
        })
    return history[::-1]

# ------------------------
# Trait System
# ------------------------

def update_trait(user_id, trait_name, value):
    traits_doc = traits_collection.find_one({"user_id": user_id})
    if traits_doc:
        traits_doc["traits"][trait_name] = value
        traits_collection.update_one(
            {"user_id": user_id},
            {"$set": {"traits": traits_doc["traits"]}}
        )
    else:
        traits_collection.insert_one({
            "user_id": user_id,
            "traits": {trait_name: value}
        })

def get_traits(user_id):
    doc = traits_collection.find_one({"user_id": user_id})
    return doc.get("traits", {}) if doc else {}

# ------------------------
# Safe Space Mode
# ------------------------

def is_safe_space_mode_enabled(user_id):
    traits = get_traits(user_id)
    return traits.get("safe_space_mode", False)

def set_safe_space_mode(user_id, enabled: bool):
    update_trait(user_id, "safe_space_mode", bool(enabled))

# ------------------------
# Memory Edit / Delete
# ------------------------

def delete_message_by_id(user_id, message_id):
    try:
        obj_id = ObjectId(message_id)
    except InvalidId:
        return False

    result = entries_collection.delete_one({
        "_id": obj_id,
        "user_id": user_id
    })
    return result.deleted_count == 1

def update_message_by_id(user_id, message_id, new_content):
    try:
        obj_id = ObjectId(message_id)
    except InvalidId:
        return False

    result = entries_collection.update_one(
        {"_id": obj_id, "user_id": user_id},
        {"$set": {"content": new_content}}
    )
    return result.modified_count == 1

# Added: json_serializer_for_mongo_types function
def json_serializer_for_mongo_types(obj):
    """
    JSON serializer for objects not serializable by default json code
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")