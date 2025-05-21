import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Import functions from your custom modules
from app.memory import (
    get_user_memory,
    add_message_to_memory,
    get_recent_history,
    update_trait,
    get_traits
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini # This file is crucial for Gemini API formatting
from app.nudge_scoring import calculate_nudging_score

# Load environment variables from .env file
load_dotenv()

# --- IMPORTANT: Ensure GEMINI_API_URL is set in your .env file correctly ---
# Example .env content:
# GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=YOUR_ACTUAL_GEMINI_API_KEY_HERE
GEMINI_URL = os.getenv("GEMINI_API_URL")

# Raise an error if the API URL is not found, preventing the app from starting with a missing critical dependency
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env. Please check your .env file.")

# Initialize FastAPI app
app = FastAPI()

# Configure CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # WARNING: For production, specify your frontend's domain(s) instead of "*"
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define system prompts for the AI's persona and tone
SOFT_PROMPT = {
    "role": "system", # Note: Gemini API often treats system prompts as part of the user turn or initial context
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

# Pydantic model for incoming chat requests
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None # Optional session ID for continuous conversations

# In-memory dictionary to store conversation history for each session
# In a production app, this would typically be backed by a persistent database (e.g., Redis, PostgreSQL)
conversations: Dict[str, List[Dict[str,str]]] = {}

# Configure logging for better visibility into application flow
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Helper function to process and inject emotional/behavioral context into the conversation
def inject_emotional_context(message: str, sid: str) -> tuple[str, List[str], Dict[str, float]]:
    """
    Analyzes the user's message, infers emotional state, and gathers relevant memory/traits
    to create a context string for the AI.
    """
    # Analyze user behavior and get flags (e.g., procrastination, resistance)
    flags = analyze_behavior(sid, message) # Pass session_id to analyze_behavior

    # Infer the user's emotional state and get a summary
    emo_state = infer_emotional_state(message)
    summary = summary_emotions(emo_state)

    # Update user traits in memory based on inferred emotions
    # emo_state is a dict like {"emotion_name": intensity_value}
    for emotion_name, intensity_value in emo_state.items():
        update_trait(sid, emotion_name, intensity_value) # Store intensity as a trait

    # Construct the context string to be appended to the user's message for the AI
    # This provides the AI with recent history, current traits, and emotional summary
    context = (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(sid))} | "
        f"User Traits: {json.dumps(get_traits(sid))} | "
        f"Inferred Emotions: {summary})"
    )
    return context, flags, emo_state

