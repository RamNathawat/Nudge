import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load env
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

conversations: Dict[str, List[Dict[str, str]]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# --- Internal imports ---
from app.auth import verify_token
from app.memory import (
    get_user_memory, add_message_to_memory, get_recent_history,
    update_trait, get_traits, get_relevant_memory,
    is_safe_space_mode_enabled, set_safe_space_mode
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Nudge AI is live!"}

@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(verify_token)):
    sid = f"{user_id}-{request.session_id or str(uuid.uuid4())}"
    conversations.setdefault(sid, [SOFT_PROMPT])

    user_txt = request.message.strip()
    add_message_to_memory(user_id=user_id, message=user_txt, sender="user")

    # Check if user is in safe space mode, alter prompt or conversation accordingly
    safe_space = is_safe_space_mode_enabled(user_id)

    # Get emotional context, flags and update traits
    context_string, flags, emotions = inject_context(user_txt, user_id)

    # Add recent relevant memory for emotional recall and pattern nudging
    for entry in get_relevant_memory(user_id)[:5]:
        conversations[sid].append({
            "role": "user" if entry.get("sender") == "user" else "model",
            "text": entry["content"]
        })

    # If safe space mode is on, use softer prompts, avoid aggressive nudges
    if safe_space:
        # Optionally insert a system message to keep tone safe
        conversations[sid].insert(1, {
            "role": "system",
            "text": "You are in safe space mode. Be gentle and supportive."
        })
    else:
        # Insert HARD_PROMPT if emotional flags suggest it and not already present
        if is_emotionally_relevant(user_txt, flags) and HARD_PROMPT not in conversations[sid]:
            conversations[sid].insert(1, HARD_PROMPT)

    conversations[sid].append({
        "role": "user",
        "text": f"{user_txt}\n\n(Emotions: {summary_emotions(emotions)} | Traits: {json.dumps(get_traits(user_id))})"
    })

    # Prepare Gemini payload (limit to last 12 messages to control size)
    payload = {"contents": format_for_gemini(conversations[sid][-12:])}

    try:
        res = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"})
        res.raise_for_status()
        reply = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        formatted_reply = format_nudge_reply(reply)
    except Exception as e:
        logger.error("Gemini API failed:", exc_info=True)
        raise HTTPException(500, "Gemini response error.")

    conversations[sid].append({"role": "model", "text": formatted_reply})
    add_message_to_memory(user_id=user_id, message=formatted_reply, sender="ai")
    score = calculate_nudging_score(emotions, flags, get_traits(user_id))

    return Response(
        content=json.dumps({
            "session_id": sid,
            "response": formatted_reply,
            "emotions": emotions,
            "nudging_score": score,
            "flags": flags,
            "safe_space_mode": safe_space
        }, ensure_ascii=False),
        media_type="application/json"
    )

@app.get("/memory")
async def full_memory(user_id: str = Depends(verify_token)):
    return get_user_memory(user_id)

@app.get("/traits")
async def full_traits(user_id: str = Depends(verify_token)):
    return get_traits(user_id)

def inject_context(msg: str, user_id: str):
    flags = analyze_behavior(user_id, msg)
    emo_state = infer_emotional_state(msg)
    summary = summary_emotions(emo_state)
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)
    return (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(user_id))} | "
        f"User Traits: {json.dumps(get_traits(user_id))} | Inferred Emotions: {summary})",
        flags,
        emo_state
    )

def format_nudge_reply(text: str) -> str:
    # Removed length limit, return full reply cleanly
    if not text:
        return "..."
    clean = text.strip().replace("\n\n", "\n")
    return clean

from app.auth import router as auth_router
app.include_router(auth_router)
