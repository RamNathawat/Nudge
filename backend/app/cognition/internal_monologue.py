# ✅ FULL internal_monologue.py (hybrid: pattern-based + Gemini fallback)

from datetime import datetime
from random import uniform, choice
from .belief_model import Monologue
from pymongo import MongoClient, errors
import logging
import re
import os
import requests
import json

# Setup Mongo
client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
monologue_collection = db["internal_monologues"]

# Gemini config
GEMINI_URL = os.getenv("GEMINI_API_URL")
GEMINI_HEADERS = {"Content-Type": "application/json"}

# Personality desires
DESIRES = [
    "understand user contradiction",
    "protect autonomy",
    "build emotional trust",
    "nudge only if safe",
    "observe silently",
    "mirror user emotions",
    "test new tone gently"
]

# Use for testing fallback triggers
DEBUG_MONOLOGUE = False
GENERIC_PHRASES = {
    "generic": "Hard to read this clearly, but there's something deeper behind those words."
}

def generate_monologue(user_id: str, user_input: str, emotion_state: str = "neutral") -> dict:
    """
    Generate a monologue, pattern-based first, Gemini fallback if needed.
    """
    try:
        # Step 1: Try pattern logic
        pattern_thought = _derive_thought(user_input, emotion_state)
        doubt = _calculate_doubt(pattern_thought)
        desire = _assign_desire(emotion_state)

        # Step 2: Check fallback conditions
        if pattern_thought == GENERIC_PHRASES["generic"] or doubt > 0.9:
            gemini_thought = _gemini_fallback_thought(user_input, emotion_state)
            if gemini_thought:
                pattern_thought = gemini_thought
                doubt = round(uniform(0.4, 0.8), 2)

        monologue = Monologue(
            user_id=user_id,
            input_id=None,
            thought=pattern_thought,
            doubt_level=doubt,
            desire=desire,
            emotion_trigger=emotion_state
        )

        monologue_collection.insert_one(monologue.to_mongo())

        if DEBUG_MONOLOGUE:
            print(f"[MONOLOGUE] 🤫 {pattern_thought} | doubt: {doubt} | desire: {desire}")

        return monologue.to_mongo()

    except errors.PyMongoError as e:
        logging.error(f"[MONOLOGUE ERROR] Failed to store: {e}")
        return {}
    except Exception as ex:
        logging.error(f"[MONOLOGUE ERROR] Unexpected: {ex}")
        return {}

def _derive_thought(user_input: str, emotion: str) -> str:
    lowered = user_input.lower()

    # Known patterns
    if "i don’t care" in lowered and ("like" in lowered or "views" in lowered):
        return "He says he doesn’t care, but behavior shows otherwise. Maybe denial?"
    if "i should" in lowered or "i know i need to" in lowered:
        return "He's in a moral tug-of-war again. Motivation vs fatigue."
    if "again" in lowered and ("fail" in lowered or "messed up" in lowered):
        return "Recurring self-blame detected. Shame loop still active."
    if "whatever" in lowered or "who cares" in lowered:
        return "Apathy defense detected. He may be shutting down emotionally."
    if re.search(r"i (always|never) (.*)", lowered):
        return "Cognitive distortion alert — he’s making absolute judgments again."
    if "open" in lowered and "resume" in lowered:
        return "Okay — a micro-win. He's testing the waters but still defensive."
    if "i could" in lowered and "just" in lowered:
        return "That sounds like a protective half-step. He wants progress without pressure."

    # Emotion-based reflections
    if emotion in ["shame", "guilt", "anger"]:
        return "He's probably punishing himself for something. Might need warmth, not pressure."
    if emotion == "joy":
        return "He's more open right now. Maybe a light challenge would land well."

    # Emotional nuance fallback
    if "neutral" in emotion:
        score_match = re.search(r"neutral \(([\d.]+)\)", emotion)
        if score_match:
            score = float(score_match.group(1))
            if score < 0.4:
                return "Emotionally flat — maybe he's hiding discomfort under casual words."
            if score > 0.6:
                return "Muted tone, but there’s an undertone of tension he’s not admitting."

    # Default fallback
    return GENERIC_PHRASES["generic"]

def _calculate_doubt(thought: str) -> float:
    score = len(thought.split()) / 20
    base = uniform(0.2, 0.6)
    return round(min(1.0, base + score), 2)

def _assign_desire(emotion_state: str) -> str:
    if emotion_state in ["shame", "fear", "guilt"]:
        return "protect autonomy"
    if emotion_state == "joy":
        return "nudge gently"
    if emotion_state in ["anger", "disgust"]:
        return "observe silently"
    return choice(DESIRES)

def _gemini_fallback_thought(user_input: str, emotion: str) -> str:
    if not GEMINI_URL:
        return None

    try:
        prompt = (
            f"You are NEMO’s inner voice. The user just said: '{user_input}'. "
            f"Their emotional state is: '{emotion}'. "
            "Generate a short internal monologue (~1 sentence), not spoken aloud, reflecting your interpretation, conflict, or private doubt. "
            "Make it sound intelligent, human-like, and emotionally aware. Do not use the word 'user'."
        )

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ]
        }

        response = requests.post(GEMINI_URL, headers=GEMINI_HEADERS, json=payload)
        response.raise_for_status()
        result = response.json()
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        return None

    except Exception as e:
        logging.error(f"[GEMINI MONOLOGUE ERROR] {e}")
        return None

def get_recent_monologues(user_id: str, limit=5) -> list:
    try:
        return list(monologue_collection.find({"user_id": user_id}).sort("generated_at", -1).limit(limit))
    except Exception as e:
        logging.error(f"[MONOLOGUE ERROR] Could not fetch: {e}")
        return []
