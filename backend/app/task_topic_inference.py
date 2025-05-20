import re

def infer_user_state(text: str) -> dict:
    """
    Infer user intent, substance use, and task topic from message text.
    Returns: dict with intent, substance, and task_topic.
    """
    lower = text.lower()

    # Substance Detection
    if any(kw in lower for kw in ["weed", "joint", "high", "stoned"]):
        substance = "weed"
    elif any(kw in lower for kw in ["alcohol", "drunk", "booze", "beer", "vodka"]):
        substance = "alcohol"
    elif any(kw in lower for kw in ["cigarette", "nicotine", "smoke", "vape"]):
        substance = "nicotine"
    else:
        substance = "none"

    # Intent Detection
    if any(kw in lower for kw in ["procrastinate", "delay", "skip", "avoid"]):
        intent = "avoidant"
    elif any(kw in lower for kw in ["finish", "complete", "do this", "get done", "start working"]):
        intent = "productive"
    elif any(kw in lower for kw in ["chill", "relax", "watch", "game", "movie", "binge"]):
        intent = "recreational"
    else:
        intent = "unknown"

    # Task Topic Detection
    if any(kw in lower for kw in ["gym", "workout", "diet", "fit", "exercise", "body"]):
        topic = "health"
    elif any(kw in lower for kw in ["money", "spend", "save", "income", "salary", "debt", "budget"]):
        topic = "finance"
    elif any(kw in lower for kw in ["project", "code", "app", "build", "website", "startup", "feature"]):
        topic = "career"
    elif any(kw in lower for kw in ["relationship", "talk", "crush", "heart", "feelings"]):
        topic = "relationship"
    elif any(kw in lower for kw in ["study", "exam", "college", "test", "assignment", "homework"]):
        topic = "education"
    else:
        topic = "unknown"

    return {
        "intent": intent,
        "substance": substance,
        "task_topic": topic
    }