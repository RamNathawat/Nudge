# app/memory/memory.py
import datetime
from typing import Dict, List, Any, Optional

# Import the user_memories from your new db.py
from app.utils.db import user_memories
from app.behaviour_analyzer import infer_user_state # Import inference functions


async def get_user_memory(user_id: str) -> Dict[str, Any]:
    """
    Retrieves a user's memory document from MongoDB.
    If no document exists for the user, a new one is created and inserted.
    """
    user_data = await user_memories.find_one({"user_id": user_id})
    if not user_data:
        user_data = {
            "user_id": user_id,
            "entries": [],
            "_traits": {},
            "_patterns": {}
        }
        await user_memories.insert_one(user_data)
    return user_data


async def add_entry_to_memory(user_id: str, entry: Dict[str, Any]):
    """
    Adds a generic entry to a user's memory entries list.
    This consolidates the functionality of the original `save_entry` and parts of `add_message_to_memory`.
    """
    await user_memories.update_one(
        {"user_id": user_id},
        {"$push": {"entries": entry}},
        upsert=True
    )


async def get_all_user_entries(user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all memory entries for a given user.
    """
    user_data = await get_user_memory(user_id)
    return user_data.get("entries", [])


async def add_message_to_memory(
    user_id: str,
    message: str,
    sender: str,
    emotion: Optional[str] = None,
    emotional_intensity: Optional[float] = None,
    salience: Optional[float] = None,
    repetition_score: Optional[float] = None,
    topic_tags: Optional[List[str]] = None, # This will now receive inferred tags
    task_reference: Optional[str] = None
):
    """
    Adds a message entry to a user's memory and updates relevant traits and patterns.
    This function combines logic from the original `add_message_to_memory` and `save_to_memory_mongo`.
    """
    # The `infer_user_state` is called in main.py, and its output (inferred tags)
    # is passed directly as `topic_tags`. We'll ensure it's a list.
    final_topic_tags = list(set(topic_tags or []))

    message_entry = {
        "user_id": user_id,
        "content": message,
        "sender": sender,
        "timestamp": datetime.datetime.now().isoformat(), # Store as ISO format string
        "emotion": emotion,
        "emotional_intensity": emotional_intensity,
        "salience": salience,
        "repetition_score": repetition_score,
        "topic_tags": final_topic_tags, # Use combined tags including inferred ones
        "task_reference": task_reference,
    }
    # Remove None values from the entry to keep the document cleaner
    message_entry = {k: v for k, v in message_entry.items() if v is not None}

    await user_memories.update_one(
        {"user_id": user_id},
        {"$push": {"entries": message_entry}},
        upsert=True
    )

    # --- Update emotion-topic patterns ---
    # Use the 'emotion' passed directly (which comes from estimate_emotion)
    current_emotion = emotion
    if sender == "user" and current_emotion and final_topic_tags:
        for tag in final_topic_tags:
            # Use dot notation to increment specific pattern counts
            await user_memories.update_one(
                {"user_id": user_id},
                {"$inc": {f"_patterns.emotion_topic.{tag}.{current_emotion}": 1}},
                upsert=True
            )

    # --- Update traits ---
    if sender == "user" and current_emotion:
        await user_memories.update_one(
            {"user_id": user_id},
            {"$inc": {f"_traits.emotion_frequency.{current_emotion}": 1}},
            upsert=True
        )

    if sender == "user":
        msg_lower = message.lower()
        if current_emotion in ["avoidance", "tired", "lazy"] or any(
            key in msg_lower for key in ["later", "not now", "another time", "tomorrow"]
        ):
            await user_memories.update_one(
                {"user_id": user_id},
                {"$inc": {"_traits.procrastination_tendency": 1}},
                upsert=True
            )
        # Check for task resistance using inferred tags as well
        if current_emotion in ["resistance", "angry", "frustration"] and any(
            tag in final_topic_tags for tag in ["task", "problem", "goal_setting"] # Added inferred tags that relate to tasks
        ):
            await user_memories.update_one(
                {"user_id": user_id},
                {"$inc": {"_traits.task_resistance": 1}},
                upsert=True
            )


async def get_recent_history(user_id: str, count: int = 5) -> List[Dict[str, str]]:
    """
    Retrieves the most recent messages for a user, formatted for chat history.
    """
    user_data = await get_user_memory(user_id)
    history = user_data.get("entries", [])[-count:]
    return [{"role": entry["sender"], "text": entry["content"]} for entry in history]


async def update_trait(user_id: str, trait_key: str, trait_value: Any):
    """
    Updates a specific trait for a user. Handles 'active_prompts' specially.
    """
    if trait_key == "active_prompts" and isinstance(trait_value, list):
        # Use $addToSet with $each to add multiple unique items to an array
        await user_memories.update_one(
            {"user_id": user_id},
            {"$addToSet": {f"_traits.{trait_key}": {"$each": trait_value}}},
            upsert=True
        )
    else:
        # For other traits, simply set the value
        await user_memories.update_one(
            {"user_id": user_id},
            {"$set": {f"_traits.{trait_key}": trait_value}},
            upsert=True
        )


async def get_traits(user_id: str) -> Dict[str, Any]:
    """
    Retrieves all traits for a user.
    """
    user_data = await get_user_memory(user_id)
    return user_data.get("_traits", {})


async def get_memory_by_tag(user_id: str, tag: str) -> List[Dict]:
    """
    Fetches memory entries for a user that contain a specific tag.
    """
    document = await user_memories.find_one({"user_id": user_id})
    if not document:
        return []

    # Filter entries in Python (consider using MongoDB aggregation for large datasets)
    return [entry for entry in document.get("entries", []) if tag in entry.get("topic_tags", [])]