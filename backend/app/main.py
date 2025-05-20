from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict
import os, uuid, requests, json, logging
from dotenv import load_dotenv

# Internal modules
from app.memory import (
    user_memory,
    save_memory,
    update_trait,
    add_message_to_memory,
    get_recent_history,
    get_traits,
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score

# ----------------------
# Request/Response Schema
# ----------------------

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

# ----------------------
# In-memory conversations
# ----------------------

conversations: Dict[str, List[Dict[str, str]]] = {}

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

# Load Gemini endpoint from .env
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")

# ----------------------
# Helper: Emotional Context Injection
# ----------------------

def inject_emotional_context(message: str):
    """
    Performs behavioral analysis, infers emotional state,
    and returns memory context string and emotional metadata.
    """
    behavior_flags = analyze_behavior(message)
    emotional_state = infer_emotional_state(message)
    summarized_state_str = summary_emotions(emotional_state)

    for trait, value in emotional_state.items():
        update_trait(trait, value)

    context = (
        f"\n\n(Recent behavior: {json.dumps(get_recent_history())} | "
        f"Traits: {json.dumps(get_traits())} | "
        f"Inferred emotions: {summarized_state_str})"
    )
    return context, behavior_flags, emotional_state

# ----------------------
# FastAPI App Instance
# ----------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Route: /chat
# ----------------------

@app.post("/chat")
def chat(request: ChatRequest):
    """
    Main endpoint for processing chat with emotional intelligence, nudging, and memory feedback.
    """
    session_id = request.session_id or str(uuid.uuid4())
    conversations.setdefault(session_id, [SOFT_PROMPT])

    user_text = request.message.strip()
    user_msg = {"role": "user", "text": user_text}
    add_message_to_memory(user_text, sender="user")

    try:
        # --- Emotional Analysis and Context ---
        context_addition, flags, emotions = inject_emotional_context(user_text)
        user_msg["text"] += context_addition
        conversations[session_id].append(user_msg)

        # --- Trigger HARD prompt based on behavior ---
        if is_emotionally_relevant(user_text, flags) and HARD_PROMPT not in conversations[session_id]:
            conversations[session_id].insert(1, HARD_PROMPT)

        # --- Gemini Payload ---
        convo_slice = conversations[session_id][-12:]
        payload = {"contents": format_for_gemini(convo_slice)}

        res = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        res.raise_for_status()
        data = res.json()

        candidates = data.get("candidates")
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini API returned no reply.")

        parts = candidates[0].get("content", {}).get("parts")
        if not parts or not parts[0].get("text"):
            raise HTTPException(status_code=500, detail="Gemini response malformed.")

        reply_text = parts[0]["text"]
        conversations[session_id].append({"role": "model", "text": reply_text})
        add_message_to_memory(reply_text, sender="ai")

        # --- Nudging Score (1-5) ---
        nudging_score = calculate_nudging_score(emotions, flags, get_traits())

        # --- Logging for internal dev ---
        logging.info({
            "session_id": session_id,
            "user_traits": get_traits(),
            "nudge_flags": flags,
            "emotional_flags": emotions,
            "nudging_score": nudging_score
        })

        return Response(
            content=json.dumps({
                "session_id": session_id,
                "response": reply_text,
                "emotions": emotions,
                "nudging_score": nudging_score
            }, ensure_ascii=False),
            media_type="application/json"
        )

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Unhandled server error")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict
import os, uuid, requests, json, logging
from dotenv import load_dotenv

# Internal modules
from app.memory import (
    user_memory,
    save_memory,
    update_trait,
    add_message_to_memory,
    get_recent_history,
    get_traits,
)
from app.behaviour_analyzer import analyze_behavior, is_emotionally_relevant
from app.state_inference import infer_emotional_state, summary_emotions
from app.utils import format_for_gemini
from app.nudge_scoring import calculate_nudging_score
from app.task_topic_inference import infer_user_state  # New import

# ----------------------
# Request/Response Schema
# ----------------------

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str

# ----------------------
# In-memory conversations
# ----------------------

conversations: Dict[str, List[Dict[str, str]]] = {}

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

# Load Gemini endpoint from .env
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")

# ----------------------
# Helper: Emotional Context Injection
# ----------------------

def inject_emotional_context(message: str):
    behavior_flags = analyze_behavior(message)
    emotional_state = infer_emotional_state(message)
    summarized_state_str = summary_emotions(emotional_state)

    for trait, value in emotional_state.items():
        update_trait(trait, value)

    context = (
        f"\n\n(Recent behavior: {json.dumps(get_recent_history())} | "
        f"Traits: {json.dumps(get_traits())} | "
        f"Inferred emotions: {summarized_state_str})"
    )
    return context, behavior_flags, emotional_state

# ----------------------
# FastAPI App Instance
# ----------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific frontend domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Route: /chat
# ----------------------

@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    conversations.setdefault(session_id, [SOFT_PROMPT])

    user_text = request.message.strip()
    user_msg = {"role": "user", "text": user_text}
    add_message_to_memory(user_text, sender="user")

    try:
        # --- Emotional Analysis and Context ---
        context_addition, flags, emotions = inject_emotional_context(user_text)

        # --- Task Topic Inference ---
        user_state = infer_user_state(user_text)
        task_topic = user_state.get("task_topic", "unknown")
        intent = user_state.get("intent", "unknown")
        substance = user_state.get("substance", "unknown")

        user_msg["text"] += context_addition
        user_msg["text"] += f"\n\n(Task topic: {task_topic})"
        conversations[session_id].append(user_msg)

        # --- Trigger HARD Prompt ---
        if is_emotionally_relevant(user_text, flags) and HARD_PROMPT not in conversations[session_id]:
            conversations[session_id].insert(1, HARD_PROMPT)

        # --- Gemini API Request ---
        convo_slice = conversations[session_id][-12:]
        payload = {"contents": format_for_gemini(convo_slice)}

        res = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        res.raise_for_status()
        data = res.json()

        candidates = data.get("candidates")
        if not candidates:
            raise HTTPException(status_code=500, detail="Gemini API returned no reply.")

        parts = candidates[0].get("content", {}).get("parts")
        if not parts or not parts[0].get("text"):
            raise HTTPException(status_code=500, detail="Gemini response malformed.")

        reply_text = parts[0]["text"]
        conversations[session_id].append({"role": "model", "text": reply_text})
        add_message_to_memory(reply_text, sender="ai")

        # --- Nudging Score ---
        nudging_score = calculate_nudging_score(emotions, flags, get_traits())

        # --- Logging ---
        logging.info({
            "session_id": session_id,
            "user_traits": get_traits(),
            "nudge_flags": flags,
            "emotional_flags": emotions,
            "nudging_score": nudging_score,
            "intent": intent,
            "task_topic": task_topic,
            "substance": substance
        })

        return Response(
            content=json.dumps({
                "session_id": session_id,
                "response": reply_text,
                "emotions": emotions,
                "nudging_score": nudging_score,
                "intent": intent,
                "task_topic": task_topic,
                "substance": substance
            }, ensure_ascii=False),
            media_type="application/json"
        )

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Unhandled server error")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")