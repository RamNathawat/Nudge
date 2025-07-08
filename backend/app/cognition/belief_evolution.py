import re
import logging
import requests
import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from .belief_model import Belief

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
beliefs_collection = db["beliefs"]
monologue_collection = db["internal_monologues"]

GEMINI_URL = os.getenv("GEMINI_API_URL")
logger = logging.getLogger("belief_evolution")

# --- REINFORCE BELIEFS BASED ON REPEATED THOUGHTS ---
def reinforce_beliefs(user_id: str, recent_thoughts: list):
    updates = 0
    beliefs = list(beliefs_collection.find({"user_id": user_id}))
    for belief in beliefs:
        belief_text = belief["belief"].lower()
        if any(belief_text in thought.lower() for thought in recent_thoughts):
            new_conf = min(belief.get("confidence", 0.5) + 0.05, 0.99)
            beliefs_collection.update_one(
                {"_id": belief["_id"]},
                {"$set": {"confidence": new_conf, "last_updated": datetime.utcnow()}}
            )
            updates += 1
    return updates

# --- DECAY STALE BELIEFS ---
def decay_unused_beliefs(user_id: str, threshold_days: int = 10):
    threshold = datetime.utcnow() - timedelta(days=threshold_days)
    decay_count = 0
    for belief in beliefs_collection.find({"user_id": user_id, "last_updated": {"$lt": threshold}}):
        new_conf = max(belief.get("confidence", 0.5) - 0.05, 0.1)
        beliefs_collection.update_one(
            {"_id": belief["_id"]},
            {"$set": {"confidence": new_conf, "last_updated": datetime.utcnow()}}
        )
        decay_count += 1
    return decay_count

# --- CONTRADICTION CHECKER ---
def detect_contradictory_pairs(belief_list: list):
    contradictions = []
    for i, b1 in enumerate(belief_list):
        for j, b2 in enumerate(belief_list):
            if i >= j:
                continue
            if is_contradictory(b1["belief"], b2["belief"]):
                contradictions.append((b1, b2))
    return contradictions

def is_contradictory(b1: str, b2: str) -> bool:
    b1 = b1.lower()
    b2 = b2.lower()
    if "not" in b1 and any(word in b1 for word in b2.split()):
        return True
    if "not" in b2 and any(word in b2 for word in b1.split()):
        return True
    if re.search(r"\\balways\\b", b1) and re.search(r"\\bnever\\b", b2):
        return True
    return False

# --- RESOLVE CONTRADICTIONS VIA GEMINI ---
def synthesize_contradictions(user_id: str, contradiction_pairs: list):
    resolutions = []
    for b1, b2 in contradiction_pairs:
        resolved = resolve_with_llm(b1["belief"], b2["belief"])
        if resolved:
            belief = Belief(
                user_id=user_id,
                belief=resolved,
                confidence=0.7,
                topic_tags=["meta", "synthesis", "conflict"],
                source="belief_contradiction_resolver"
            )
            beliefs_collection.insert_one(belief.to_mongo())
            resolutions.append(resolved)
            logger.info(f"[RESOLVED] Belief synthesis: {resolved}")
    return resolutions

def resolve_with_llm(b1: str, b2: str) -> str:
    if not GEMINI_URL:
        return None
    prompt = f"""These two beliefs appear contradictory:
    1. "{b1}"
    2. "{b2}"

Is there a deeper belief that might reconcile them both? Return only the synthesized belief as a short sentence."""
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}

    try:
        res = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        data = res.json()
        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error(f"[GEMINI CONTRADICTION ERROR] {e}")
        return None
