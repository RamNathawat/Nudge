import os
import re
import requests
import logging
from datetime import datetime
from pymongo import MongoClient
from collections import Counter
from bson.objectid import ObjectId

from .belief_model import Belief, Monologue
from .belief_evolution import (
    reinforce_beliefs,
    decay_unused_beliefs,
    detect_contradictory_pairs,
    synthesize_contradictions
)


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
    summary = {
        "new_beliefs": 0,
        "reinforced_beliefs": 0,
        "decayed_beliefs": 0,
        "conflicts_found": 0,
        "synthesized_beliefs": 0,
        "goals_failed": 0,
        "curiosities_reviewed": 0,
        "curiosities_resolved": 0,
        "goals_promoted": 0
    }

    try:
        thoughts = compress_monologues(user_id)
        summary["new_beliefs"] = thoughts["new_beliefs"]

        summary["reinforced_beliefs"] = reinforce_beliefs(user_id, thoughts["thoughts"])
        summary["decayed_beliefs"] = decay_unused_beliefs(user_id)

        beliefs = list(beliefs_collection.find({"user_id": user_id}))
        contradiction_pairs = detect_contradictory_pairs(beliefs)
        summary["conflicts_found"] = len(contradiction_pairs)
        synth = synthesize_contradictions(user_id, contradiction_pairs)
        summary["synthesized_beliefs"] = len(synth)

        summary.update(update_goals(user_id))
        summary.update(review_curiosity(user_id))

        generate_self_reflective_monologue(user_id, summary)

        logger.info(f"✅ [DREAM MODE] Completed cycle for {user_id}")
        return {"status": "success", "summary": summary}

    except Exception as e:
        logger.error(f"[DREAM MODE ERROR] {e}")
        return {"status": "error", "msg": str(e)}
from pymongo import MongoClient
from datetime import datetime
from .belief_model import Belief, Monologue
from .belief_evolution import (
    reinforce_beliefs,
    decay_unused_beliefs,
    detect_contradictory_pairs,
    synthesize_contradictions
)
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

def compress_monologues(user_id: str):
    monologues = list(monologue_collection.find(
        {"user_id": user_id}
    ).sort("generated_at", -1).limit(50))

    thoughts = [m.get("thought") for m in monologues if "thought" in m]
    emotions = [m.get("emotion_trigger", "neutral") for m in monologues]

    common_thoughts = Counter(thoughts).most_common(2)
    stats = {"new_beliefs": 0, "thoughts": thoughts}

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
            stats["new_beliefs"] += 1
            logger.info(f"[DREAM] Created belief from monologue: {belief_text}")

    return stats
def update_goals(user_id: str):
    now = datetime.utcnow()
    stats = {"goals_failed": 0}

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
            logger.warning(f"[DREAM] Goal expired: {goal['goal']}")
            stats["goals_failed"] += 1

    return stats

def run_dream_cycle(user_id: str) -> dict:
    logger.info(f"🌙 [DREAM MODE] Starting memory evolution for {user_id}...")
    summary = {
        "new_beliefs": 0,
        "reinforced_beliefs": 0,
        "decayed_beliefs": 0,
        "conflicts_found": 0,
        "synthesized_beliefs": 0,
        "goals_failed": 0,
        "curiosities_reviewed": 0,
        "curiosities_resolved": 0,
        "goals_promoted": 0
    }

    try:
        thoughts = compress_monologues(user_id)
        summary["new_beliefs"] = thoughts["new_beliefs"]

        summary["reinforced_beliefs"] = reinforce_beliefs(user_id, thoughts["thoughts"])
        summary["decayed_beliefs"] = decay_unused_beliefs(user_id)

        beliefs = list(beliefs_collection.find({"user_id": user_id}))
        contradiction_pairs = detect_contradictory_pairs(beliefs)
        summary["conflicts_found"] = len(contradiction_pairs)
        synth = synthesize_contradictions(user_id, contradiction_pairs)
        summary["synthesized_beliefs"] = len(synth)

        summary.update(update_goals(user_id))
        summary.update(review_curiosity(user_id))

        generate_self_reflective_monologue(user_id, summary)

        logger.info(f"✅ [DREAM MODE] Completed cycle for {user_id}")
        return {"status": "success", "summary": summary}

    except Exception as e:
        logger.error(f"[DREAM MODE ERROR] {e}")
        return {"status": "error", "msg": str(e)}
def review_curiosity(user_id: str):
    stats = {
        "curiosities_reviewed": 0,
        "curiosities_resolved": 0,
        "goals_promoted": 0
    }

    open_questions = list(curiosity_collection.find({
        "user_id": user_id,
        "status": "unresolved"
    }).sort("priority", -1).limit(5))

    now = datetime.utcnow()
    for q in open_questions:
        stats["curiosities_reviewed"] += 1
        curiosity_collection.update_one(
            {"_id": q["_id"]},
            {"$set": {"last_reviewed": now}}
        )

        if q.get("priority", 0) <= 0.4:
            resolved = resolve_with_llm(q["question"])
            if resolved:
                curiosity_collection.update_one(
                    {"_id": q["_id"]},
                    {"$set": {
                        "status": "resolved",
                        "resolved_answer": resolved,
                        "last_reviewed": now
                    }}
                )
                belief = Belief(
                    user_id=user_id,
                    belief=resolved,
                    confidence=0.6,
                    topic_tags=["curiosity", "introspection"],
                    source="curiosity_resolution"
                )
                beliefs_collection.insert_one(belief.to_mongo())
                stats["curiosities_resolved"] += 1

        elif q.get("priority", 0) >= 0.8:
            goal = {
                "user_id": user_id,
                "goal": f"Answer: {q['question']}",
                "status": "in_progress",
                "source": "dream_mode_promotion",
                "created_at": now
            }
            goals_collection.insert_one(goal)
            stats["goals_promoted"] += 1

    return stats

def resolve_with_llm(question: str) -> str:
    GEMINI_URL = os.getenv("GEMINI_API_URL")
    if not GEMINI_URL:
        return None
    try:
        prompt = f"Reflect on this internal question and offer a short, thoughtful belief-like answer:\n'{question}'"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error(f"[GEMINI_RESOLVE] {e}")
        return None

def generate_self_reflective_monologue(user_id: str, summary: dict):
    thought = f"*Dream mode finished. Reinforced {summary['reinforced_beliefs']} beliefs, decayed {summary['decayed_beliefs']}, synthesized {summary['synthesized_beliefs']} insights. Sleep isn't rest—it’s growth.*"
    monologue = Monologue(
        user_id=user_id,
        input_id=None,
        thought=thought,
        doubt_level=0.4,
        desire="meta-insight",
        emotion_trigger="reflection"
    )
    monologue_collection.insert_one(monologue.to_mongo())
    logger.info(f"[DREAM] Final reflective monologue stored.")
