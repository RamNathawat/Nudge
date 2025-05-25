# app/behaviour_analyzer.py
from typing import List

# Determine user's emotional state from the message
def infer_emotional_state(message: str) -> str:
    lower_msg = message.lower()
    if any(word in lower_msg for word in ["happy", "great", "good", "awesome", "fantastic", "excited"]):
        return "positive"
    elif any(word in lower_msg for word in ["sad", "depressed", "unhappy", "bad", "terrible", "upset", "lonely"]):
        return "negative"
    elif any(word in lower_msg for word in ["angry", "mad", "furious", "annoyed", "pissed"]):
        return "angry"
    elif any(word in lower_msg for word in ["anxious", "worried", "nervous", "scared"]):
        return "anxious"
    else:
        return "neutral"

# Determine user intent from the message
def infer_intent(message: str) -> str:
    lower_msg = message.lower()
    if "i want" in lower_msg or "i need" in lower_msg or "i'm trying to" in lower_msg:
        return "goal_setting"
    elif "i feel like" in lower_msg or "i don't want" in lower_msg:
        return "avoidance"
    elif "how do i" in lower_msg or "can you help" in lower_msg:
        return "help_request"
    else:
        return "casual"

# Determine message substance based on content
def infer_message_substance(message: str) -> str:
    lower_msg = message.lower()
    if any(word in lower_msg for word in ["routine", "habit", "every day", "daily", "schedule"]):
        return "routine"
    elif any(word in lower_msg for word in ["problem", "issue", "struggle", "challenge", "blocker"]):
        return "problem"
    elif any(word in lower_msg for word in ["idea", "plan", "project", "goal"]):
        return "goal"
    elif any(word in lower_msg for word in ["nothing", "bored", "meh", "whatever"]):
        return "low_substance"
    else:
        return "general"

# Combine all inference functions and return tags
def infer_user_state(message: str) -> List[str]:
    emotion = infer_emotional_state(message)
    intent = infer_intent(message)
    substance = infer_message_substance(message)
    return [emotion, intent, substance]