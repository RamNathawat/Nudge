import os
import json
from pymongo import MongoClient, errors

# Setup MongoDB client
uri = "mongodb+srv://Ram:8M8lCFAHyVkt89pf@nudge.m4ztyjg.mongodb.net/?retryWrites=true&w=majority&appName=Nudge"
client = MongoClient(uri)
db = client["Nudge"]
user_memory_collection = db["user_memory"]

# Construct absolute path to user_memory.json
json_path = os.path.join(os.path.dirname(__file__), "../../app/utils/user_memory.json")

try:
    with open(json_path, "r", encoding="utf-8") as f:
        memory_data = json.load(f)
except FileNotFoundError:
    print(f"❌ File not found: {json_path}")
    exit(1)
except json.JSONDecodeError as e:
    print(f"❌ Failed to decode JSON: {e}")
    exit(1)

# Validate structure
if "users" not in memory_data:
    print("❌ Invalid format: missing 'users' key in JSON")
    exit(1)

# Migrate users
migrated_count = 0
for user_id, user_data in memory_data["users"].items():
    if not isinstance(user_data, dict):
        print(f"⚠️ Skipping user {user_id}: Invalid format")
        continue

    doc = {"user_id": user_id, **user_data}
    try:
        user_memory_collection.update_one(
            {"user_id": user_id}, {"$set": doc}, upsert=True
        )
        migrated_count += 1
    except errors.PyMongoError as e:
        print(f"❌ MongoDB error for user {user_id}: {e}")

# Create helpful indexes
try:
    user_memory_collection.create_index("user_id")
    user_memory_collection.create_index("entries.timestamp")
    user_memory_collection.create_index("_traits.procrastination_tendency")
    user_memory_collection.create_index("_patterns.emotion_topic")
except errors.PyMongoError as e:
    print(f"❌ Index creation error: {e}")
    exit(1)

print(f"✅ Migration complete. {migrated_count} users migrated and indexes created.")
