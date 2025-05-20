from datetime import datetime, timedelta
from .memory import load_memory
from .nlp_analysis import is_task_like_message

# Thresholds
AVOIDANCE_REPETITION_THRESHOLD = 2
AVOIDANCE_TIME_THRESHOLD_DAYS = 3

def infer_ongoing_tasks(user_id):
    memory = load_memory().get(user_id, [])
    task_candidates = {}

    for m in memory:
        if not is_task_like_message(m["content"]):
            continue
        task = m["task_reference"] or infer_task_from_text(m["content"])
        if not task:
            continue

        if task not in task_candidates:
            task_candidates[task] = {
                "messages": [],
                "last_mentioned": datetime.min,
                "repetitions": 0,
                "emotion_total": 0.0,
                "emotion_count": 0
            }

        info = task_candidates[task]
        info["messages"].append(m)
        msg_time = datetime.fromisoformat(m["timestamp"])
        if msg_time > info["last_mentioned"]:
            info["last_mentioned"] = msg_time
        info["repetitions"] += 1
        info["emotion_total"] += m.get("emotional_intensity", 0.0)
        info["emotion_count"] += 1

    tasks = []
    for task, data in task_candidates.items():
        if data["emotion_count"] == 0:
            continue
        avg_emotion = data["emotion_total"] / data["emotion_count"]
        days_since_last = (datetime.now() - data["last_mentioned"]).days

        if (data["repetitions"] >= AVOIDANCE_REPETITION_THRESHOLD and 
            days_since_last >= AVOIDANCE_TIME_THRESHOLD_DAYS):
            tasks.append({
                "task": task,
                "avg_emotion": avg_emotion,
                "days_inactive": days_since_last,
                "nudge_intensity": compute_nudge_urgency(data["repetitions"], avg_emotion, days_since_last),
                "examples": data["messages"]
            })

    return sorted(tasks, key=lambda t: t["nudge_intensity"], reverse=True)

def infer_task_from_text(text):
    keywords = ["start", "finish", "build", "launch", "clean", "workout", "quit", "study", "submit"]
    for word in keywords:
        if word in text.lower():
            return text.strip()
    return None

def compute_nudge_urgency(reps, emotion, days_inactive):
    urgency = 0.4 * min(reps / 5, 1) + 0.3 * min(days_inactive / 7, 1) + 0.3 * min(emotion, 1)
    return round(urgency, 2)

def generate_task_nudge(task_data):
    task = task_data["task"]
    intensity = task_data["nudge_intensity"]

    if intensity > 0.7:
        return f"You've been avoiding *{task}* for a while. What's stopping you really? Let's handle it—step by step."
    elif intensity > 0.5:
        return f"Hey, remember *{task}*? It's been lingering for {task_data['days_inactive']} days. Just a little push can get it going."
    else:
        return f"Quick reminder—*{task}* is still open. You’ve thought about it multiple times. Want to revisit it?"

