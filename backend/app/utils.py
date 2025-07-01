# In app/utils.py

from datetime import datetime
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

def safe_bson_date(date):
    """
    Ensures the input is a datetime object or None.
    Returns the datetime object as is, or None if input is not a datetime.
    """
    if isinstance(date, datetime):
        return date
    return None

def format_for_gemini(conversation_slice: List[Dict]) -> List[Dict]:
    """
    Formats conversation history for Gemini API chat completion.
    """

    formatted_content = []
    total_chars = 0
    max_chars = 6000

    for entry in conversation_slice:
        # Ensure 'content' key exists. If not, this entry cannot be used.
        if "content" not in entry:
            logger.warning(f"Skipping conversation entry due to missing 'content' field: {entry}")
            continue

        # Safely get 'role'. If missing, provide a default and log a warning.
        role = entry.get("sender") # Use 'sender' from your DB entry as the role
        if role is None:
            logger.warning(f"Conversation entry missing 'sender' field, defaulting to 'user': {entry}")
            role = "user" # Default to 'user' if sender is missing.

        text = entry["content"].strip() # *** Changed from entry["text"] to entry["content"] ***

        # Map internal roles to Gemini-friendly ones
        if role == "system":
            role = "user"  # Gemini doesn't formally support 'system' role in the chat body
        elif role == "ai":
            role = "model"
        # If 'role' was initially missing and defaulted to 'user', it will stay 'user'.

        # Skip empty or whitespace-only texts
        if not text:
            continue

        # Enforce hard max total char limit
        if total_chars + len(text) > max_chars:
            break

        formatted_content.append({
            "role": role,
            "parts": [{"text": text}]
        })

        total_chars += len(text)
    
    return formatted_content