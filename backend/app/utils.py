# app/utils.py

def format_for_gemini(conversation_slice: list[dict]) -> list[dict]:
    """
    Formats the conversation slice for the Gemini API.
    Gemini expects a list of dictionaries with 'role' and 'parts' keys,
    where 'parts' is a list of dictionaries with a 'text' key.
    """
    formatted_content = []
    for entry in conversation_slice:
        # Ensure role is 'user' or 'model' for Gemini
        role = entry["role"]
        if role == "system":
            # Gemini's system role usually integrates into user/model turns or initial prompt
            # For simplicity here, we'll assign system prompts to 'user' role for now.
            # A more sophisticated approach might embed them into user messages or initial turn.
            role = "user"
        elif role == "ai": # Assuming 'ai' role from your memory.py, convert to 'model'
            role = "model"

        formatted_content.append(
            {"role": role, "parts": [{"text": entry["text"]}]}
        )
    return formatted_content