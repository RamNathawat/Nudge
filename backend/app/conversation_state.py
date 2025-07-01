# app/conversation_state.py

from app.memory import get_traits, update_trait, get_recent_history

def infer_conversation_mode(user_id: str, history_limit: int = 10) -> str:
    """
    Infers the user's current conversation mode based on recent message history and user traits.
    Modes: debate, emotional_vent, task_mode, casual, safe_space, unknown
    """
    history = get_recent_history(user_id, limit=history_limit)
    combined_text = " ".join(entry.get("content", "").lower() for entry in history)

    # Priority: Safe Space Mode always overrides
    traits = get_traits(user_id)
    if traits.get("safe_space_mode"):
        return "safe_space"

    # Mode heuristics
    if any(kw in combined_text for kw in ["debate", "argue", "counterpoint", "rebuttal", "let's discuss"]):
        return "debate"

    if any(kw in combined_text for kw in ["vent", "frustrated", "overwhelmed", "emotion", "feel like", "feeling", "sad", "stressed"]):
        return "emotional_vent"

    if any(kw in combined_text for kw in ["task", "goal", "next step", "todo", "action item", "plan", "deadline", "work on"]):
        return "task_mode"

    if any(kw in combined_text for kw in ["lol", "funny", "haha", "meme", "bro", "buddy", "friend", "lmao", "😂", "😁"]):
        return "casual"

    return "unknown"

def update_conversation_mode(user_id: str):
    """
    Updates the user's conversation_mode trait.
    """
    mode = infer_conversation_mode(user_id)
    update_trait(user_id, "conversation_mode", mode)
