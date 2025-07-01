# app/user_profile_inference.py

from app.memory import update_trait
from app.nlp_analysis import extract_topic_tags
from typing import Dict

def infer_user_name(user_id: str, user_input: str):
    """
    Simple heuristic: If user says something like "My name is ___" or "I'm ___", extract and save name.
    """
    lowered = user_input.lower()
    if "my name is" in lowered:
        name = user_input.split("my name is")[-1].strip().split()[0].capitalize()
        update_trait(user_id, "user_name", name)
    elif "i'm " in lowered or "i am " in lowered:
        after = user_input.split("i'm")[-1] if "i'm" in lowered else user_input.split("i am")[-1]
        name = after.strip().split()[0].capitalize()
        update_trait(user_id, "user_name", name)

def infer_user_topics(user_id: str, user_input: str):
    """
    Extract topics from user messages and track them as favorite topics (long-term trait building).
    """
    topics = extract_topic_tags(user_input)
    if topics:
        for topic in topics:
            trait_key = f"interest_{topic.lower()}"
            update_trait(user_id, trait_key, True)

def update_user_profile(user_id: str, user_input: str):
    infer_user_name(user_id, user_input)
    infer_user_topics(user_id, user_input)
