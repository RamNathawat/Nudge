import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

# Custom modules
from app.memory import (
    get_user_memory,
    add_message_to_memory,
    get_recent_history,
    update_trait,
    get_traits,
    get_relevant_memory
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score

# Initialize app
app = FastAPI()

# CORS config — production-safe
origins = [
    "https://leafy-tiramisu-ed9886.netlify.app",
    "http://localhost",
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

conversations: Dict[str, List[Dict[str, str]]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Nudge AI service is running."}

@app.post("/chat")
async def chat(request: ChatRequest):
    sid = request.session_id or str(uuid.uuid4())
    logger.info(f"Session {sid}: Received message: {request.message}")

    conversations.setdefault(sid, [SOFT_PROMPT])
    user_txt = request.message.strip()
    add_message_to_memory(user_id=sid, message=user_txt, sender="user")

    # Emotional context
    context_string, flags, emotions = inject_emotional_context(user_txt, sid)

    # Load memory into conversation
    for entry in get_relevant_memory(sid)[:5]:
        conversations[sid].append({
            "role": "user" if entry.get("sender") == "user" else "model",
            "text": entry["content"]
        })

    # Add new user message
    conversations[sid].append({
        "role": "user",
        "text": f"{user_txt}\n\n(Emotions: {summary_emotions(emotions)} | Traits: {json.dumps(get_traits(sid))})"
    })

    # Tone shift
    if is_emotionally_relevant(user_txt, flags) and HARD_PROMPT not in conversations[sid]:
        if conversations[sid][0] == SOFT_PROMPT:
            conversations[sid].insert(1, HARD_PROMPT)
        else:
            conversations[sid].append(HARD_PROMPT)

    convo_slice = conversations[sid][-12:]
    payload = {"contents": format_for_gemini(convo_slice)}

    try:
        res = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"})
        logger.info(f"Gemini raw response: {res.text}")
        res.raise_for_status()
        data = res.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.exception("Gemini API failure")
        raise HTTPException(500, detail="Gemini API failed or returned malformed response.")

    conversations[sid].append({"role": "model", "text": reply})
    add_message_to_memory(user_id=sid, message=reply, sender="ai")
    score = calculate_nudging_score(emotions, flags, get_traits(sid))

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

@app.get("/memory/{session_id}")
async def get_full_user_memory_endpoint(session_id: str):
    return Response(
        content=json.dumps({"session_id": session_id, "memory": get_user_memory(session_id)}, ensure_ascii=False),
        media_type="application/json"
    )

@app.get("/traits/{session_id}")
async def get_user_traits_endpoint(session_id: str):
    return Response(
        content=json.dumps({"session_id": session_id, "traits": get_traits(session_id)}, ensure_ascii=False),
        media_type="application/json"
    )

def inject_emotional_context(message: str, sid: str) -> tuple[str, List[str], Dict[str, float]]:
    flags = analyze_behavior(sid, message)
    emo_state = infer_emotional_state(message)
    summary = summary_emotions(emo_state)
    for emotion, intensity in emo_state.items():
        update_trait(sid, emotion, intensity)
    context = (
        f"\n\n(Recent Interaction History: {json.dumps(get_recent_history(sid))} | "
        f"User Traits: {json.dumps(get_traits(sid))} | "
        f"Inferred Emotions: {summary})"
    )
    return context, flags, emo_state
