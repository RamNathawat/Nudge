import requests

# Local backend URL
RESET_URL = "http://localhost:8000/reset-memory"

try:
    response = requests.post(RESET_URL)
    response.raise_for_status()
    print("✅ Memory reset successful:", response.json()["message"])
except requests.exceptions.RequestException as e:
    print("❌ Failed to reset memory:", str(e))
