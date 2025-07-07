# app/cognition/curiosity_engine.py

from datetime import datetime
from pymongo import MongoClient, errors
import logging
import re

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
curiosity_collection = db["curiosity_traces"]

def track_curiosity(user_id: str, user_input: str, emotion_state: str = "neutral") -> dict:
    """
    Analyze the user input for contradictions, confusion, or unknowns.
    If detected, store a curiosity trace for later exploration.
    """
    try:
        question = _infer_question(user_input, emotion_state)
        if not question:
            return {"msg": "No curiosity triggered."}

        doc = {
            "user_id": user_id,
            "question": question,
            "status": "unresolved",
            "emotion_trigger": emotion_state,
            "created_at": datetime.utcnow(),
            "last_reviewed": None,
            "priority": _estimate_priority(emotion_state),
            "input_reference": user_input
        }

        curiosity_collection.insert_one(doc)
        return {"msg": f"Curiosity added: {question}"}

    except errors.PyMongoError as e:
        logging.error(f"[CURIOSITY ENGINE ERROR] {e}")
        return {"msg": "MongoDB error during curiosity tracking"}
    except Exception as e:
        logging.error(f"[CURIOSITY ENGINE ERROR] {e}")
        return {"msg": "Unexpected error"}

def _infer_question(user_input: str, emotion: str) -> str:
    """
    Returns a question NEMO might privately wonder about.
    """
    lowered = user_input.lower()

    if "i don’t care" in lowered and re.search(r"like|view|followers", lowered):
        return "Why does Ram seek validation while claiming not to care?"

    if "i know i should" in lowered and re.search(r"but|can't|don’t", lowered):
        return "What’s blocking Ram from doing what he believes he should?"

    if "i always" in lowered or "i never" in lowered:
        return "Is Ram using cognitive distortions like absolutes in self-assessment?"

    if "i give up" in lowered and emotion in ["shame", "anger", "disgust"]:
        return "Does Ram feel hopeless when things aren’t instantly successful?"

    if "no point" in lowered or "why bother" in lowered:
        return "Has Ram developed a belief that effort won’t change outcomes?"

    return None  # No curiosity triggered

def _estimate_priority(emotion: str) -> float:
    # Prioritize negative-emotion triggers
    if emotion in ["shame", "guilt", "fear"]:
        return 0.9
    if emotion in ["anger", "disgust"]:
        return 0.7
    return 0.3  # neutral or joy

def get_unresolved_questions(user_id: str, limit: int = 5):
    try:
        return list(curiosity_collection.find({
            "user_id": user_id,
            "status": "unresolved"
        }).sort("priority", -1).limit(limit))
    except Exception as e:
        logging.error(f"[CURIOSITY RETRIEVAL ERROR] {e}")
        return []

def mark_question_resolved(question_id: str):
    try:
        curiosity_collection.update_one(
            {"_id": question_id},
            {"$set": {"status": "resolved", "last_reviewed": datetime.utcnow()}}
        )
    except Exception as e:
        logging.error(f"[CURIOSITY RESOLUTION ERROR] {e}")
