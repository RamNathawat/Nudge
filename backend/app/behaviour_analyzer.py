
import re
from .memory import update_trait, user_memory

def analyze_behavior(message: str):
    message = message.lower()

    # === Excuses Detection ===
    excuses = [
        "i'll do it later",
        "i'm tired",
        "maybe tomorrow",
        "not in the mood",
        "i’m lazy"
    ]
    for excuse in excuses:
        if excuse in message and excuse not in user_memory["traits"]["common_excuses"]:
            user_memory["traits"]["common_excuses"].append(excuse)

    # === Procrastination Detection ===
    if re.search(r"\b(do it (later|tomorrow|next time))\b", message):
        user_memory["traits"]["procrastination_level"] += 1

    # === Mood Detection ===
    if any(word in message for word in ["happy", "excited", "glad", "awesome"]):
        update_trait("mood", "happy")
    elif any(word in message for word in ["sad", "tired", "bored", "depressed", "lazy"]):
        update_trait("mood", "down")
    elif any(word in message for word in ["angry", "frustrated", "annoyed"]):
        update_trait("mood", "frustrated")
