from datetime import datetime
from typing import List, Dict

def safe_bson_date(date):
    """
    Converts a MongoDB BSON datetime object to ISO format.
    Returns None if input is invalid.
    """
    if isinstance(date, datetime):
        return date.isoformat()
    return None

def format_for_gemini(conversation_slice: List[Dict]) -> List[Dict]:
    """
    Formats conversation history for Gemini API chat completion.
    
    Rules:
    - Gemini expects a list of {role: str, parts: [{text: str}]}
    - Roles must be 'user' or 'model'
    - System prompts get injected as 'user' role (for safety on Gemini API)
    - Length: Trim overly long inputs, avoid context overflow.
    """

    formatted_content = []
    total_chars = 0
    max_chars = 6000  # ✅ Total conversation context limit (to prevent Gemini cutoff issues)

    for entry in conversation_slice:
        role = entry["role"]
        text = entry["text"].strip()

        # ✅ Map internal roles to Gemini-friendly ones
        if role == "system":
            role = "user"  # Gemini doesn't formally support 'system' role in the chat body
        elif role == "ai":
            role = "model"

        # ✅ Skip empty or whitespace-only texts
        if not text:
            continue

        # ✅ Enforce hard max total char limit (avoids 400 error from Gemini API on huge payloads)
        if total_chars + len(text) > max_chars:
            break

        formatted_content.append({
            "role": role,
            "parts": [{"text": text}]
        })

        total_chars += len(text)

    return formatted_content
