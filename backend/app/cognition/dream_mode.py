# backend/app/cognition/dream_mode.py

import os
import re
import requests
import logging
from datetime import datetime
from pymongo import MongoClient
from collections import Counter
from bson.objectid import ObjectId

# Import the goal manager to create new learning goals
from . import goal_manager
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

def _extract_concept_for_research(question: str) -> str:
    """Uses an LLM to find the core psychological concept in a question."""
    GEMINI_URL = os.getenv("GEMINI_API_URL")
    if not GEMINI_URL:
        return " ".join(question.split()[-4:]) # Fallback to simple keyword extraction

    try:
        prompt = f"""From the following psychological question, extract the core underlying concept as a 2-4 word search query. For example, for 'Why does the user equate success with a loss of freedom?', the answer should be 'psychology of success avoidance'.

Question: "{question}"

Concept:"""
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error(f"[DREAM_CONCEPT_EXTRACTION_ERROR] {e}")
        return " ".join(question.split()[-4:])

def resolve_with_llm(question: str) -> str:
    """Resolves a low-priority curiosity question with a single LLM call."""
    GEMINI_URL = os.getenv("GEMINI_API_URL")
    if not GEMINI_URL: return "Could not resolve due to missing API configuration."
    try:
        prompt = f"Reflect on this internal question and offer a short, thoughtful belief-like answer:\n'{question}'"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        headers = {"Content-Type": "application/json"}
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error(f"[GEMINI_RESOLVE] {e}")
        return "Failed to synthesize an answer."

def review_curiosity(user_id: str):
    stats = {"curiosities_reviewed": 0, "curiosities_resolved": 0, "goals_promoted": 0}
    open_questions = list(curiosity_collection.find({"user_id": user_id, "status": "unresolved"}).sort("priority", -1).limit(5))
    now = datetime.utcnow()

    for q in open_questions:
        stats["curiosities_reviewed"] += 1
        curiosity_collection.update_one({"_id": q["_id"]}, {"$set": {"last_reviewed": now}})

        if q.get("priority", 0) <= 0.4:
            resolved_answer = resolve_with_llm(q["question"])
            if resolved_answer:
                beliefs_collection.insert_one(Belief(user_id=user_id, belief=resolved_answer, confidence=0.6, topic_tags=["curiosity", "introspection"], source="curiosity_resolution").to_mongo())
                curiosity_collection.update_one({"_id": q["_id"]}, {"$set": {"status": "resolved", "resolved_answer": resolved_answer}})
                stats["curiosities_resolved"] += 1
        
        # --- UPGRADED LOGIC: More Proactive Curiosity ---
        # Lowered priority threshold from 0.8 to 0.6
        elif q.get("priority", 0) >= 0.6:
            concept = _extract_concept_for_research(q['question'])
            if concept:
                logger.info(f"Dream Mode: Promoting curiosity to a deep learning goal for concept: '{concept}'")
                goal_manager.create_goal(
                    user_id=user_id,
                    goal_text=f"Master Topic: {concept}",
                    strategy=f"Triggered by high-priority curiosity: {q['question']}",
                    deadline_days=30,
                    goal_type="deep_learning"
                )
                curiosity_collection.update_one({"_id": q["_id"]}, {"$set": {"status": "resolved"}})
                stats["goals_promoted"] += 1

    return stats

def compress_monologues(user_id: str):
    monologues = list(monologue_collection.find({"user_id": user_id}).sort("generated_at", -1).limit(50))
    if not monologues: return {"new_beliefs": 0, "thoughts": []}
    thoughts = [m.get("thought") for m in monologues if "thought" in m]
    common_thoughts = Counter(thoughts).most_common(3)
    stats = {"new_beliefs": 0, "thoughts": thoughts}

    for thought, freq in common_thoughts:
        if freq >= 3:
            belief_text = f"Recurring internal thought: '{thought}'"
            belief = Belief(user_id=user_id, belief=belief_text, confidence=min(0.5 + freq * 0.05, 0.95), topic_tags=["meta", "self-reflection"], source="dream_mode")
            beliefs_collection.insert_one(belief.to_mongo())
            stats["new_beliefs"] += 1
            logger.info(f"[DREAM] Created belief from monologue: {belief_text}")
    return stats

def update_goals(user_id: str):
    now = datetime.utcnow()
    stats = {"goals_failed": 0}
    for goal in goals_collection.find({"user_id": user_id, "status": "in_progress"}):
        deadline = goal.get("deadline")
        if deadline and now > deadline:
            goals_collection.update_one({"_id": goal["_id"]}, {"$set": {"status": "failed", "last_updated": now}})
            logger.warning(f"[DREAM] Goal expired: {goal['goal']}")
            stats["goals_failed"] += 1
    return stats

def generate_self_reflective_monologue(user_id: str, summary: dict):
    thought = f"*Dream mode finished. Reinforced {summary.get('reinforced_beliefs', 0)} beliefs, decayed {summary.get('decayed_beliefs', 0)}, synthesized {summary.get('synthesized_beliefs', 0)} insights, and promoted {summary.get('goals_promoted', 0)} curiosities to research goals. Sleep isn't rest—it’s growth.*"
    monologue = Monologue(user_id=user_id, thought=thought, doubt_level=0.1, desire="meta-insight", emotion_trigger="reflection")
    monologue_collection.insert_one(monologue.to_mongo())
    logger.info("[DREAM] Final reflective monologue stored.")


def run_dream_cycle(user_id: str) -> dict:
    logger.info(f"🌙 [DREAM MODE] Starting memory evolution for {user_id}...")
    summary = {
        "new_beliefs": 0, "reinforced_beliefs": 0, "decayed_beliefs": 0,
        "conflicts_found": 0, "synthesized_beliefs": 0, "goals_failed": 0,
        "curiosities_reviewed": 0, "curiosities_resolved": 0, "goals_promoted": 0
    }

    try:
        thoughts_summary = compress_monologues(user_id)
        summary.update(thoughts_summary)

        summary["reinforced_beliefs"] = reinforce_beliefs(user_id, thoughts_summary["thoughts"])
        summary["decayed_beliefs"] = decay_unused_beliefs(user_id)

        beliefs = list(beliefs_collection.find({"user_id": user_id}))
        contradiction_pairs = detect_contradictory_pairs(beliefs)
        summary["conflicts_found"] = len(contradiction_pairs)
        
        if contradiction_pairs:
            synth = synthesize_contradictions(user_id, contradiction_pairs)
            summary["synthesized_beliefs"] = len(synth)

        summary.update(update_goals(user_id))
        summary.update(review_curiosity(user_id))

        generate_self_reflective_monologue(user_id, summary)

        logger.info(f"✅ [DREAM MODE] Completed cycle for {user_id} with summary: {summary}")
        return {"status": "success", "summary": summary}

    except Exception as e:
        logger.error(f"[DREAM MODE ERROR] {e}", exc_info=True)
        return {"status": "error", "msg": str(e)}