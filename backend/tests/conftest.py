import pytest
import os
import sys
import json
from fastapi.testclient import TestClient

# Add the 'backend' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now these imports should work
from app.main import app
from app.memory import MEMORY_FILE # Only import MEMORY_FILE if you need to override it

# Override the MEMORY_FILE for testing
# This ensures tests use a temporary, clean memory file
TEST_MEMORY_FILE = "test_user_memory.json"

@pytest.fixture(autouse=True)
def setup_test_memory_file():
    """
    Fixture to ensure a clean test_user_memory.json for each test.
    This runs automatically for all tests (autouse=True).
    """
    original_memory_file = MEMORY_FILE # Store original path
    try:
        # Temporarily change MEMORY_FILE in the app.memory module
        from app import memory
        memory.MEMORY_FILE = TEST_MEMORY_FILE

        # Ensure the test memory file is clean before each test
        if os.path.exists(TEST_MEMORY_FILE):
            os.remove(TEST_MEMORY_FILE)
        
        # Initialize with an empty users dict
        with open(TEST_MEMORY_FILE, "w") as f:
            json.dump({"users": {}}, f)

        yield # Yield control to the test function (test runs here)

    finally:
        # Clean up the test memory file after each test
        if os.path.exists(TEST_MEMORY_FILE):
            os.remove(TEST_MEMORY_FILE)
        
        # Restore the original MEMORY_FILE path
        from app import memory
        memory.MEMORY_FILE = original_memory_file

@pytest.fixture(autouse=True) # Apply this fixture to all tests
def mock_external_services(mocker):
    """
    Mocks external services (Gemini API calls via requests, and NLP/behavioral modules)
    for all tests to ensure isolation and speed.
    """
    # Mock requests.post for Gemini API calls
    mock_gemini_response = mocker.Mock()
    mock_gemini_response.status_code = 200
    # Simulate Gemini's expected JSON response structure
    mock_gemini_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Mocked Gemini AI response"}]}}]
    }
    mocker.patch('requests.post', return_value=mock_gemini_response)

    # Mock functions from app.behaviour_analyzer
    mocker.patch('app.behaviour_analyzer.analyze_behavior', return_value={"flags": ["mock_flag"]})
    mocker.patch('app.behaviour_analyzer.is_emotionally_relevant', return_value=False) # Default
    mocker.patch('app.behaviour_analyzer.estimate_emotion', return_value={"emotion": "neutral", "intensity": 0.3})
    mocker.patch('app.behaviour_analyzer.calculate_salience', return_value=1.0)
    mocker.patch('app.behaviour_analyzer.calculate_repetition_score', return_value=0.0)

    # Mock functions from app.state_inference
    mocker.patch('app.state_inference.infer_emotional_state', return_value={"neutral": 1.0})
    mocker.patch('app.state_inference.summary_emotions', return_value="a neutral emotional state")

    # Mock functions from app.nlp_analysis (if used for topic_tags, main.py doesn't show explicit call now)
    # If main.py calls extract_topic_tags, uncomment and ensure path is correct
    # mocker.patch('app.nlp_analysis.extract_topic_tags', return_value=["mock_topic"])

    # Mock functions from app.salient_memory
    mocker.patch('app.salient_memory.get_salient_memories', return_value=[{"content": "mock salient memory"}])

    # Mock functions from app.nudge_scoring
    mocker.patch('app.nudge_scoring.calculate_nudging_score', return_value=0.5)

    # Mock functions from app.utils (e.g., format_for_gemini)
    mocker.patch('app.utils.format_for_gemini', side_effect=lambda x: x) # Simply return input for testing purposes


@pytest.fixture(scope="module")
def client():
    """
    Provides a TestClient for your FastAPI application.
    Scoped to 'module' so it's created once per test file.
    """
    return TestClient(app)

@pytest.fixture
def get_test_memory():
    """
    Helper fixture to load the content of the test memory file.
    """
    def _get_memory():
        with open(TEST_MEMORY_FILE, "r") as f:
            return json.load(f)
    return _get_memory

@pytest.fixture
def set_test_memory():
    """
    Helper fixture to manually set the content of the test memory file.
    """
    def _set_memory(data):
        with open(TEST_MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    return _set_memory