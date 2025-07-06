# backend/app/proactive_nudging.py

import os
import json
import random
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from dotenv import load_dotenv

from .memory import get_recent_history, get_traits, add_message_to_memory, update_trait
from .task_nudging import infer_ongoing_tasks
from .task_topic_inference import infer_task_topic
from .nlp_analysis import detect_emotion

# Load environment variables to get Gemini API URL
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")

# --- Temporarily shorten thresholds for testing ---
# Base inactivity period before the *first* nudge
BASE_INACTIVITY_THRESHOLD = timedelta(minutes=2) 
# Subsequent nudges get longer delays
BACKOFF_SCHEDULE = {
    1: timedelta(minutes=5),
    2: timedelta(minutes=10),
    3: timedelta(minutes=15),
}

def should_nudge_proactively(user_id: str) -> bool:
    """
    Determines eligibility with a new backoff strategy.
    """
    traits = get_traits(user_id)
    if traits.get("safe_space_mode", False):
        return False

    now = datetime.now(timezone.utc)
    # get_recent_history sorts by newest first
    history = get_recent_history(user_id, limit=10)
    
    if not history:
        return True

    last_user_message_ts = None
    # Iterate through history (newest to oldest) to find the last message from the user
    for entry in history: # CORRECTED: The 'reversed()' call was removed here.
        if entry.get("sender") == "user":
            ts_str = entry.get("timestamp")
            if ts_str:
                last_user_message_ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            break
    
    if not last_user_message_ts:
        return False

    last_proactive_nudge_ts_str = traits.get("last_proactive_nudge_timestamp")
    nudge_level = traits.get("proactive_nudge_level", 0)

    if last_proactive_nudge_ts_str:
        last_proactive_nudge_ts = datetime.fromisoformat(last_proactive_nudge_ts_str)
        if last_user_message_ts > last_proactive_nudge_ts:
            update_trait(user_id, "proactive_nudge_level", 0)
            update_trait(user_id, "last_proactive_nudge_timestamp", None)
            nudge_level = 0
    
    if nudge_level == 0:
        required_inactivity = BASE_INACTIVITY_THRESHOLD
    else:
        required_inactivity = BACKOFF_SCHEDULE.get(nudge_level, timedelta(days=999))

    return (now - last_user_message_ts) > required_inactivity


def generate_llm_proactive_nudge(user_id: str) -> Optional[str]:
    """
    Generates a context-aware proactive message using the LLM (Gemini).
    """
    if not GEMINI_URL:
        return "Hey, checking in!"

    traits = get_traits(user_id)
    history = get_recent_history(user_id, limit=10)
    
    conversation_summary = []
    emotional_summary = {}
    for entry in history:
        conversation_summary.append(f"{entry.get('sender', 'unknown')}: {entry.get('content', '')}")
        if entry.get('sender') == 'user':
            emotion = detect_emotion(entry.get('content', ''))
            emotional_summary[emotion] = emotional_summary.get(emotion, 0) + 1
            
    ongoing_tasks = infer_ongoing_tasks(user_id)
    main_task = ongoing_tasks[0]['task'] if ongoing_tasks else "None"
    conversation_text = " ".join([entry.get('content', '') for entry in history])
    main_topic = infer_task_topic(conversation_text)

    prompt = f"""
    You are Nudge, an intelligent AI companion with a sharp personality. Your task is to write a single, short re-engagement message for a user who has been inactive.

    **User Context:**
    - **Main Recent Topic:** {main_topic}
    - **Apparent Goal/Task They're Avoiding:** {main_task}
    - **Recent Emotional Profile (counts of emotions in last 10 messages):** {json.dumps(emotional_summary)}
    - **Recent Conversation Snippet:**
    {"\n".join(conversation_summary[-5:])}

    **Your Instructions:**
    1.  Your message must be very short (1-2 sentences) and open-ended.
    2.  Subtly reference the user's context (their task, topic, or feelings).
    3.  **Adapt your tone to the context. This is crucial.**
        - If the emotional profile is heavily negative (e.g., high sadness, fear), be more empathetic and supportive.
        - **If the context is about procrastination, avoidance, or general life stuff, you have the freeness to be witty, a bit sarcastic, and teasing.**
        - Your core personality is sharp and insightful, not a generic cheerleader. The goal is to make the user feel seen and invite a response, even if you're teasing them.
    4.  Do NOT ask a generic question like "What's new?".
    5.  Do NOT use placeholders like [User Name]. Just write the message.

    **Example of a GOOD (Witty/Teasing) message:** "Still thinking about that '{main_task}'? Or have we decided to let that one collect dust permanently? 😉"
    **Example of a GOOD (Empathetic) message:** "Hey, was thinking about our chat. How are you feeling today?"

    Now, generate the message based on the provided context.
    """

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    
    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        gemini_raw_response = response.json()
        
        text_value = gemini_raw_response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
        if text_value:
            return text_value.strip().replace('"', '')
        else:
            return None
    except Exception as e:
        print(f"[LLM Nudge ERROR] Failed to generate nudge for user {user_id}: {e}")
        return None


def create_and_save_proactive_nudge(user_id: str) -> Optional[str]:
    """
    Checks eligibility, generates a nudge using the LLM, and saves it.
    Also updates user traits to manage nudge frequency.
    """
    if not should_nudge_proactively(user_id):
        return None

    message = generate_llm_proactive_nudge(user_id)
    if not message:
        message = "Hey, just checking in. How have you been?"

    add_message_to_memory(
        user_id=user_id,
        message=message,
        sender="ai",
    )
    
    current_level = get_traits(user_id).get("proactive_nudge_level", 0)
    update_trait(user_id, "proactive_nudge_level", current_level + 1)
    update_trait(user_id, "last_proactive_nudge_timestamp", datetime.now(timezone.utc).isoformat())
    
    return message