@app.post("/chat")
async def chat(request: ChatRequest): # Use async def for FastAPI endpoints
    logger.info(f"Received chat request from session: {request.session_id}")

    # Generate a new session ID if one is not provided (for new conversations)
    sid = request.session_id or str(uuid.uuid4())
    # Initialize conversation history for the session with the soft prompt if it's new
    conversations.setdefault(sid, [SOFT_PROMPT])

    user_txt = request.message.strip()
    # Add the user's message to persistent memory
    add_message_to_memory(user_id=sid, message=user_txt, sender="user")
    logger.info(f"Session {sid}: User message: '{user_txt}'")

    # Inject emotional and behavioral context into the user's message
    context_string, flags, emotions = inject_emotional_context(user_txt, sid)
    user_entry_for_gemini = {"role": "user", "text": user_txt + context_string}
    # Add the user's message (with context) to the in-memory conversation buffer
    conversations[sid].append(user_entry_for_gemini)

    # Logic for dynamic tone shift (e.g., from SOFT_PROMPT to HARD_PROMPT)
    if is_emotionally_relevant(user_txt, flags) and HARD_PROMPT not in conversations[sid]:
        # If the SOFT_PROMPT is at the beginning, insert HARD_PROMPT right after it.
        # This ensures system prompts are always at the start of the conversation.
        if conversations[sid] and conversations[sid][0] == SOFT_PROMPT:
            conversations[sid].insert(1, HARD_PROMPT)
            logger.info(f"Session {sid}: Tone shifted to HARD_PROMPT.")
        else:
            # Fallback: if soft prompt isn't at index 0, just append hard prompt.
            # This case should ideally not happen if prompts are managed strictly.
            conversations[sid].append(HARD_PROMPT)
            logger.warning(f"Session {sid}: HARD_PROMPT appended, SOFT_PROMPT not found at index 0.")

    # Select the last 12 entries for the Gemini API call to provide context
    # Adjust this number based on desired context length and API token limits
    convo_slice_for_gemini = conversations[sid][-12:]

    # Format the conversation slice according to Gemini API's requirements
    payload = {"contents": format_for_gemini(convo_slice_for_gemini)}

    try:
        # Make the API call to Gemini
        res = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"})
        res.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = res.json()

        # Extract the AI's reply from the Gemini response
        # This path might vary slightly based on Gemini's exact response structure
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(f"Session {sid}: Received AI response: '{reply}'")

    except requests.exceptions.HTTPError as errh:
        logger.error(f"Session {sid}: HTTP Error: {errh} - Response: {errh.response.text if errh.response else 'N/A'}", exc_info=True)
        raise HTTPException(502, detail=f"❌ Gemini API HTTP error: {errh.response.text if errh.response else 'N/A'}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"Session {sid}: Connection Error: {errc}", exc_info=True)
        raise HTTPException(503, detail="❌ Gemini API connection error. Please check network or API endpoint.")
    except requests.exceptions.Timeout as errt:
        logger.error(f"Session {sid}: Timeout Error: {errt}", exc_info=True)
        raise HTTPException(504, detail="❌ Gemini API request timed out.")
    except requests.exceptions.RequestException as err:
        logger.error(f"Session {sid}: General Request Error: {err}", exc_info=True)
        raise HTTPException(500, detail="❌ An unexpected error occurred while calling Gemini API.")
    except KeyError as ke:
        logger.error(f"Session {sid}: Malformed Gemini API response (KeyError): {ke} - Response data: {data}", exc_info=True)
        raise HTTPException(502, detail="❌ Malformed Gemini API response. Check API documentation.")
    except Exception as e:
        logger.error(f"Session {sid}: Unexpected error during Gemini API call: {e}", exc_info=True)
        raise HTTPException(500, detail="❌ An unexpected error occurred.")


    # Add the AI's reply to the in-memory conversation buffer
    conversations[sid].append({"role":"model","text":reply})
    # Add the AI's reply to persistent memory
    add_message_to_memory(user_id=sid, message=reply, sender="ai")

    # Calculate nudging score based on current emotional state, flags, and traits
    score = calculate_nudging_score(emotions, flags, get_traits(sid))
    logger.info(f"Session {sid}: Nudging score: {score}")

    # Return the response to the client
    return Response(
        content=json.dumps({
            "session_id": sid,
            "response": reply,
            "emotions": emotions, # Current emotional state
            "nudging_score": score, # Calculated nudging score
            "flags": flags # Behavioral flags detected
        }, ensure_ascii=False),
        media_type="application/json"
    )

# Endpoint to retrieve full memory for a given session
@app.get("/memory/{session_id}")
async def get_full_user_memory_endpoint(session_id: str):
    logger.info(f"Received request for full memory for session: {session_id}")
    user_mem = get_user_memory(session_id)
    return Response(
        content=json.dumps({"session_id": session_id, "memory": user_mem}, ensure_ascii=False),
        media_type="application/json"
    )

# Endpoint to retrieve traits for a given session
@app.get("/traits/{session_id}")
async def get_user_traits_endpoint(session_id: str):
    logger.info(f"Received request for traits for session: {session_id}")
    user_traits = get_traits(session_id)
    return Response(
        content=json.dumps({"session_id": session_id, "traits": user_traits}, ensure_ascii=False),
        media_type="application/json"
    )