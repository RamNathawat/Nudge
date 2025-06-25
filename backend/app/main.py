import os, uuid, json, logging, requests
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Dict, List
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId

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
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score

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
    safe_mode: Optional[bool] = False
    reply_to_id: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Nudge AI is live!"}

@app.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(verify_token)):
    sid = f"{user_id}-{request.session_id or str(uuid.uuid4())}"
    conversations.setdefault(sid, [SOFT_PROMPT])

    user_txt = request.message.strip()

    # ✅ Add user message to memory, support reply_to_id
    add_message_to_memory(
        user_id=user_id,
        message=user_txt,
        sender="user",
        reply_to_id=request.reply_to_id
    )

    safe_space = request.safe_mode or is_safe_space_mode_enabled(user_id)
    context_string, flags, emotions = inject_context(user_txt, user_id)

    # ✅ Add recent relevant memory
    for entry in get_relevant_memory(user_id)[:5]:
        conversations[sid].append({
            "role": "user" if entry.get("sender") == "user" else "model",
            "text": entry["content"]
        })

    # ✅ Inject system prompt
    if safe_space:
        conversations[sid].insert(1, {
            "role": "system",
            "text": "You are in safe space mode. Be gentle and supportive."
        })
    else:
        if is_emotionally_relevant(user_txt, flags) and HARD_PROMPT not in conversations[sid]:
            conversations[sid].insert(1, HARD_PROMPT)

    # ✅ Inject reply quote if reply_to_id is valid
    reply_quote = ""
    if request.reply_to_id:
        try:
            quoted = entries_collection.find_one({"_id": ObjectId(request.reply_to_id)})
            if quoted:
                preview = quoted["content"][:100].strip().replace("\n", " ")
                reply_quote = f'Replying to: "{preview}"\n\n'
        except InvalidId:
            logger.warning(f"Ignoring invalid reply_to_id: {request.reply_to_id}")

    # ✅ Final user message with emotion + trait summary
    conversations[sid].append({
        "role": "user",
        "text": f"{reply_quote}{user_txt}\n\n(Emotions: {summary_emotions(emotions)} | Traits: {json.dumps(get_traits(user_id))})"
    })

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
async def paginated_memory(
    user_id: str = Depends(verify_token),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, gt=0, le=100)
):
    return get_user_memory(user_id, offset=offset, limit=limit)

@app.get("/traits")
async def full_traits(user_id: str = Depends(verify_token)):
    return get_traits(user_id)

@app.delete("/memory/{entry_id}")
async def delete_memory(entry_id: str, user_id: str = Depends(verify_token)):
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
    set_safe_space_mode(user_id, enabled)
    return {"status": "ok", "safe_space_mode": enabled}

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
    return text.strip().replace("\n\n", "\n") if text else "..."
