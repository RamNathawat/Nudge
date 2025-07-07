# app/cognition/belief_engine.py

from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
beliefs_collection = db["beliefs"]

def form_belief(user_id, belief_text, source="inference", confidence=0.5, topic_tags=None):
    existing = beliefs_collection.find_one({
        "user_id": user_id,
        "belief": belief_text
    })

    if existing:
        new_conf = min(existing["confidence"] + 0.05, 1.0)
        beliefs_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {"confidence": new_conf, "last_updated": datetime.utcnow()}}
        )
        return f"Updated belief: {belief_text} (↑ confidence to {round(new_conf, 2)})"

    belief_doc = {
        "user_id": user_id,
        "belief": belief_text,
        "confidence": confidence,
        "topic_tags": topic_tags or [],
        "source": source,
        "created_at": datetime.utcnow(),
        "last_updated": datetime.utcnow(),
        "history": []
    }
    beliefs_collection.insert_one(belief_doc)
    return f"Stored new belief: {belief_text}"

def get_beliefs(user_id, topic=None):
    query = {"user_id": user_id}
    if topic:
        query["topic_tags"] = topic
    return list(beliefs_collection.find(query))

def belief_confidence(user_id, belief_text):
    doc = beliefs_collection.find_one({"user_id": user_id, "belief": belief_text})
    return doc["confidence"] if doc else None

def detect_conflicting_belief(user_id, belief_text, threshold=0.7):
    # A primitive check: reverse phrasing match
    belief_words = set(belief_text.lower().split())
    all_beliefs = beliefs_collection.find({"user_id": user_id})

    for b in all_beliefs:
        if b["confidence"] < threshold:
            continue
        if belief_words.intersection(set(b["belief"].lower().split())):
            if "not" in b["belief"] or "never" in b["belief"]:
                return b["belief"]
    return None
