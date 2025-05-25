# app/utils/format_for_gemini.py
from typing import List, Dict, Any

def format_for_gemini(conversation_history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Formats a list of conversation messages into the structure expected by the Gemini API.

    Args:
        conversation_history: A list of dictionaries, where each dictionary represents
                              a message with "role" (e.g., "user", "model", "system")
                              and "text" keys.

    Returns:
        A list of dictionaries formatted for the Gemini API's 'contents' field.
        Each message will have a 'role' and a 'parts' key, where 'parts' is a list
        containing a dictionary with a 'text' key.
    """
    formatted_messages = []
    for message in conversation_history:
        role = message.get("role")
        text = message.get("text")

        if role and text:
            # Map "ai" sender to "model" for Gemini, if it ever slips through
            if role == "ai":
                role = "model"
            
            # Gemini expects 'parts' which is a list of 'text' objects
            formatted_messages.append({
                "role": role,
                "parts": [{"text": text}]
            })
    return formatted_messages