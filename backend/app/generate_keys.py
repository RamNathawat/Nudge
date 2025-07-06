# backend/generate_keys.py

from pywebpush import Vapid

try:
    # This creates a new Vapid key pair.
    v = Vapid.from_new_keypair()

    # Retrieve the keys as a dictionary.
    # The `.vapid_keys` attribute holds an object with public_key and private_key
    keys = v.vapid_keys

    print("--- VAPID Keys Generated Successfully ---")
    print("Copy the following two lines into your .env file:\n")
    print("VAPID_PUBLIC_KEY=" + keys.public_key)
    print("VAPID_PRIVATE_KEY=" + keys.private_key)

except Exception as e:
    print(f"An error occurred: {e}")
    print("Please ensure you have run 'pip install -r requirements.txt' in your virtual environment.")