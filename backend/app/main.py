from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import List, Optional, Dict
import os, uuid, requests, json, logging
from dotenv import load_dotenv

from .behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from .state_inference import infer_emotional_state, summary_emotions
from .memory import (
    update_trait,
    user_memory,
    add_message_to_memory,
    get_recent_history,
    get_traits,
)

# === Environment Setup ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY is missing in .env")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# === FastAPI App Initialization ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Global State ===
conversations: Dict[str, List[Dict[str, str]]] = {}

# === Chat Tone Personas ===

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


# === Request Schema ===
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


# === API Routes ===
@app.get("/ping")
def ping():
    return {"message": "pong 🧠"}


@app.post("/reset-memory")
def reset_memory():
    user_memory.clear()
    conversations.clear()
    return {"message": "🧠 Nudge's memory has been wiped clean."}


# === Helper Functions ===
def format_for_gemini(convo: List[Dict[str, str]]) -> List[Dict]:
    return [
        {
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["text"]}]
        } for msg in convo
    ]


def inject_emotional_context(message: str):
    behavior_flags = analyze_behavior(message)
    emotional_state = infer_emotional_state(message)
    summarized_state_str = summary_emotions(emotional_state)  # returns a string summary

    # Update memory traits using the actual dict
    for trait, value in emotional_state.items():
        update_trait(trait, value)

    # Format context
    return (
        f"\n\n(Recent behavior: {json.dumps(get_recent_history())} | "
        f"Traits: {json.dumps(get_traits())} | "
        f"Inferred emotions: {summarized_state_str})",
        behavior_flags,
        emotional_state,  # returning the real dict
    )



# === Main Chat Endpoint ===
@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    conversations.setdefault(session_id, [SOFT_PROMPT])

    user_text = request.message.strip()
    user_msg = {"role": "user", "text": user_text}

    # Log input
    add_message_to_memory(user_text, sender="user")

    # Analyze emotional context
    context_addition, flags, emotions = inject_emotional_context(user_text)
    user_msg["text"] += context_addition
    conversations[session_id].append(user_msg)

    # Decide tone shift
    if is_emotionally_relevant(user_text, flags) and HARD_PROMPT not in conversations[session_id]:
        conversations[session_id].insert(1, HARD_PROMPT)

    # Build request to Gemini
    convo_slice = conversations[session_id][-12:]
    payload = {"contents": format_for_gemini(convo_slice)}

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

        reply_text = parts[0]["text"]
        conversations[session_id].append({"role": "model", "text": reply_text})
        add_message_to_memory(reply_text, sender="ai")

        return Response(
            content=json.dumps({
                "session_id": session_id,
                "response": reply_text,
                "emotions": emotions
            }, ensure_ascii=False),
            media_type="application/json"
        )

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Unhandled server error")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
