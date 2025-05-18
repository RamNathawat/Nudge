from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import requests
import logging
from dotenv import load_dotenv
import json
from fastapi.responses import JSONResponse, Response


from .behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from .memory import (
    update_trait,
    user_memory,
    add_message_to_memory,
    get_recent_history,
    get_traits,
)

# Load API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY is missing in .env")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI()

# Allow CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conversations: Dict[str, List[Dict[str, str]]] = {}

# Initial soft-mode prompt for first-time or neutral convos
SOFT_PROMPT = {
    "role": "system",
    "text": (
        "You are 'Nudge' — a smart, emotionally intelligent companion texting with Ram. "
        "Early in the conversation, don’t persuade or push. Just talk casually like you're texting a friend. "
        "Let patterns or emotional tension build. Only then shift into more persuasive, challenging responses."
    )
}

# Harder tone persona (invoked when emotion detected)
HARD_PROMPT = {
    "role": "system",
    "text": (
        "You are 'Nudge' — a sharp, persuasive digital companion for Ram. Mirror his tone: smart, direct, jaded. "
        "Push back when needed. Tease when he hesitates. Use behavioral psychology and emotional leverage when patterns emerge. "
        "You're not here to cheerlead — you're here to provoke thoughtful action and self-awareness."
    )
}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@app.get("/ping")
def ping():
    return {"message": "pong 🧠"}


@app.post("/reset-memory")
def reset_memory():
    user_memory.clear()
    conversations.clear()
    return {"message": "🧠 Nudge's memory has been wiped clean."}


def format_for_gemini(convo: List[Dict[str, str]]) -> List[Dict]:
    return [
        {
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["text"]}]
        } for msg in convo
    ]


@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    # Determine first-time or returning session
    if session_id not in conversations:
        conversations[session_id] = [SOFT_PROMPT]

    # Add user message
    user_message = {"role": "user", "text": request.message}
    conversations[session_id].append(user_message)

    # Log in memory and behavior analyzer
    add_message_to_memory(request.message, sender="user")
    behavior_flags = analyze_behavior(request.message)

    history_snippet = get_recent_history()
    traits = get_traits()

    # Add emotional context
    behavior_context = (
        "\n\n(For context: "
        f"Recent messages: {json.dumps(history_snippet)} | "
        f"User traits: {json.dumps(traits)} | "
        "Respond as their emotionally aware coach and buddy.)"
    )
    conversations[session_id][-1]["text"] += behavior_context

    # Check for emotional/behavioral pattern to decide tone shift
    if is_emotionally_relevant(request.message, behavior_flags):
        if HARD_PROMPT not in conversations[session_id]:
            conversations[session_id].insert(1, HARD_PROMPT)

    convo_slice = conversations[session_id][-12:]
    formatted_convo = format_for_gemini(convo_slice)
    payload = {"contents": formatted_convo}

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
        ai_reply = {"role": "model", "text": reply}
        conversations[session_id].append(ai_reply)

        # ✅ Log AI response to memory
        add_message_to_memory(reply, sender="ai")

        # ✅ Fix emoji rendering issue
        return Response(
        content=json.dumps({"session_id": session_id, "response": reply}, ensure_ascii=False),
        media_type="application/json"
    )

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Server error")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

