from typing import Optional, List, Dict

def infer_task_topic(message: str) -> Optional[str]:
    """
    Infers a task or topic from the user's message.
    This is a placeholder and would require more sophisticated NLP.
    """
    message_lower = message.lower()
    if "work" in message_lower or "project" in message_lower:
        return "work_related"
    if "study" in message_lower or "learn" in message_lower:
        return "learning"
    if "health" in message_lower or "exercise" in message_lower:
        return "health_fitness"
    if "goal" in message_lower or "achieve" in message_lower:
        return "personal_goals"
    return None

def infer_ongoing_tasks(user_id: str) -> List[Dict]:
    """
    Placeholder function to infer ongoing tasks for a user.
    In a real system, this would likely involve checking memory for task-related entries,
    or a dedicated task tracking system.
    """
    # For demonstration, returning a dummy task.
    return [{"id": "task_123", "description": "Finish the report", "status": "pending"}]

def generate_task_nudge(task: Dict) -> str:
    """
    Generates a specific nudge for a given task.
    """
    if task["status"] == "pending":
        return f"How's progress on '{task['description']}'? Just checking in."
    return ""