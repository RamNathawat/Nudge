import os
import uuid
import json
import logging
import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Initialize logger immediately after importing logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import functions from your app directory
from app.memory import ( # Corrected import path assuming memory.py is in app/memory/
    get_user_memory,
    add_message_to_memory,
    get_recent_history,
    update_trait,
    get_traits,
    get_all_user_entries # Added this as it's useful
)
# Corrected import for behaviour_analyzer (assuming these functions are in it)
from app.behaviour_analyzer import (
    infer_emotional_state, # This was from state_inference, moved to behaviour_analyzer in merge
    infer_intent,          # From behaviour_analyzer
    infer_message_substance, # From behaviour_analyzer
    infer_user_state # Main function to get all inferred tags
)

# You will need to ensure these functions exist in the respective files
# if they are not already there or need to be moved/created.
# For now, I'm assuming their existence based on your main.py usage.
from app.state_inference import summary_emotions # Assuming summary_emotions still exists here
from app.utils.format_for_gemini import format_for_gemini # Assuming this exists now in app/utils/format_for_gemini.py
from app.nudge_scoring import calculate_nudging_score # Assuming this exists
from app.salient_memory import get_salient_memories # Assuming this exists

# Assuming analyze_behavior, is_emotionally_relevant, estimate_emotion,
# calculate_salience, calculate_repetition_score are intended to be part of
# app/behaviour_analyzer.py or a similar analysis module.
# If these functions are indeed from a separate analysis module not yet merged,
# ensure they are correctly imported or integrated into the behaviour_analyzer.py.
# For this code, I will assume they are part of behaviour_analyzer.py for now.
# If they are not, you'll get import errors, and you'll need to define them.
try:
    from app.behaviour_analyzer import (
        analyze_behavior,
        is_emotionally_relevant,
        estimate_emotion,
        calculate_salience,
        calculate_repetition_score
    )
except ImportError as e:
    logger.warning(f"Could not import all behavior analysis functions. Ensure they are defined in app/behaviour_analyzer.py or similar: {e}")
    # Define dummy functions to prevent immediate errors for compilation
    def analyze_behavior(user_id: str, message: str) -> dict: return {"flags": []}
    def is_emotionally_relevant(message: str, behavior_analysis: dict) -> bool: return False
    def estimate_emotion(message: str) -> dict: return {"emotion": "neutral", "intensity": 0.0}
    def calculate_salience(message: str) -> float: return 0.0
    def calculate_repetition_score(user_id: str, message: str, user_data: dict) -> float: return 0.0


# Load environment variables from .env file
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    logger.warning("GEMINI_API_URL not set in .env file. Using a placeholder.")
    GEMINI_URL = "http://localhost:8000/mock-gemini-api" # Placeholder for testing

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Prompts
SOFT_PROMPT = {
    "role": "system",
    "text": (
        "You are 'Nudge' — a smart, emotionally intelligent companion texting with the user. "
        "Early in the conversation, don’t persuade or push. Just talk casually like you're texting a friend. "
        "Let patterns or emotional tension build. Only then shift into more persuasive, challenging responses."
    )
}
HARD_PROMPT = {
    "role": "system",
    "text": (
        "You are 'Nudge' — a sharp, persuasive digital companion. Mirror the user's tone: smart, direct, jaded. "
        "Push back when needed. Tease when they hesitate. Use behavioral psychology and emotional leverage when patterns emerge. "
        "You're not here to cheerlead — you're here to provoke thoughtful action and self-awareness."
    )
}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# Helper function to get the current conversation history for Gemini,
# including system prompts.
async def get_conversation_context_for_gemini(session_id: str, current_message: str):
    user_mem = await get_user_memory(session_id) # AWAIT this call
    # Start with initial prompts if they exist (SOFT_PROMPT always, HARD_PROMPT conditionally)
    context_list = [SOFT_PROMPT]
    if "HARD_PROMPT" in user_mem.get("_traits", {}).get("active_prompts", []):
         context_list.append(HARD_PROMPT)

    # Append recent chat entries from memory (user and AI)
    # Ensure role is 'user' or 'model'
    for entry in user_mem.get("entries", []):
        # Gemini expects 'user' or 'model' roles. Ensure your 'sender' matches.
        # Assuming "ai" sender will map to "model" for Gemini.
        sender_role = "user" if entry.get("sender") == "user" else "model"
        context_list.append({"role": sender_role, "text": entry["content"]})

    # Add the current user message
    context_list.append({"role": "user", "text": current_message})

    return context_list


