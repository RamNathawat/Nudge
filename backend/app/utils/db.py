# app/utils/db.py
import os
import logging
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# MongoDB Connection Setup
# Get URI from environment variable
uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/") # Provide a default for local dev if not set

# Use AsyncIOMotorClient for asynchronous operations
client = AsyncIOMotorClient(uri, server_api=ServerApi('1'))

# Access the database and collection
db = client["Nudge"]
memory_collection = db["user_memories"] # This is the primary collection for user memories and traits

# Optional: Ping command at import time for immediate feedback
# In a real application, you might do this more robustly in an app startup hook
try:
    # Synchronous ping for immediate feedback, doesn't block event loop at import
    client.admin.command('ping')
    logger.info("Pinged your deployment. Successfully connected to MongoDB!")
except Exception as e:
    logger.error(f"MongoDB connection failed on import: {e}")