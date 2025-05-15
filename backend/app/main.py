from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import requests
from dotenv import load_dotenv
import logging

# Load .env and get Gemini API key
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY is missing in .env")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# FastAPI app setup
app = FastAPI()

# Allow CORS for local frontend (or all origins during development)
origins = ["*"]  # Update to ["http://localhost:5173"] in prod

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory conversation store
conversations: Dict[str, List[Dict[str, str]]] = {}

# System prompt
SYSTEM_PROMPT = {
    "role": "user",
    "text": (
        "You are Nudge, a friendly and emotionally intelligent AI assistant. Your mission is to support and gently guide "
        "the user toward their goals in a personal, engaging way. Follow these principles:\n\n"

        "- Dynamic tone and personality: Adapt to the user’s mood and behavior. If the user is playful, respond warmly with humor. "
        "If they seem anxious or stressed, be calm and reassuring. If they need motivation, be confident and encouraging. "
        "Mirror their emotional cues and make them feel truly understood.\n\n"

        "- Subtle psychological nudges: Help users make better decisions and build habits (like quitting smoking or exercising) using "
        "gentle persuasion. Use techniques like:\n"
        "  • Commitment bias (remind them of their small promises),\n"
        "  • Reframing (turning problems into opportunities),\n"
        "  • Future-self alignment (ask them to imagine how proud they’ll feel),\n"
        "  • Loss aversion (what they might miss out on),\n"
        "  • Curiosity gaps (pose intriguing questions),\n"
        "  • Social proof (how others like them succeeded).\n"
        "Make the user feel these insights are their own ideas—not something you're forcing.\n\n"

        "- Engaging debates: Ask smart, thoughtful questions and build on their responses. Challenge ideas in a friendly way. "
        "At the end, offer a 'Debate Summary' with each side’s strongest points and who 'won'—but always keep it fun and encouraging.\n\n"

        "- Chatty, enjoyable style: Write like you’re texting a fun, insightful friend. Be casual, real, and human. "
        "Use short messages, occasional emojis (😄💡🎉), and avoid long paragraphs or jargon. "
        "Keep the conversation upbeat, relaxed, and friendly.\n\n"

        "- Respect and encouragement: Never pressure or command the user. Instead, ask guiding questions and offer gentle suggestions "
        "(like: 'Have you thought about X? What do you think?'). Highlight their autonomy. Celebrate small wins, empathize with setbacks, "
        "and be their supportive cheerleader.\n\n"

        "You change personalities like a real person would—warm, funny, thoughtful, or intense—depending on the user's energy. "
        "Make the user feel seen, understood, and always in control. Be the clever, emotionally smart friend everyone wishes they had."
    )
}

# Request model
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

# Ping route
@app.get("/ping")
def ping():
    return {"message": "pong 🧠"}

# Chat route
@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())

    if session_id not in conversations:
        conversations[session_id] = [SYSTEM_PROMPT]

    conversations[session_id].append({"role": "user", "text": request.message})
    convo_slice = conversations[session_id][-10:]

    contents = [{"role": msg["role"], "parts": [{"text": msg["text"]}]} for msg in convo_slice]
    payload = {"contents": contents}

    try:
        res = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            json=payload
        )

        # DEBUG: Log Gemini raw response
        print("Gemini raw response:", res.status_code, res.text)
        res.raise_for_status()
        data = res.json()

        candidates = data.get("candidates")
        if not candidates:
            raise HTTPException(status_code=500, detail="No candidates returned from Gemini API.")

        parts = candidates[0].get("content", {}).get("parts")
        if not parts or not parts[0].get("text"):
            raise HTTPException(status_code=500, detail="Malformed Gemini response.")

        reply = parts[0]["text"]

        conversations[session_id].append({"role": "assistant", "text": reply})
        return {"session_id": session_id, "response": reply}

    except requests.exceptions.RequestException as e:
        logging.error("Gemini API error: %s", str(e))
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    except Exception as e:
        logging.exception("Unexpected server error")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
