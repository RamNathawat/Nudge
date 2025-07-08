# backend/app/cognition/curiosity_engine.py

from datetime import datetime, timedelta
from pymongo import MongoClient, errors
from bson.objectid import ObjectId
import logging
import re
import difflib
import os
import requests
from dotenv import load_dotenv
from typing import Optional  # Added missing import

# --- NEW: Import the goal manager to create learning goals ---
from . import goal_manager 

load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
curiosity_collection = db["curiosity_traces"]

# Configure logging
logger = logging.getLogger(__name__)  # Added missing logger

# --- Configurable thresholds ---
DUPLICATE_WINDOW_MINUTES = 30
SIMILARITY_THRESHOLD = 0.85


# --- NEW HELPER FUNCTION: To identify knowledge-based topics ---
def _infer_topic_from_input(user_input: str) -> Optional[str]:
    """
    Uses heuristics to identify if the user is asking about a specific topic.
    Returns the topic name if found, otherwise None.
    """
    lowered = user_input.lower()
    # Patterns that suggest a request for knowledge
    patterns = [
        r"tell me about (.+)",
        r"what is (.+)",
        r"what are (.+)",
        r"explain (.+)",
        r"who is (.+)",
        r"do you know about (.+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            # Extract the topic, removing trailing question marks
            topic = match.group(1).strip().rstrip("?").title()
            return topic
    return None


def track_curiosity(user_id: str, user_input: str, emotion_state: str = "neutral", source_id: str = None) -> dict:
    """
    Tracks user-triggered curiosity.
    NEW: First checks for knowledge topics to create learning goals.
    Then, falls back to generating psychological questions about the user.
    """
    # --- NEW LOGIC: Prioritize Topic-Based Learning ---
    topic = _infer_topic_from_input(user_input)
    if topic:
        logger.info(f"Identified knowledge topic: '{topic}'. Creating a deep learning goal.")
        # Create a long-term learning goal for the background agent
        goal_manager.create_goal(
            user_id=user_id,
            goal_text=f"Master Topic: {topic}",
            strategy="Trigger background research and knowledge graph synthesis.",
            deadline_days=90, # Long-term goal
            # Custom type to distinguish from regular goals
            goal_type="deep_learning" 
        )
        return {"msg": f"Curiosity triggered a new learning goal for topic: {topic}"}

    # --- Original Logic: Generate psychological questions ---
    try:
        now = datetime.utcnow()
        question = _infer_question(user_input, emotion_state)

        if not question and GEMINI_URL:
            question = _llm_infer_question(user_input, emotion_state)

        if not question:
            return {"msg": "No psychological curiosity triggered."}

        if _is_duplicate(user_id, question, now):
            return {"msg": "Duplicate psychological curiosity avoided."}

        trace = {
            "user_id": user_id,
            "question": question,
            "status": "unresolved",
            "emotion_trigger": emotion_state,
            "created_at": now,
            "last_reviewed": None,
            "priority": _estimate_priority(emotion_state),
            "urgency": _initial_urgency(emotion_state),
            "input_reference": user_input,
            "source_message_id": source_id,
            "thread_id": _assign_thread_id(question),
            "linked_beliefs": [],
        }

        curiosity_collection.insert_one(trace)
        return {"msg": f"Psychological curiosity added: {question}"}

    except errors.PyMongoError as e:
        logging.error(f"[CURIOSITY ENGINE ERROR] {e}")
        return {"msg": "MongoDB error during curiosity tracking"}
    except Exception as e:
        logging.error(f"[CURIOSITY ENGINE ERROR] {e}")
        return {"msg": "Unexpected error"}


# --- Heuristic rules for psychological questions ---
def _infer_question(user_input: str, emotion: str) -> str:
    lowered = user_input.lower()

    if "i don't care" in lowered and re.search(r"like|view|followers", lowered):
        return "Why does Ram seek validation while claiming not to care?"
    if "i know i should" in lowered and re.search(r"but|can't|don't", lowered):
        return "What's blocking Ram from doing what he believes he should?"
    if "i always" in lowered or "i never" in lowered:
        return "Is Ram using cognitive distortions like absolutes in self-assessment?"
    if "i give up" in lowered and emotion in ["shame", "anger", "disgust"]:
        return "Does Ram feel hopeless when things aren't instantly successful?"
    if "no point" in lowered or "why bother" in lowered:
        return "Has Ram developed a belief that effort won't change outcomes?"

    return None


# --- Fallback LLM question generator ---
def _llm_infer_question(user_input: str, emotion: str) -> str:
    try:
        prompt = f"""
You are an emotionally intelligent AI. Based on the following user input and emotion, infer a curiosity-driven internal question the AI might privately ask to better understand the user's psychology.

User Input: "{user_input}"
Detected Emotion: "{emotion}"

Return only the question.
"""
        response = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logging.error(f"[LLM FALLBACK ERROR] Failed to infer curiosity: {e}")
        return None


# --- Duplicate prevention ---
def _is_duplicate(user_id: str, new_q: str, now: datetime) -> bool:
    recent_traces = curiosity_collection.find({
        "user_id": user_id,
        "created_at": {"$gte": now - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)}
    })

    for trace in recent_traces:
        existing = trace.get("question", "")
        similarity = difflib.SequenceMatcher(None, existing.lower(), new_q.lower()).ratio()
        if similarity > SIMILARITY_THRESHOLD:
            return True
    return False


def _estimate_priority(emotion: str) -> float:
    if emotion in ["shame", "guilt", "fear"]:
        return 0.9
    if emotion in ["anger", "disgust"]:
        return 0.7
    return 0.3


def _initial_urgency(emotion: str) -> float:
    base = _estimate_priority(emotion)
    return round(base * 1.2, 2)  # boost slightly for newness


def _assign_thread_id(question: str) -> str:
    """
    Generate a deterministic thread ID from question text.
    """
    return re.sub(r"[^a-z0-9]+", "-", question.lower())[:40]


# --- Retrieval ---
def get_top_unanswered_questions(user_id: str, limit: int = 5):
    try:
        return list(curiosity_collection.find({
            "user_id": user_id,
            "status": "unresolved"
        }).sort([("urgency", -1), ("created_at", 1)]).limit(limit))
    except Exception as e:
        logging.error(f"[CURIOSITY RETRIEVAL ERROR] {e}")
        return []


def mark_question_resolved(question_id: str):
    try:
        curiosity_collection.update_one(
            {"_id": ObjectId(question_id)},
            {"$set": {"status": "resolved", "last_reviewed": datetime.utcnow()}}
        )
    except Exception as e:
        logging.error(f"[CURIOSITY RESOLUTION ERROR] {e}")