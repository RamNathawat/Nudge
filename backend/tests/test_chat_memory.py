import pytest
import os
import uuid
import json # To check the memory file directly

# Note: No explicit mocking needed here as it's handled by conftest.py's autouse fixture.

def test_initial_chat_creates_user_entry(client, get_test_memory):
    """
    Test that sending a message as a new user creates a new entry in memory.
    """
    user_id = str(uuid.uuid4())
    response = client.post("/chat", json={"session_id": user_id, "message": "hello"})
    assert response.status_code == 200
    assert "Mocked Gemini AI response" in response.json()["response"] # Check against mocked response

    memory = get_test_memory()
    assert user_id in memory["users"]
    assert len(memory["users"][user_id]["entries"]) == 2 # 1 user message + 1 AI reply
    assert memory["users"][user_id]["entries"][0]["content"] == "hello"
    assert memory["users"][user_id]["entries"][1]["content"] == "Mocked Gemini AI response"


def test_subsequent_chat_adds_to_existing_user(client, get_test_memory):
    """
    Test that subsequent messages from the same user add to their existing memory.
    """
    user_id = str(uuid.uuid4())
    # First message
    client.post("/chat", json={"session_id": user_id, "message": "first message"})
    
    # Second message
    response = client.post("/chat", json={"session_id": user_id, "message": "second message"})
    assert response.status_code == 200

    memory = get_test_memory()
    assert user_id in memory["users"]
    assert len(memory["users"][user_id]["entries"]) == 4 # 2 user messages + 2 AI replies
    assert memory["users"][user_id]["entries"][-2]["content"] == "second message"
    assert memory["users"][user_id]["entries"][-1]["content"] == "Mocked Gemini AI response"


def test_memory_persistence_across_app_loads(client, get_test_memory, set_test_memory):
    """
    Test that memory is loaded correctly when the app starts.
    This simulates restarting the FastAPI app by ensuring the file state is consistent.
    """
    user_id = str(uuid.uuid4())
    initial_memory_data = {
        "users": {
            user_id: {
                "entries": [
                    {"user_id": user_id, "content": "I like cats", "timestamp": "2024-01-01T10:00:00", "emotion": "joy", "emotional_intensity": 0.8, "salience": 2.0, "repetition_score": 0.0, "topic_tags": ["pets"], "task_reference": None, "sender": "user"},
                    {"user_id": user_id, "content": "Meow!", "timestamp": "2024-01-01T10:00:01", "emotion": "neutral", "emotional_intensity": 0.3, "salience": 0.5, "repetition_score": 0.0, "topic_tags": ["pets"], "task_reference": None, "sender": "ai"}
                ],
                "_traits": {"last_detected_mood": "joy", "joy": 0.8}
            }
        }
    }
    set_test_memory(initial_memory_data)

    # Send a new message. The app will load the memory from the file due to the fixture setup.
    response = client.post("/chat", json={"session_id": user_id, "message": "What did I say I liked?"})
    assert response.status_code == 200

    current_memory = get_test_memory()
    assert user_id in current_memory["users"]
    assert len(current_memory["users"][user_id]["entries"]) == 4 # 2 old entries + 2 new entries (user + AI)
    
    # Verify the old entry is still there
    assert "I like cats" in [e["content"] for e in current_memory["users"][user_id]["entries"]]
    assert "Meow!" in [e["content"] for e in current_memory["users"][user_id]["entries"]]


def test_multiple_users_have_separate_memories(client, get_test_memory):
    """
    Test that memory for different users is kept separate.
    """
    user_id_1 = str(uuid.uuid4())
    user_id_2 = str(uuid.uuid4())

    # User 1 sends a message
    client.post("/chat", json={"session_id": user_id_1, "message": "I love dogs"})
    
    # User 2 sends a message
    client.post("/chat", json={"session_id": user_id_2, "message": "I love cats"})

    memory = get_test_memory()
    assert user_id_1 in memory["users"]
    assert user_id_2 in memory["users"]

    # Check content for User 1
    user1_contents = [e["content"] for e in memory["users"][user_id_1]["entries"]]
    assert "I love dogs" in user1_contents
    assert "I love cats" not in user1_contents # Ensure no cross-contamination

    # Check content for User 2
    user2_contents = [e["content"] for e in memory["users"][user_id_2]["entries"]]
    assert "I love cats" in user2_contents
    assert "I love dogs" not in user2_contents # Ensure no cross-contamination