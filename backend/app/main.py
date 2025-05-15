from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import requests
import logging
from dotenv import load_dotenv


# Memory and behavior modules
from .behaviour_analyzer import analyze_behavior
from .memory import (
    update_trait,
    user_memory,
    add_message_to_memory,
    get_recent_history,
    get_traits,
)
# Load .env and Gemini API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY is missing in .env")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# FastAPI app
app = FastAPI()

# Allow CORS (dev: *, prod: restrict this)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session chat store
conversations: Dict[str, List[Dict[str, str]]] = {}

# System Prompt
SYSTEM_PROMPT = {
    "role": "user",
    "text": (
        "You are Nudge, a friendly and emotionally intelligent AI assistant. Your mission is to support and gently guide "
        "the user toward their goals in a personal, engaging way...\n\n"
        "You change personalities like a real person would—warm, funny, thoughtful, or intense—depending on the user's energy."
    )
}

# Input model
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.get("/ping")
def ping():
    return {"message": "pong 🧠"}

@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # Init conversation if new
    if session_id not in conversations:
        conversations[session_id] = [SYSTEM_PROMPT]

    user_message = {"role": "user", "text": request.message}
    conversations[session_id].append(user_message)

    # Log message in memory
    add_message_to_memory(request.message, sender="user")

    # Analyze behavior
    analyze_behavior(request.message)

    # Include recent memory context
    history_snippet = get_recent_history()
    traits = get_traits()

    # Format memory and behavior summary
    behavior_context = (
        f"\n\nHere’s what I know:\nRecent messages: {history_snippet}\n"
        f"User traits: {traits}\nRespond as their emotionally aware coach and buddy."
    )

    # Prepare Gemini API payload
    convo_slice = conversations[session_id][-10:]
    convo_slice[-1]["text"] += behavior_context  # add behavioral memory to last user message

    contents = [{"role": msg["role"], "parts": [{"text": msg["text"]}]} for msg in convo_slice]
    payload = {"contents": contents}

    try:
        res = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json=payload
        )

        res.raise_for_status()
        data = res.json()

        candidates = data.get("candidates")
        if not candidates:
            raise HTTPException(status_code=500, detail="❌ Gemini API gave no reply.")

        parts = candidates[0].get("content", {}).get("parts")
        if not parts or not parts[0].get("text"):
            raise HTTPException(status_code=500, detail="❌ Gemini reply malformed.")

        reply = parts[0]["text"]
        ai_reply = {"role": "assistant", "text": reply}
        conversations[session_id].append(ai_reply)

        # Add AI message to memory
        add_message_to_memory(reply, sender="ai")

        return {"session_id": session_id, "response": reply}

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Server error")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
