# app/nudge_scoring.py
import random
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from .memory import get_recent_history, get_traits, update_trait
from .behaviour_analyzer import is_emotionally_relevant
from .nlp_analysis import detect_emotion, is_task_like_message # Removed is_question
from .dark_nudge_engine import generate_dark_nudge # Not used here, removing for clarity

# ----------------------------------
# Scoring Parameters (Adjust these weights)
# ----------------------------------
WEIGHTS = {
    "emotional_relevance": 0.3,
    "procrastination": 0.2,
    "resistance": 0.2,
    "user_engagement": 0.1,
    "nudge_fatigue": -0.2, # Negative weight for fatigue
    "safe_space_mode": -1.0, # Strong negative weight if safe space is on
    "task_relevance": 0.2 # New weight for task-related nudging
}

# ----------------------------------
# Nudging Score Calculation (Main)
# ----------------------------------

def calculate_nudging_score(
    user_id: str,
    user_message: str,
    ai_response: str,
    behavior_flags: List[str],
    user_traits: Dict
) -> float:
    """
    Calculates a score indicating how appropriate it is to issue a "nudge" to the user.
    Higher score = more appropriate for a nudge.
    
    Parameters:
    - user_id: The ID of the user.
    - user_message: The user's most recent message.
    - ai_response: The AI's generated response.
    - behavior_flags: List of flags from behavior analysis (e.g., procrastination, resistance).
    - user_traits: Current traits/profile of the user.
    """
    
    score = 0.0

    # 1. Emotional Relevance
    if is_emotionally_relevant(user_message, behavior_flags):
        score += WEIGHTS["emotional_relevance"] * (user_traits.get("emotional_intensity", 0) + 1) # Boost for intensity

    # 2. Procrastination
    if "procrastination" in behavior_flags:
        score += WEIGHTS["procrastination"] * (user_traits.get("procrastination_level", 0.5) + 1) # Boost for level

    # 3. Resistance
    if "resistance" in behavior_flags:
        score += WEIGHTS["resistance"] * (user_traits.get("retreat_count", 0.5) + 1) # Boost for count

    # 4. User Engagement (simple heuristic: more recent messages = more engaged)
    recent_history = get_recent_history(user_id)
    if len(recent_history) >= 5: # Engaged if more than 5 messages recently
        score += WEIGHTS["user_engagement"]

    # 5. Nudge Fatigue (if too many nudges recently)
    last_nudge_time = user_traits.get("last_nudge_sent_at")
    if last_nudge_time:
        # Assuming last_nudge_sent_at is stored in isoformat or datetime object
        if isinstance(last_nudge_time, str):
            try:
                last_nudge_time = datetime.fromisoformat(last_nudge_time)
            except ValueError:
                last_nudge_time = None # Handle invalid format gracefully
        
        if last_nudge_time: # Only proceed if conversion was successful
            cooldown_period = timedelta(minutes=10) # Matches nudge_cooldown_minutes in dark_nudge_engine.py
            if datetime.now() - last_nudge_time < cooldown_period:
                score += WEIGHTS["nudge_fatigue"] # Reduce score if within cooldown

    # 6. Safe Space Mode (strong negative impact)
    if user_traits.get("safe_space_mode", False):
        score += WEIGHTS["safe_space_mode"]

    # 7. Task Relevance
    if is_task_like_message(user_message):
        score += WEIGHTS["task_relevance"]
    
    # Clamp score between 0 and 1 (or other meaningful range)
    return max(0.0, min(score, 1.0)) # Assuming score should be between 0 and 1

# ----------------------------------
# Debugging Helper (Optional)
# ----------------------------------

def explain_nudging_score(
    user_id: str,
    user_message: str,
    ai_response: str,
    behavior_flags: List[str],
    user_traits: Dict
) -> Dict:
    """
    Returns detailed breakdown of how the nudging score was calculated.
    """
    detail = {}
    score = 0.0

    # 1. Emotional Relevance
    is_emotional = is_emotionally_relevant(user_message, behavior_flags)
    emotional_contribution = 0.0
    if is_emotional:
        emotional_contribution = WEIGHTS["emotional_relevance"] * (user_traits.get("emotional_intensity", 0) + 1)
        score += emotional_contribution
    detail["emotional_relevance"] = {"is_relevant": is_emotional, "contribution": emotional_contribution}

    # 2. Procrastination
    is_procrastinating = "procrastination" in behavior_flags
    procrastination_contribution = 0.0
    if is_procrastinating:
        procrastination_contribution = WEIGHTS["procrastination"] * (user_traits.get("procrastination_level", 0.5) + 1)
        score += procrastination_contribution
    detail["procrastination"] = {"detected": is_procrastinating, "contribution": procrastination_contribution}

    # 3. Resistance
    is_resisting = "resistance" in behavior_flags
    resistance_contribution = 0.0
    if is_resisting:
        resistance_contribution = WEIGHTS["resistance"] * (user_traits.get("retreat_count", 0.5) + 1)
        score += resistance_contribution
    detail["resistance"] = {"detected": is_resisting, "contribution": resistance_contribution}

    # 4. User Engagement
    recent_history_len = len(get_recent_history(user_id))
    engagement_contribution = 0.0
    if recent_history_len >= 5:
        engagement_contribution = WEIGHTS["user_engagement"]
        score += engagement_contribution
    detail["user_engagement"] = {"recent_messages": recent_history_len, "contribution": engagement_contribution}

    # 5. Nudge Fatigue
    fatigue_contribution = 0.0
    last_nudge_time = user_traits.get("last_nudge_sent_at")
    within_cooldown = False
    if last_nudge_time:
        if isinstance(last_nudge_time, str):
            try:
                last_nudge_time = datetime.fromisoformat(last_nudge_time)
            except ValueError:
                last_nudge_time = None
        
        if last_nudge_time:
            cooldown_period = timedelta(minutes=10)
            if datetime.now() - last_nudge_time < cooldown_period:
                fatigue_contribution = WEIGHTS["nudge_fatigue"]
                score += fatigue_contribution
                within_cooldown = True
    detail["nudge_fatigue"] = {"last_nudge_time": str(last_nudge_time) if last_nudge_time else None, "within_cooldown": within_cooldown, "contribution": fatigue_contribution}

    # 6. Safe Space Mode
    in_safe_space = user_traits.get("safe_space_mode", False)
    safe_space_contribution = 0.0
    if in_safe_space:
        safe_space_contribution = WEIGHTS["safe_space_mode"]
        score += safe_space_contribution
    detail["safe_space_mode"] = {"enabled": in_safe_space, "contribution": safe_space_contribution}

    # 7. Task Relevance
    is_task_relevant = is_task_like_message(user_message)
    task_relevance_contribution = 0.0
    if is_task_relevant:
        task_relevance_contribution = WEIGHTS["task_relevance"]
        score += task_relevance_contribution
    detail["task_relevance"] = {"is_task_like": is_task_relevant, "contribution": task_relevance_contribution}
    
    final_score = max(0.0, min(score, 1.0))
    detail["final_score"] = final_score
    return detail