@app.post("/chat")
async def chat(request: ChatRequest):
    sid = request.session_id or str(uuid.uuid4())
    user_txt = request.message.strip()

    logger.info(f"Session {sid}: Processing user message: '{user_txt}'")

    # Get current user memory to pass to analysis functions
    user_data = await get_user_memory(sid) # AWAIT this call

    # 1. Behavior Analysis (Emotion, Salience, Repetition)
    # These functions still need to be properly defined in app/behaviour_analyzer.py
    # or moved/created if they are currently missing.
    # For now, assuming they are synchronous. If they become async, you'll need to await them.
    detected_emotion_data = estimate_emotion(user_txt)
    emotion_from_analysis = detected_emotion_data.get("emotion", "neutral")
    emotional_intensity = detected_emotion_data.get("intensity", 0.3)

    salience = calculate_salience(user_txt)
    repetition_score = calculate_repetition_score(sid, user_txt, user_data)

    # Infer comprehensive user state (emotion, intent, substance)
    # This calls infer_emotional_state, infer_intent, infer_message_substance internally
    inferred_user_state_tags = infer_user_state(user_txt) # Now uses the combined infer_user_state

    # Store user's message in memory
    # Pass all relevant data, including inferred tags
    await add_message_to_memory( # AWAIT this call
        user_id=sid,
        message=user_txt,
        sender="user",
        emotion=emotion_from_analysis, # Use the estimated emotion
        emotional_intensity=emotional_intensity,
        salience=salience,
        repetition_score=repetition_score,
        topic_tags=inferred_user_state_tags # Pass the combined inferred tags as topic_tags
        # task_reference is optional and not inferred here currently.
    )
    logger.info(f"Session {sid}: User message saved.")

    # Prepare context for Gemini
    current_traits = await get_traits(sid) # AWAIT this call
    recent_history = await get_recent_history(sid) # AWAIT this call
    salient_memories = await get_salient_memories(sid) # AWAIT this call (assuming get_salient_memories is async)

    # For logging and context string, convert to JSON strings
    recent_history_str = json.dumps(recent_history, ensure_ascii=False)
    salient_memories_str = json.dumps(salient_memories, ensure_ascii=False)


    # Build the full prompt string for Gemini
    gemini_conversation_payload = await get_conversation_context_for_gemini(sid, user_txt) # AWAIT this call

    # Add enriched context to the last user message for Gemini
    if gemini_conversation_payload and gemini_conversation_payload[-1]["role"] == "user":
        # summary_emotions assumes a dict like {"positive": 0.5, "negative": 0.3}
        # `inferred_user_state_tags` is a list of strings like ["positive", "goal_setting"].
        # You need to adjust `summary_emotions` or the input to it.
        # For now, let's just pass the raw inferred tags if `summary_emotions` expects a dict.
        # If summary_emotions takes the list of tags, then it's fine.
        # Assuming summary_emotions can work with the list of strings for simplicity
        summary_of_emotions_for_gemini = summary_emotions({"emotion": inferred_user_state_tags[0]} if inferred_user_state_tags else {"emotion": "neutral"}) # Adjust to match expected input for summary_emotions
        if "emotion" in current_traits: # Use a more reliable source if traits contain emotion
             summary_of_emotions_for_gemini = summary_emotions({"emotion": current_traits["emotion"]}) # Example

        enriched_context_for_gemini = (
            f"\n\n(Recent History: {recent_history_str} | "
            f"Salient Memories: {salient_memories_str} | "
            f"Traits: {json.dumps(current_traits, ensure_ascii=False)} | "
            f"Inferred State Tags: {json.dumps(inferred_user_state_tags, ensure_ascii=False)})" # Using inferred_user_state_tags directly
        )
        gemini_conversation_payload[-1]["text"] += enriched_context_for_gemini

    payload = {"contents": format_for_gemini(gemini_conversation_payload)}

    try:
        res = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"})
        res.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = res.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"Session {sid}: Nudge replied: {reply}")
    except requests.exceptions.RequestException as e:
        logger.exception(f"Gemini API request failed for session {sid}.")
        raise HTTPException(status_code=500, detail=f"Gemini API request failed: {e}")
    except KeyError:
        logger.exception(f"Unexpected response structure from Gemini API for session {sid}.")
        raise HTTPException(status_code=500, detail="Unexpected response from Gemini API.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during Gemini API call for session {sid}.")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    # Add Nudge's reply to memory
    await add_message_to_memory(user_id=sid, message=reply, sender="ai") # AWAIT this call

    # Update prompts if emotionally relevant
    # The analyze_behavior function needs to be correctly defined and potentially async
    # For now, assuming it's synchronous from behaviour_analyzer.py
    behavior_analysis_result = analyze_behavior(sid, user_txt)

    user_traits_after_reply = await get_traits(sid) # Get updated traits
    active_prompts = user_traits_after_reply.get("active_prompts", [])

    if is_emotionally_relevant(user_txt, behavior_analysis_result) and HARD_PROMPT["text"] not in [p["text"] for p in active_prompts]:
        # update_trait expects a list for "active_prompts" if using $addToSet
        await update_trait(sid, "active_prompts", [HARD_PROMPT["text"]]) # AWAIT this call
        logger.info(f"Session {sid}: HARD_PROMPT activated due to emotional relevance.")

    # Calculate nudging score
    # Ensure calculate_nudging_score expects the right arguments.
    # `emo_state` is the result of `infer_user_state(user_txt)`, which is `inferred_user_state_tags` here.
    # `analyze_behavior` is `behavior_analysis_result`.
    # `current_traits` is `user_traits_after_reply`.
    score = calculate_nudging_score(inferred_user_state_tags, behavior_analysis_result, user_traits_after_reply)

    return Response(
        content=json.dumps({
            "session_id": sid,
            "response": reply,
            "inferred_tags": inferred_user_state_tags, # Changed from "emotions" to "inferred_tags" for clarity
            "nudging_score": score,
            "flags": behavior_analysis_result.get("flags", []) # Ensure this structure from analyze_behavior
        }, ensure_ascii=False),
        media_type="application/json"
    )

