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

# --- Added for Proactive Nudging ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.proactive_nudging import create_and_save_proactive_nudge
# ---

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


# --- Proactive Nudging Scheduler ---
scheduler = AsyncIOScheduler()

async def check_for_proactive_nudges():
    """The job that the scheduler will run."""
    logger.info(f"Scheduler running job at {datetime.now()}...")
    
    # Get all unique user IDs from the traits collection
    all_user_ids = [doc['user_id'] for doc in traits_collection.find({}, {'user_id': 1})]

    for user_id in all_user_ids:
        logger.info(f"Checking user {user_id} for proactive nudge...")
        try:
            # This function handles the logic of whether to nudge and saves it to DB
            message = create_and_save_proactive_nudge(user_id)
            if message:
                logger.info(f"Generated and saved proactive nudge for {user_id}: '{message}'")
        except Exception as e:
            logger.error(f"Failed to process proactive nudge for user {user_id}: {e}", exc_info=True)

@app.on_event("startup")
async def startup_event():
    # Run the job every hour. For testing, you can change this to minutes=1
    scheduler.add_job(
        check_for_proactive_nudges,
        trigger=IntervalTrigger(hours=1), # CHANGED FROM hours=1
        id="proactive_nudge_job",
        name="Check for and send proactive nudges",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Proactive Nudge Scheduler started.")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Proactive Nudge Scheduler shut down.")
# --- End of Scheduler Setup ---


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
    # Note: The original code had a bug where it returned a dictionary. 
    # The 'get_user_memory' function in memory.py seems to be designed to return a dictionary with 'messages', 'hasMore', etc.
    # So the following logic is adjusted to work with that structure.
    memory_data = get_user_memory(user_id, offset, limit)
    
    # The memory_data is expected to be a dict like {"messages": [...], "hasMore": ...}
    # We serialize the contents of the 'messages' list.
    if "messages" in memory_data and isinstance(memory_data["messages"], list):
        for entry in memory_data["messages"]:
            if "_id" in entry and isinstance(entry["_id"], ObjectId):
                entry["_id"] = str(entry["_id"])
            if "timestamp" in entry and isinstance(entry["timestamp"], datetime):
                entry["timestamp"] = safe_bson_date(entry["timestamp"])

    # The original function was trying to return just the list, which might be a bug.
    # Returning the whole dictionary as received from get_user_memory is safer.
    return {"memory": memory_data}


@app.post("/chat")
async def chat(
    message: Message,
    user_id: str = Depends(verify_token)
):
    user_txt = message.message.strip()

    add_message_to_memory(
        user_id=user_id,
        message=user_txt,
        sender="user",
    )

    flags = analyze_behavior(user_id, user_txt)
    emo_state = infer_emotional_state(user_txt, user_id) # Passing user_id here as state_inference supports it
    summary = summary_emotions(emo_state)
    if summary: # summary_emotions from state_inference returns a string, not meant to update traits
        pass # The string summary could be logged or used differently if needed
    
    # The trait update loop from the original code seems redundant if state_inference handles it,
    # but we'll keep it for consistency with the provided code.
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)

    # The original inject_context is kept, but it also has redundant logic.
    # For clarity, we'll call it as intended in the original code.
    context_string, flags, emotions = inject_context(user_txt, user_id)
    
    context_entries = get_relevant_memory(user_id)[:5]
    recent_history_entries = get_recent_history(user_id)

    full_context_entries = recent_history_entries + context_entries
    formatted_context = format_for_gemini(full_context_entries)
    
    formatted_context.append({"role": "user", "parts": [{"text": user_txt}]})

    formatted_context.insert(0, {
    "role": "user",
    "parts": [{
        "text": (
            "Important: Keep your replies short, punchy, and direct—no more than 2-3 sentences. "
            "Be concise but still sound like Nudge: emotionally aware, witty, and a little sarcastic if needed. "
            "Cut unnecessary filler, but keep personality intact."
            "be empathetic and supportive, but also witty and a bit sarcastic if you feel the user needs it or is sad or feeling negative emotions . "
        )
    }]
})

    headers = {
        "Content-Type": "application/json"
    }

    response_content = ""

    try:
        gemini_response_obj = {"contents": formatted_context}
        logger.info(f"Sending to Gemini API: {json.dumps(gemini_response_obj, indent=2)}")

        response = requests.post(GEMINI_URL, headers=headers, json=gemini_response_obj)
        response.raise_for_status()
        gemini_raw_response = response.json()
        logger.info(f"Raw Gemini API response: {json.dumps(gemini_raw_response, indent=2)}")

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

        if not response_content:
            logger.warning("Gemini API returned an empty or unparseable response content.")
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

    add_message_to_memory(
        user_id=user_id,
        message=response_content,
        sender="ai",
    )
    
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
    set_safe_space_mode(user_id, bool(enabled))
    return {"status": "ok", "safe_space_mode": enabled}

def inject_context(msg: str, user_id: str):
    flags = analyze_behavior(user_id, msg)
    # The logic in state_inference.py for infer_emotional_state is more complex than the original here.
    # We will use the one from state_inference.py which also updates traits.
    emo_state = infer_emotional_state(msg, user_id) 
    summary = summary_emotions(emo_state)
    
    # The original loop is redundant if infer_emotional_state in state_inference.py already updates traits.
    # for emotion, intensity in emo_state.items():
    #     update_trait(user_id, emotion, intensity)
    
    # This context string is primarily for logging/debugging.
    return (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(user_id), default=json_serializer_for_mongo_types)} | "
        f"Relevant Memories: {json.dumps(get_relevant_memory(user_id), default=json_serializer_for_mongo_types)} | "
        f"Current User Traits: {json.dumps(get_traits(user_id))} | "
        f"User Behavior Flags: {json.dumps(flags)} | "
        f"Inferred Emotional State: {json.dumps(emo_state)} | "
        f"Safe Space Mode: {is_safe_space_mode_enabled(user_id)})"
    ), flags, emo_state