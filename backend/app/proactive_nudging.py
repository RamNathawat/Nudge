# backend/app/proactive_nudging.py

import os
import json
import random
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

from .memory import (
    get_recent_history,
    get_traits,
    add_message_to_memory,
    update_trait,
)
from .task_nudging import infer_ongoing_tasks
from .task_topic_inference import infer_task_topic
from .nlp_analysis import detect_emotion

# --- NEW imports for curiosity-driven nudging ---
from .cognition.curiosity_engine import get_top_unanswered_questions
from .memory import get_last_conversation_topic

# Load environment variables to get Gemini API URL
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")

# --- Temporarily shorten thresholds for testing ---
BASE_INACTIVITY_THRESHOLD = timedelta(minutes=2)
BACKOFF_SCHEDULE = {
    1: timedelta(minutes=5),
    2: timedelta(minutes=10),
    3: timedelta(minutes=15),
}


def should_nudge_proactively(user_id: str) -> bool:
    traits = get_traits(user_id)
    if traits.get("safe_space_mode", False):
        return False

    now = datetime.now(timezone.utc)
    history = get_recent_history(user_id, limit=10)
    if not history:
        return True

    last_user_message_ts = None
    for entry in history:
        if entry.get("sender") == "user":
            ts_str = entry.get("timestamp")
            if ts_str:
                last_user_message_ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            break

    if not last_user_message_ts:
        return False

    last_nudge_ts_str = traits.get("last_proactive_nudge_timestamp")
    level = traits.get("proactive_nudge_level", 0)

    if last_nudge_ts_str:
        last_nudge_ts = datetime.fromisoformat(last_nudge_ts_str)
        # reset level if user spoke after last nudge
        if last_user_message_ts > last_nudge_ts:
            update_trait(user_id, "proactive_nudge_level", 0)
            update_trait(user_id, "last_proactive_nudge_timestamp", None)
            level = 0

    required = BASE_INACTIVITY_THRESHOLD if level == 0 else BACKOFF_SCHEDULE.get(level, timedelta(days=999))
    return (now - last_user_message_ts) > required


def generate_llm_proactive_nudge(user_id: str) -> Optional[str]:
    if not GEMINI_URL:
        return "Hey, checking in!"

    traits = get_traits(user_id)
    history = get_recent_history(user_id, limit=10)

    # Build context
    conversation_summary = []
    emotional_summary = {}
    for entry in history:
        conversation_summary.append(f"{entry.get('sender')}: {entry.get('content')}")
        if entry.get('sender') == 'user':
            em = detect_emotion(entry.get('content', ''))
            emotional_summary[em] = emotional_summary.get(em, 0) + 1

    tasks = infer_ongoing_tasks(user_id)
    main_task = tasks[0]["task"] if tasks else "None"
    conv_text = " ".join(e.get("content", "") for e in history)
    main_topic = infer_task_topic(conv_text)

    prompt = f"""
You are Nudge, an intelligent AI companion with a sharp personality. Your task is to write a single, short re-engagement message for a user who has been inactive.

**User Context:**
- **Main Topic:** {main_topic}
- **Apparent Goal:** {main_task}
- **Emotional Profile:** {json.dumps(emotional_summary)}
- **Recent Snippet:**
{"\n".join(conversation_summary[-5:])}

**Instructions:**
1.  Keep it to 1–2 sentences.
2.  Reference the context subtly.
3.  Adapt tone: empathetic if sadness/fear, witty if procrastination/avoidance.
4.  No generic “What’s new?” or placeholders.

Examples:
- “Still stuck on that '{main_task}'? Or is it collecting dust again? 😉”
- “I’ve been thinking about our chat—how are you feeling today?”

Generate your re-engagement message now.
"""
    try:
        res = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            timeout=20,
        )
        res.raise_for_status()
        data = res.json()
        candidate = data.get("candidates", [{}])[0]
        text = candidate.get("content", {}).get("parts", [{}])[0].get("text")
        return text.strip() if text else None
    except Exception as e:
        # If LLM fails, fallback silently
        return None


def create_and_save_proactive_nudge(user_id: str) -> Optional[str]:
    """
    Generates and saves a proactive nudge.
    Prioritizes:
    1. Curiosity-based nudges
    2. LLM-generated re-engagement
    3. Old fallback behavioral poke
    """
    if not should_nudge_proactively(user_id):
        return None

    message = None

    # 1) Curiosity-driven nudge
    last_topic = get_last_conversation_topic(user_id)
    open_qs = get_top_unanswered_questions(user_id)
    
    if open_qs:
        q = open_qs[0]
        message = (
            f"Hey, I’ve been thinking… remember when we talked about “{last_topic}”? "
            f"That left me wondering: {q['question']} Want to explore that a bit?"
        )

    # 2) LLM-based fallback if no curiosity trace
    if not message:
        message = generate_llm_proactive_nudge(user_id)

    # 3) Final fallback if LLM also fails
    if not message:
        message = "Hey, just checking in. How have you been?"

    # Save the message
    add_message_to_memory(user_id, message, sender="ai")
    current = get_traits(user_id).get("proactive_nudge_level", 0)
    update_trait(user_id, "proactive_nudge_level", current + 1)
    update_trait(user_id, "last_proactive_nudge_timestamp", datetime.now(timezone.utc).isoformat())

    return message