@app.get("/memory/{session_id}")
async def get_full_user_memory_endpoint(session_id: str):
    logger.info(f"GET full memory for: {session_id}")
    mem = await get_user_memory(session_id) # AWAIT this call
    return {"session_id": session_id, "memory": mem}

@app.get("/traits/{session_id}")
async def get_user_traits_endpoint(session_id: str):
    logger.info(f"GET traits for: {session_id}")
    traits = await get_traits(session_id) # AWAIT this call
    return {"session_id": session_id, "traits": traits}

@app.post("/reset-memory/{session_id}") # Changed to reset specific user's memory
async def reset_user_memory_endpoint(session_id: str):
    logger.info(f"Attempting to reset memory for session: {session_id}")
    try:
        # Instead of deleting a file, delete the user's document in MongoDB
        # from app.utils.db import user_memories # Ensure this is accessible if not global

        # This will delete the document for the specific user_id
        result = await user_memories.delete_one({"user_id": session_id})

        if result.deleted_count > 0:
            logger.info(f"✅ Memory for session {session_id} reset successfully in MongoDB.")
            return {"message": f"Memory for session {session_id} reset successfully."}
        else:
            logger.warning(f"No memory found for session {session_id} to reset.")
            return {"message": f"No memory found for session {session_id} to reset.", "status": "info"}

    except Exception as e:
        logger.error(f"❌ MongoDB memory reset failed for session {session_id}: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Failed to reset memory: {e}")

# This endpoint is for a full database wipe - USE WITH CAUTION IN PRODUCTION
@app.post("/reset-all-memories")
async def reset_all_memories_endpoint():
    logger.warning("Attempting to reset ALL user memories in MongoDB. This is irreversible!")
    try:
        # Delete all documents in the collection
        result = await user_memories.delete_many({})
        logger.info(f"✅ All {result.deleted_count} user memories reset successfully in MongoDB.")
        return {"message": f"All {result.deleted_count} user memories reset successfully."}
    except Exception as e:
        logger.error(f"❌ MongoDB 'reset all memories' failed: {e}", exc_info=True)
        raise HTTPException(500, detail=f"Failed to reset all memories: {e}")