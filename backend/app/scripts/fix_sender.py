import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
db = client["nudge_db"]
entries = db["entries"]

updated = 0
for entry in entries.find({"sender": {"$exists": False}}):
    content = entry.get("content", "").lower()
    guessed_sender = "ai" if "ram" in content or content.startswith(("alright", "hey", "so", "ok")) else "user"
    entries.update_one({"_id": entry["_id"]}, {"$set": {"sender": guessed_sender}})
    updated += 1

print(f"✅ Sender backfill complete. Updated {updated} entries.")
