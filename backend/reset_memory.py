import requests
import os
from dotenv import load_dotenv

# Optional: Load from .env
load_dotenv()
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

RESET_MEMORY_URL = f"{BASE_URL}/reset-memory"
RESET_TRAITS_URL = f"{BASE_URL}/reset-traits"

def reset_memory():
    try:
        response = requests.post(RESET_MEMORY_URL)
        response.raise_for_status()
        print("✅ Memory reset successful:", response.json().get("message", "OK"))
    except requests.exceptions.RequestException as e:
        print("❌ Failed to reset memory:", str(e))

def reset_traits():
    try:
        response = requests.post(RESET_TRAITS_URL)
        response.raise_for_status()
        print("✅ Traits reset successful:", response.json().get("message", "OK"))
    except requests.exceptions.RequestException as e:
        print("❌ Failed to reset traits:", str(e))

if __name__ == "__main__":
    reset_memory()
    reset_traits()
