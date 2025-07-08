# backend/app/cognition/goal_manager.py

from datetime import datetime, timedelta
from typing import Optional
from .belief_model import Goal
from pymongo import MongoClient, errors
import logging

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
goals_collection = db["ai_goals"]

# --- MODIFIED: Added goal_type parameter ---
def create_goal(user_id: str, goal_text: str, strategy: Optional[str] = None,
                linked_beliefs=None, deadline_days: int = 7, goal_type: str = "user") -> dict:
    try:
        existing = goals_collection.find_one({
            "user_id": user_id,
            "goal": goal_text,
            "status": {"$in": ["in_progress", "paused"]}
        })
        if existing:
            return {"msg": "Goal already exists and is in progress."}

        goal = Goal(
            user_id=user_id,
            goal=goal_text,
            strategy=strategy,
            linked_beliefs=linked_beliefs or [],
            deadline=datetime.utcnow() + timedelta(days=deadline_days),
            goal_type=goal_type # Save the new goal type
        )
        goals_collection.insert_one(goal.to_mongo())
        return {"msg": f"Goal created: {goal_text} (Type: {goal_type})"}

    except errors.PyMongoError as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return {"msg": "Database error during goal creation"}

def update_goal_status(user_id: str, goal_text: str, status: str) -> dict:
    try:
        result = goals_collection.update_one(
            {"user_id": user_id, "goal": goal_text},
            {"$set": {"status": status, "last_updated": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            return {"msg": "No matching goal found."}
        return {"msg": f"Goal status updated to {status}"}
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return {"msg": "Update failed"}

def get_active_goals(user_id: str) -> list:
    try:
        # This function now correctly fetches only user-facing goals
        return list(goals_collection.find({
            "user_id": user_id,
            "status": "in_progress",
            "goal_type": "user" 
        }))
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return []

# --- NEW FUNCTION: For the background learning agent ---
def get_learning_goals(limit: int = 1) -> list:
    """
    Fetches the oldest, active 'deep_learning' goals for the background agent to work on.
    """
    try:
        # Fetches goals across all users, as the learning agent is a global worker
        return list(goals_collection.find({
            "status": "in_progress",
            "goal_type": "deep_learning"
        }).sort("created_at", 1).limit(limit)) # Sort by oldest first
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] Could not fetch learning goals: {e}")
        return []


def evaluate_goals(user_id: str, user_input: str) -> list:
    """
    Check if the user's input is related to an existing goal.
    Return relevant goals that should react.
    """
    active_goals = get_active_goals(user_id)
    triggered = []

    for goal in active_goals:
        if any(kw in user_input.lower() for kw in goal["goal"].lower().split()):
            triggered.append(goal)

    return triggered