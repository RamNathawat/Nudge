import json
import os
from .memory import load_memory # Import load_memory from the same package

def get_salient_memories(session_id):
    full_memory = load_memory()
    # Access the 'users' dictionary first
    session_data = full_memory.get("users", {}).get(session_id, {})
    # Assuming 'entries' holds the history where 'salient' might be a key
    history = session_data.get("entries", [])

    salient_entries = []
    for entry in history:
        # Assuming 'salience' is a key within the MemoryEntry dict
        if entry.get("salience", 0) > 0.5: # Example threshold for salience
            salient_entries.append(entry)
    return salient_entries