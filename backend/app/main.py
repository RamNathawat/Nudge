import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load .env
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

# Core app
app = FastAPI()

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prompts
SOFT_PROMPT = {
    "role": "system",
    "text": "You are 'Nudge' — a smart companion texting with the user. Start casual, build tension, then nudge."
}
HARD_PROMPT = {
    "role": "system",
    "text": "You are 'Nudge' — sharp and persuasive. Challenge user behavior using tone-mirroring and psychology."
}

# Session store
conversations: Dict[str, List[Dict[str, str]]] = {}

# Chat input
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# --- Import app modules ---
from app.auth import verify_token
from app.memory import (
    get_user_memory, add_message_to_memory, get_recent_history,
    update_trait, get_traits, get_relevant_memory
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score

# --- HEALTH ---
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Nudge AI service is running."}

# --- CHAT ---
@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(verify_token)):
    sid = request.session_id or str(uuid.uuid4())
    conversations.setdefault(sid, [SOFT_PROMPT])

    user_txt = request.message.strip()
    add_message_to_memory(user_id=user_id, message=user_txt, sender="user")
    context_string, flags, emotions = inject_context(user_txt, user_id)

    # Pull relevant memory into convo
    for entry in get_relevant_memory(user_id)[:5]:
        conversations[sid].append({
            "role": "user" if entry.get("sender") == "user" else "model",
            "text": entry["content"]
        })

    conversations[sid].append({
        "role": "user",
        "text": f"{user_txt}\n\n(Emotions: {summary_emotions(emotions)} | Traits: {json.dumps(get_traits(user_id))})"
    })

    # Tone shift
    if is_emotionally_relevant(user_txt, flags) and HARD_PROMPT not in conversations[sid]:
        if conversations[sid][0] == SOFT_PROMPT:
            conversations[sid].insert(1, HARD_PROMPT)
        else:
            conversations[sid].append(HARD_PROMPT)

    # Gemini Request
    payload = {"contents": format_for_gemini(conversations[sid][-12:])}

    try:
        res = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"})
        res.raise_for_status()
        reply = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error("Gemini API failed:", exc_info=True)
        raise HTTPException(500, "Gemini response error.")

    conversations[sid].append({"role": "model", "text": reply})
    add_message_to_memory(user_id=user_id, message=reply, sender="ai")
    score = calculate_nudging_score(emotions, flags, get_traits(user_id))

    return Response(
        content=json.dumps({
            "session_id": sid,
            "response": reply,
            "emotions": emotions,
            "nudging_score": score,
            "flags": flags
        }, ensure_ascii=False),
        media_type="application/json"
    )

# --- MEMORY ROUTES ---
@app.get("/memory")
async def full_memory(user_id: str = Depends(verify_token)):
    return get_user_memory(user_id)

@app.get("/traits")
async def full_traits(user_id: str = Depends(verify_token)):
    return get_traits(user_id)

# --- CONTEXT BUILDER ---
def inject_context(msg: str, user_id: str):
    flags = analyze_behavior(user_id, msg)
    emo_state = infer_emotional_state(msg)
    summary = summary_emotions(emo_state)
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)
    context = (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(user_id))} | "
        f"User Traits: {json.dumps(get_traits(user_id))} | Inferred Emotions: {summary})"
    )
    return context, flags, emo_state

# ✅ --- Register auth routes ---
from app.auth import router as auth_router
app.include_router(auth_router)
