import pytest
import uuid

# Note: Global mocking is handled by conftest.py's autouse fixture.
# Specific mocks below will override the global ones for these tests.

def test_positive_emotion_reflected_in_memory_and_response_mock(client, mocker, get_test_memory):
    """
    Test that positive emotion is detected and influences Nudge's reply.
    We mock behavior_analyzer.estimate_emotion and requests.post
    to simulate the desired outcome.
    """
    # Override global mocks for this specific test
    mocker.patch('app.behaviour_analyzer.estimate_emotion', return_value={"emotion": "joy", "intensity": 0.9})
    mocker.patch('app.behaviour_analyzer.calculate_salience', return_value=3.0) # Specific salience for this test
    # Mock Gemini's specific response to joy
    mock_gemini_response = mocker.Mock()
    mock_gemini_response.status_code = 200
    mock_gemini_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "That sounds absolutely wonderful! So glad to hear that!"}]}}]
    }
    mocker.patch('requests.post', return_value=mock_gemini_response)

    user_id = str(uuid.uuid4())
    message = "I just got a huge promotion at work!"
    response = client.post("/chat", json={"session_id": user_id, "message": message})

    assert response.status_code == 200
    assert "That sounds absolutely wonderful!" in response.json()["response"]

    memory = get_test_memory()
    user_entries = memory["users"][user_id]["entries"]
    
    # User's message entry
    assert user_entries[0]["content"] == message
    assert user_entries[0]["emotion"] == "joy"
    assert user_entries[0]["emotional_intensity"] == 0.9
    assert user_entries[0]["salience"] == 3.0 # Verify specific salience
    
    # Nudge's reply entry
    assert user_entries[1]["content"] == "That sounds absolutely wonderful! So glad to hear that!"
    # The default mock for Nudge's emotion/intensity will apply here unless specifically mocked for AI messages.

    # Check user traits
    assert memory["users"][user_id]["_traits"]["last_detected_mood"] == "joy"
    assert memory["users"][user_id]["_traits"]["joy"] == 0.9


def test_negative_emotion_reflected_in_memory_and_response_mock(client, mocker, get_test_memory):
    """
    Test that negative emotion is detected and influences Nudge's reply.
    """
    mocker.patch('app.behaviour_analyzer.estimate_emotion', return_value={"emotion": "sadness", "intensity": 0.8})
    mocker.patch('app.behaviour_analyzer.calculate_salience', return_value=4.0) # Specific salience
    # Mock Gemini's specific response to sadness
    mock_gemini_response = mocker.Mock()
    mock_gemini_response.status_code = 200
    mock_gemini_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "I'm truly sorry to hear that. Is there anything I can do?"}]}}]
    }
    mocker.patch('requests.post', return_value=mock_gemini_response)

    user_id = str(uuid.uuid4())
    message = "I failed my exam, feeling really down."
    response = client.post("/chat", json={"session_id": user_id, "message": message})

    assert response.status_code == 200
    assert "I'm truly sorry to hear that." in response.json()["response"]

    memory = get_test_memory()
    user_entries = memory["users"][user_id]["entries"]
    
    # User's message entry
    assert user_entries[0]["content"] == message
    assert user_entries[0]["emotion"] == "sadness"
    assert user_entries[0]["emotional_intensity"] == 0.8
    assert user_entries[0]["salience"] == 4.0 # Verify specific salience

    # Check user traits
    assert memory["users"][user_id]["_traits"]["last_detected_mood"] == "sadness"
    assert memory["users"][user_id]["_traits"]["sadness"] == 0.8


def test_salience_and_repetition_scores_are_captured(client, mocker, get_test_memory):
    """
    Test that salience and repetition scores are correctly stored.
    This also implicitly tests that `add_message_to_memory` saves these.
    """
    user_id = str(uuid.uuid4())

    # --- First message (High Salience, No Repetition) ---
    mocker.patch('app.behaviour_analyzer.calculate_salience', return_value=5.0)
    mocker.patch('app.behaviour_analyzer.calculate_repetition_score', return_value=0.0)
    message_high_salience = "I had a terrible argument with my best friend, I'm so upset!"
    client.post("/chat", json={"session_id": user_id, "message": message_high_salience})

    # --- Second message (Low Salience, High Repetition) ---
    # Need to get user_memory to pass to repetition score for the next mock
    current_memory_before_second_message = get_test_memory()
    mocker.patch('app.behaviour_analyzer.calculate_salience', return_value=0.5) # Lower salience
    mocker.patch('app.behaviour_analyzer.calculate_repetition_score', 
                 side_effect=lambda uid, msg, mem: 0.7 if msg == "hey" else 0.0) # Simulate high repetition only for "hey"
    
    message_low_salience_repetitive = "hey"
    client.post("/chat", json={"session_id": user_id, "message": message_low_salience_repetitive})


    memory = get_test_memory()
    user_entries = memory["users"][user_id]["entries"]

    # Check first user message (index 0)
    assert user_entries[0]["content"] == message_high_salience
    assert user_entries[0]["salience"] == 5.0
    assert user_entries[0]["repetition_score"] == 0.0

    # Check second user message (index 2, because an AI reply is at index 1)
    assert user_entries[2]["content"] == message_low_salience_repetitive
    assert user_entries[2]["salience"] == 0.5
    assert user_entries[2]["repetition_score"] == 0.7 # Verify calculated repetition score