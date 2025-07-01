import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId
import re
from datetime import datetime

from app.auth import verify_token
from app.memory import (
    get_user_memory, add_message_to_memory, get_recent_history,
    update_trait, get_traits, get_relevant_memory,
    is_safe_space_mode_enabled, set_safe_space_mode,
    delete_message_by_id, update_message_by_id,
    entries_collection, traits_collection
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini, safe_bson_date
from app.nudge_scoring import calculate_nudging_score
from app.dark_nudge_engine import generate_dark_nudge

load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper to serialize ObjectId and datetime for JSON dumping
def json_serializer_for_mongo_types(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class Message(BaseModel):
    message: str

@app.get("/memory")
async def get_memory(user_id: str = Depends(verify_token), offset: int = 0, limit: int = 20):
    memory_entries = get_user_memory(user_id, offset, limit)
    # Convert ObjectId to string for JSON serialization
    for entry in memory_entries:
        if "_id" in entry:
            entry["_id"] = str(entry["_id"])
        if "timestamp" in entry:
            entry["timestamp"] = safe_bson_date(entry["timestamp"])
    return {"memory": memory_entries}

@app.post("/chat")
async def chat(
    message: Message,
    user_id: str = Depends(verify_token)
):
    user_txt = message.message.strip()

    # Add the user's message to memory immediately
    # Removed emotion, emotional_intensity, salience as they are computed inside add_message_to_memory
    add_message_to_memory(
        user_id=user_id,
        message=user_txt,
        sender="user",
    )

    # Analyze user behavior and infer emotional state
    flags = analyze_behavior(user_id, user_txt)
    emo_state = infer_emotional_state(user_txt)
    summary_emotions(emo_state) # This updates user traits based on emo_state
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)

    # Prepare context for Gemini
    context_string, flags, emotions = inject_context(user_txt, user_id) # Re-run for updated flags/emotions if needed, or pass from above
    
    # Get relevant memory entries and recent history
    context_entries = get_relevant_memory(user_id)[:5]
    recent_history_entries = get_recent_history(user_id)

    # Combine recent history and relevant memories
    full_context_entries = recent_history_entries + context_entries

    # Format for Gemini
    formatted_context = format_for_gemini(full_context_entries)
    
    # Add the current user message to the context
    formatted_context.append({"role": "user", "parts": [{"text": user_txt}]})

    # Prepare headers for Gemini API call
    headers = {
        "Content-Type": "application/json"
    }

    response_content = "" # Initialize to empty string

    try:
        # Make the call to Gemini API
        gemini_response_obj = {"contents": formatted_context}
        logger.info(f"Sending to Gemini API: {json.dumps(gemini_response_obj, indent=2)}")

        response = requests.post(GEMINI_URL, headers=headers, json=gemini_response_obj)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        gemini_raw_response = response.json()
        logger.info(f"Raw Gemini API response: {json.dumps(gemini_raw_response, indent=2)}")

        # CORRECTED CODE FOR EXTRACTING GEMINI RESPONSE CONTENT
        if gemini_raw_response and isinstance(gemini_raw_response, dict):
            candidates = gemini_raw_response.get("candidates")
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                first_candidate = candidates[0]
                if first_candidate and isinstance(first_candidate, dict):
                    content_obj = first_candidate.get("content")
                    if content_obj and isinstance(content_obj, dict):
                        parts = content_obj.get("parts")
                        if parts and isinstance(parts, list) and len(parts) > 0:
                            text_part = parts[0]
                            if text_part and isinstance(text_part, dict):
                                text_value = text_part.get("text")
                                if text_value is not None:
                                    response_content = str(text_value).strip()
        # END OF CORRECTION

        if not response_content:
            logger.warning("Gemini API returned an empty or unparseable response content.")
            # Fallback if Gemini response is empty or could not be parsed correctly
            response_content = "I'm sorry, I couldn't generate a response at this time. Could you please try again?"

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Gemini API: {e}")
        raise HTTPException(status_code=500, detail=f"Error from Gemini API: {e}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from Gemini API response: {response.text}")
        raise HTTPException(status_code=500, detail="Invalid JSON response from Gemini API")
    except Exception as e:
        logger.error(f"An unexpected error occurred in chat function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during chat processing.")

    # Add the AI's response to memory
    # Removed emotion, emotional_intensity, salience as they are computed inside add_message_to_memory
    add_message_to_memory(
        user_id=user_id,
        message=response_content,
        sender="ai",
    )
    
    # Return the response to the frontend
    return {"response": response_content}


@app.get("/traits")
async def get_user_traits(user_id: str = Depends(verify_token)):
    traits = get_traits(user_id)
    return {"traits": traits}

@app.delete("/memory/{entry_id}")
async def delete_memory_entry(entry_id: str, user_id: str = Depends(verify_token)):
    if delete_message_by_id(user_id, entry_id):
        return {"message": "Deleted"}
    raise HTTPException(404, "Message not found or not yours")

@app.patch("/memory/{entry_id}")
async def update_memory(entry_id: str, body: dict, user_id: str = Depends(verify_token)):
    if update_message_by_id(user_id, entry_id, body.get("content", "")):
        return {"message": "Updated"}
    raise HTTPException(404, "Message not found or not yours")

@app.post("/reset-memory")
def reset_memory():
    entries_collection.delete_many({})
    return {"message": "All memory entries wiped"}

@app.post("/reset-traits")
def reset_traits():
    traits_collection.delete_many({})
    return {"message": "All user traits wiped"}

@app.post("/safe-space-mode")
def toggle_safe_space(enabled: bool, user_id: str = Depends(verify_token)):
    set_safe_space_mode(user_id, bool(enabled)) # Ensure enabled is a boolean
    return {"status": "ok", "safe_space_mode": enabled}

def inject_context(msg: str, user_id: str):
    flags = analyze_behavior(user_id, msg)
    emo_state = infer_emotional_state(msg)
    summary = summary_emotions(emo_state)
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)
    
    # This context string is no longer directly used for Gemini `contents` but can be for internal logging/context
    return (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(user_id), default=json_serializer_for_mongo_types)} | "
        f"Relevant Memories: {json.dumps(get_relevant_memory(user_id), default=json_serializer_for_mongo_types)} | "
        f"Current User Traits: {json.dumps(get_traits(user_id))} | "
        f"User Behavior Flags: {json.dumps(flags)} | "
        f"Inferred Emotional State: {json.dumps(emo_state)} | "
        f"Safe Space Mode: {is_safe_space_mode_enabled(user_id)})"
    ), flags, emo_state