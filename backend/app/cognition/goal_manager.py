# backend/app/cognition/goal_manager.py

from datetime import datetime, timedelta
from typing import Optional
from .belief_model import Goal
from pymongo import MongoClient, errors
import logging

# Get a specific logger instance
logger = logging.getLogger(__name__)

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
goals_collection = db["ai_goals"]

def create_goal(user_id: str, goal_text: str, strategy: Optional[str] = None,
                linked_beliefs=None, deadline_days: int = 7, goal_type: str = "user") -> dict:
    """
    Creates a new goal in the database, now with more explicit parameter setting
    and better logging for reliability.
    """
    try:
        # Check for existing active goals to prevent duplicates
        existing = goals_collection.find_one({
            "user_id": user_id,
            "goal": goal_text,
            "status": {"$in": ["in_progress", "paused"]}
        })
        if existing:
            logger.warning(f"Attempted to create a duplicate active goal: {goal_text}")
            return {"msg": "Goal already exists and is in progress."}

        # Explicitly set all required fields for the Goal model
        goal = Goal(
            user_id=user_id,
            goal=goal_text,
            strategy=strategy,
            linked_beliefs=linked_beliefs or [],
            deadline=datetime.utcnow() + timedelta(days=deadline_days),
            goal_type=goal_type,
            status="in_progress" # Explicitly set the status
        )
        
        result = goals_collection.insert_one(goal.to_mongo())
        
        # Added logging to confirm successful insertion
        if result.inserted_id:
            logger.info(f"✅ Successfully created goal in DB with ID {result.inserted_id}: '{goal_text}'")
            return {"msg": f"Goal created: {goal_text} (Type: {goal_type})"}
        else:
            logger.error(f"[GOAL_MANAGER ERROR] InsertOne failed silently for goal: {goal_text}")
            return {"msg": "Database insert operation failed."}


    except errors.PyMongoError as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return {"msg": "Database error during goal creation"}

def update_goal_status(user_id: str, goal_text: str, status: str) -> dict:
    """Updates the status of an existing goal."""
    try:
        result = goals_collection.update_one(
            {"user_id": user_id, "goal": goal_text},
            {"$set": {"status": status, "last_updated": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            logger.warning(f"Could not find matching goal to update status for: {goal_text}")
            return {"msg": "No matching goal found."}
        logger.info(f"Updated goal status to '{status}' for goal: {goal_text}")
        return {"msg": f"Goal status updated to {status}"}
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return {"msg": "Update failed"}

def get_active_goals(user_id: str) -> list:
    """Gets all active goals intended for the user."""
    try:
        return list(goals_collection.find({
            "user_id": user_id,
            "status": "in_progress",
            "goal_type": "user" 
        }))
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] {e}")
        return []

def get_learning_goals(limit: int = 5) -> list:
    """
    Fetches the oldest, active 'deep_learning' goals for the background agent.
    """
    try:
        return list(goals_collection.find({
            "status": "in_progress",
            "goal_type": "deep_learning"
        }).sort("created_at", 1).limit(limit))
    except Exception as e:
        logging.error(f"[GOAL_MANAGER ERROR] Could not fetch learning goals: {e}")
        return []


def evaluate_goals(user_id: str, user_input: str) -> list:
    """
    Checks if the user's input is related to an existing goal.
    """
    active_goals = get_active_goals(user_id)
    triggered = []

    for goal in active_goals:
        if any(kw in user_input.lower() for kw in goal["goal"].lower().split()):
            triggered.append(goal)

    return triggered