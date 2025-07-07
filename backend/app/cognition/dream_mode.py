# app/cognition/dream_mode.py

from pymongo import MongoClient
from datetime import datetime
from .belief_model import Belief
from collections import Counter
from bson.objectid import ObjectId
import logging
import re

# Setup
client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
beliefs_collection = db["beliefs"]
monologue_collection = db["internal_monologues"]
curiosity_collection = db["curiosity_traces"]
goals_collection = db["ai_goals"]

logger = logging.getLogger("nemo_dream_mode")
logging.basicConfig(level=logging.INFO)


def run_dream_cycle(user_id: str) -> dict:
    logger.info(f"🌙 [DREAM MODE] Starting memory evolution for {user_id}...")

    try:
        compress_monologues(user_id)
        resolve_conflicting_beliefs(user_id)
        update_goals(user_id)
        review_curiosity(user_id)

        logger.info(f"✅ [DREAM MODE] Completed cycle for {user_id}")
        return {"status": "success", "msg": "Dream cycle completed"}

    except Exception as e:
        logger.error(f"[DREAM MODE ERROR] {e}")
        return {"status": "error", "msg": str(e)}


# ─── MONOLOGUE COMPRESSION ────────────────────────────────────────────────

def compress_monologues(user_id: str):
    last_monologues = list(monologue_collection.find(
        {"user_id": user_id}
    ).sort("generated_at", -1).limit(50))

    if not last_monologues:
        return

    thoughts = [m.get("thought") for m in last_monologues if "thought" in m]
    emotions = [m.get("emotion_trigger", "neutral") for m in last_monologues]

    common_thoughts = Counter(thoughts).most_common(2)
    common_emotions = Counter(emotions).most_common(2)

    for thought, freq in common_thoughts:
        if freq >= 3:
            belief_text = f"Recurring internal thought: '{thought}'"
            belief = Belief(
                user_id=user_id,
                belief=belief_text,
                confidence=min(0.5 + freq * 0.05, 0.95),
                topic_tags=["meta", "self-reflection"],
                source="dream_mode"
            )
            beliefs_collection.insert_one(belief.to_mongo())
            logger.info(f"[DREAM] New belief created from monologue: {belief_text}")


# ─── BELIEF CONFLICT DETECTION ────────────────────────────────────────────

def resolve_conflicting_beliefs(user_id: str):
    beliefs = list(beliefs_collection.find({"user_id": user_id}))
    conflict_pairs = []

    for i, b1 in enumerate(beliefs):
        for j, b2 in enumerate(beliefs):
            if i >= j:
                continue
            if is_contradictory(b1["belief"], b2["belief"]):
                conflict_pairs.append((b1["belief"], b2["belief"]))

    for b1, b2 in conflict_pairs[:3]:  # limit to 3 per cycle
        question = f"Why do I believe both: '{b1}' AND '{b2}'?"
        curiosity_collection.insert_one({
            "user_id": user_id,
            "question": question,
            "status": "unresolved",
            "priority": 0.85,
            "emotion_trigger": "contradiction",
            "created_at": datetime.utcnow(),
            "input_reference": "[dream_mode_conflict]"
        })
        logger.info(f"[DREAM] Belief contradiction flagged: {question}")


def is_contradictory(b1: str, b2: str) -> bool:
    b1_clean = b1.lower()
    b2_clean = b2.lower()

    # Absolute statements conflict (e.g., "always" vs "never")
    if re.search(r"\balways\b", b1_clean) and re.search(r"\bnever\b", b2_clean):
        return True

    # Negation conflict (primitive)
    if "not" in b1_clean and any(word in b1_clean for word in b2_clean.split()):
        return True

    if "not" in b2_clean and any(word in b2_clean for word in b1_clean.split()):
        return True

    return False


# ─── GOAL STATUS EVALUATION ──────────────────────────────────────────────

def update_goals(user_id: str):
    now = datetime.utcnow()
    active_goals = goals_collection.find({
        "user_id": user_id,
        "status": "in_progress"
    })

    for goal in active_goals:
        deadline = goal.get("deadline")
        if deadline and now > deadline:
            goals_collection.update_one(
                {"_id": goal["_id"]},
                {"$set": {"status": "failed", "last_updated": now}}
            )
            logger.warning(f"[DREAM] Goal expired and marked as failed: {goal['goal']}")


# ─── CURIOSITY REVIEW ─────────────────────────────────────────────────────

def review_curiosity(user_id: str):
    open_questions = list(curiosity_collection.find({
        "user_id": user_id,
        "status": "unresolved"
    }).sort("priority", -1).limit(3))

    for q in open_questions:
        curiosity_collection.update_one(
            {"_id": q["_id"]},
            {"$set": {"last_reviewed": datetime.utcnow()}}
        )
        logger.info(f"[DREAM] Reviewing curiosity: {q['question']}")
