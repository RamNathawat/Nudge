# backend/app/main.py

import os
import uuid
import json
import logging
import requests
import re
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, List

# Load environment variables at the very beginning
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient

# --- Local project imports ---
# Import your existing application modules
from app.config import config
from app.utils import generate_gemini_response, generate_pdf, format_for_gemini, safe_bson_date
# The verify_token from your original main.py is used for other routes
from app.auth import verify_token
from app.web_scraper import scrape_search_engine, fetch_page_content
from app.memory import (
    get_user_memory, add_message_to_memory, get_recent_history, update_trait,
    get_traits, get_relevant_memory, is_safe_space_mode_enabled, set_safe_space_mode,
    delete_message_by_id, update_message_by_id, entries_collection, traits_collection
)
from app.behaviour_analyzer import analyze_behavior
from app.state_inference import infer_emotional_state, summary_emotions
from app.nudge_scoring import calculate_nudging_score
from app.dark_nudge_engine import generate_dark_nudge

# --- NEMO Cognitive modules ---
from app.cognition import (
    internal_monologue, belief_engine, goal_manager, curiosity_engine, dream_mode,
    inference_engine,
    orchestrator_agent 
)

# --- Proactive nudging & Background Workers ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.proactive_nudging import create_and_save_proactive_nudge
from app.background_workers import learning_agent

# --- [CRITICAL] Import the authentication router ---
# Make sure auth.py is in the same 'app' directory
from app import auth as auth_router

# ─────────────────────────────
# Application Setup
# ─────────────────────────────
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

# Initialize the FastAPI app
app = FastAPI(
    title="Nudge AI API",
    description="The complete backend service for the Nudge AI application.",
    version="1.0.0"
)

# --- [CRITICAL] CORS Middleware ---
# This allows your React frontend to communicate with this backend.
# In production, you might want to restrict origins to your actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Logging Configuration ---
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Database Connection ---
# It's good practice to establish the client connection once.
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["nudge_db"]

# --- [CRITICAL] Include Authentication Routes ---
# This line makes /auth/login and /auth/signup available to your app
app.include_router(auth_router.router)


class Message(BaseModel):
    message: str

# Helper to serialize ObjectId and datetime for JSON dumping
def json_serializer_for_mongo_types(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

# ─────────────────────────────
# Scheduler for Background Tasks
# ─────────────────────────────
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(check_for_proactive_nudges, trigger=IntervalTrigger(hours=1), id="proactive_nudge_job", name="Check and send proactive nudges", replace_existing=True)
    scheduler.add_job(lambda: dream_mode.run_dream_cycle("ram_nathawat"), trigger=CronTrigger(hour=2, minute=30), id="dream_mode_job", name="NEMO nightly evolution", replace_existing=True)
    scheduler.add_job(learning_agent.run_learning_cycle, trigger=IntervalTrigger(minutes=15), id="learning_agent_job", name="Background learning and knowledge synthesis", replace_existing=True)
    scheduler.start()
    logger.info("✅ Scheduler started (nudges + dream mode + learning agent)")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

async def check_for_proactive_nudges():
    """The job that the scheduler will run."""
    logger.info(f"Scheduler running job at {datetime.now()}...")
    all_user_ids = [doc['user_id'] for doc in traits_collection.find({}, {'user_id': 1})]
    for user_id in all_user_ids:
        logger.info(f"Checking user {user_id} for proactive nudge...")
        try:
            message = create_and_save_proactive_nudge(user_id)
            if message:
                logger.info(f"[NUDGE] Sent to {user_id}: '{message}'")
        except Exception as e:
            logger.error(f"[NUDGE ERROR] {user_id}: {e}", exc_info=True)


# ─────────────────────────────
# Core Application Routes
# ─────────────────────────────

def _create_context_summary(history_slice: List[Dict]) -> Optional[str]:
    if not GEMINI_URL or len(history_slice) < 2: return None
    summary_prompt_text = "You are a context summarizer. Briefly summarize the key points, user intent, and emotional tone of the following conversation turns in a single, concise sentence. Focus on the most recent exchange.\n\n"
    for entry in history_slice:
        sender = "AI" if entry.get("sender") == "ai" else "User"
        summary_prompt_text += f"{sender}: {entry.get('content')}\n"
    summary_prompt_text += "\nOne-sentence summary:"
    try:
        summary = generate_gemini_response(summary_prompt_text)
        logging.info(f"✅ Generated context summary: '{summary}'")
        return summary
    except Exception as e:
        logging.error(f"[CONTEXT_SUMMARY_ERROR] {e}")
        return None

def _classify_question_type(text: str) -> str:
    """
    Uses an LLM to classify the user's input into a specific category to route it to the correct engine.
    """
    prompt = f"""
    Analyze the user's message and classify its primary intent into one category:
    1.  **multi_domain_synthesis**: Asks to connect/combine/model ideas from two or more distinct fields (e.g., "How does Game Theory apply to psychology?", "Use Stoicism to design a system...").
    2.  **complex_question**: Asks a factual question within a single topic (e.g., "Who was involved with the Manhattan Project?", "What is the history of Stoicism?").
    3.  **standard_chat**: A normal conversation, expressing feelings, or a simple command.

    User Message: "{text}"
    Category:"""
    try:
        classification = generate_gemini_response(prompt).lower().strip().replace("*", "")
        logger.info(f"Triage classified question as: '{classification}'")
        if "multi_domain_synthesis" in classification:
            return "multi_domain_synthesis"
        if "complex_question" in classification:
            return "complex_question"
    except Exception as e:
        logger.error(f"Failed to classify question type: {e}")
    return "standard_chat"

@app.post("/chat")
async def chat(message: Message, user_id: str = Depends(verify_token)):
    user_txt = message.message.strip()
    add_message_to_memory(user_id=user_id, message=user_txt, sender="user")

    question_type = _classify_question_type(user_txt)

    if question_type == "multi_domain_synthesis":
        logger.info("Multi-domain problem detected. Routing to Orchestrator.")
        response_content = orchestrator_agent.solve_multi_domain_problem(user_id, user_txt)
    elif question_type == "complex_question":
        logger.info("Complex question detected. Routing to Inference Engine.")
        response_content = inference_engine.answer_complex_question(user_txt)
    else:
        # Standard Chat Flow
        logger.info("Standard chat detected. Proceeding with normal flow.")
        flags = analyze_behavior(user_id, user_txt)
        emo_state = infer_emotional_state(user_txt, user_id)
        internal_monologue.generate_monologue(user_id, user_txt, summary_emotions(emo_state))
        curiosity_engine.track_curiosity(user_id, user_txt, summary_emotions(emo_state))
        
        full_history = get_recent_history(user_id, limit=10)
        context_summary = _create_context_summary(full_history[-4:])
        formatted_context = format_for_gemini(full_history)
        
        system_prompt = {"role": "user", "parts": [{"text": ("Important: Be concise, emotionally attuned, strategic, and sarcastic when needed. Always prioritize the user's growth, not comfort. 2-3 sentences max. Cut unnecessary filler, but keep personality intact. Be empathetic and supportive, but also witty and a bit sarcastic if you feel the user needs it or is sad or feeling negative emotions.")}]}
        
        final_context = [system_prompt]
        if context_summary:
            final_context.append({"role": "user", "parts": [{"text": f"INTERNAL CONTEXT: {context_summary}"}]})
        final_context.extend(formatted_context)
        final_context.append({"role": "user", "parts": [{"text": user_txt}]})
        
        try:
            gemini_response_obj = {"contents": final_context}
            response = requests.post(GEMINI_URL, headers={"Content-Type": "application/json"}, json=gemini_response_obj)
            response.raise_for_status()
            gemini_raw = response.json()
            response_content = gemini_raw["candidates"][0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if gemini_raw.get("candidates") else "I'm thinking..."
        except Exception as e:
            logger.error(f"[GEMINI CHAT ERROR] {e}", exc_info=True)
            response_content = "Sorry, I'm having a little trouble connecting right now."

    add_message_to_memory(user_id=user_id, message=response_content, sender="ai")
    return {"response": response_content}

@app.get("/debug_nemo_mind")
async def debug_nemo_mind(user_id: str = Depends(verify_token)):
    try:
        beliefs = list(db["beliefs"].find({"user_id": user_id}).sort("confidence", -1).limit(10))
        curiosities = list(db["curiosity_traces"].find({"user_id": user_id, "status": "unresolved"}).sort("priority", -1))
        monologues = list(db["internal_monologues"].find({"user_id": user_id}).sort("generated_at", -1).limit(5))
        goals = list(db["ai_goals"].find({"user_id": user_id, "status": "in_progress"}))

        return {
            "beliefs": [{"belief": b["belief"], "confidence": b["confidence"], "tags": b.get("topic_tags", [])} for b in beliefs],
            "curiosity_queue": [{"question": c["question"], "priority": c["priority"], "trigger": c.get("emotion_trigger", "none")} for c in curiosities],
            "recent_monologues": [{"thought": m["thought"], "doubt": m["doubt_level"], "emotion": m.get("emotion_trigger")} for m in monologues],
            "active_goals": [{"goal": g["goal"], "strategy": g.get("strategy"), "deadline": g.get("deadline")} for g in goals]
        }
    except Exception as e:
        logger.error(f"[DEBUG NEMO] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to introspect NEMO mind")

@app.post("/online_search")
async def online_search_endpoint(request: Request, user_id: str = Depends(verify_token)):
    try:
        data = await request.json()
        search_query = data.get('query', '')
        if not search_query: raise HTTPException(status_code=400, detail="No query provided")
        search_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            search_futures = [executor.submit(scrape_search_engine, search_query, engine) for engine in config.SEARCH_ENGINES]
            for future in concurrent.futures.as_completed(search_futures):
                search_results.extend(future.result())
        if not search_results: raise HTTPException(status_code=404, detail="No results found")
        unique_urls = list(set(search_results))
        content_snippets = []
        references = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            fetch_futures = {executor.submit(fetch_page_content, url): url for url in unique_urls[:10]}
            for future in concurrent.futures.as_completed(fetch_futures):
                snippets, refs = future.result()
                content_snippets.extend(snippets)
                references.extend(refs)
        combined_content = "\n\n".join(content_snippets)
        prompt = f"Analyze web content for: '{search_query}'. Extract key facts and details. Be concise. Content:\n\n{combined_content}"
        explanation = generate_gemini_response(prompt)
        add_message_to_memory(user_id=user_id, message=f"Searched for: {search_query}", sender="user")
        add_message_to_memory(user_id=user_id, message=explanation, sender="ai")
        return {"explanation": explanation, "references": references}
    except Exception as e:
        logging.error(f"Online search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deep_research")
async def deep_research_endpoint(request: Request, user_id: str = Depends(verify_token)):
    try:
        data = await request.json()
        search_query = data.get('query', '')
        if not search_query: raise HTTPException(status_code=400, detail="No query provided")
        all_summaries, all_references, current_query = [], set(), search_query
        for i in range(2):
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
                search_results = []
                search_futures = [executor.submit(scrape_search_engine, current_query, engine) for engine in config.SEARCH_ENGINES]
                for future in concurrent.futures.as_completed(search_futures): search_results.extend(future.result())
                unique_urls = list(set(search_results) - all_references)
                all_references.update(unique_urls)
                fetch_futures = {executor.submit(fetch_page_content, url): url for url in unique_urls[:5]}
                for future in concurrent.futures.as_completed(fetch_futures):
                    snippets, _ = future.result()
                    if snippets:
                        summary_prompt = config.DEEP_RESEARCH_SUMMARY_PROMPT.format(query=current_query) + "\n\n" + "\n".join(snippets)
                        summary = generate_gemini_response(summary_prompt)
                        all_summaries.append(summary)
            if i < 1 and all_summaries:
                refinement_prompt = config.DEEP_RESEARCH_REFINEMENT_PROMPT.format(original_query=search_query) + "\n\n" + "\n".join(all_summaries)
                refined_queries = generate_gemini_response(refinement_prompt).split('\n')
                if refined_queries: current_query = refined_queries[0].strip()
        report_prompt = config.DEEP_RESEARCH_REPORT_PROMPT.format(search_query=search_query, report_structure="**Structure:**\n- Introduction\n- Key Findings\n- Conclusion", summaries="\n\n".join(all_summaries))
        final_report = generate_gemini_response(report_prompt)
        pdf_buffer = generate_pdf(f"Deep Research Report: {search_query}", final_report, list(all_references))
        headers = {'Content-Disposition': f'attachment; filename="Nudge_Research_{search_query[:20]}.pdf"'}
        return StreamingResponse(iter([pdf_buffer.getvalue()]), media_type="application/pdf", headers=headers)
    except Exception as e:
        logging.error(f"Deep research error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory")
async def get_memory(user_id: str = Depends(verify_token), offset: int = 0, limit: int = 20):
    memory_data = get_user_memory(user_id, offset, limit)
    if "messages" in memory_data and isinstance(memory_data["messages"], list):
        for entry in memory_data["messages"]:
            if "_id" in entry and isinstance(entry["_id"], ObjectId):
                entry["_id"] = str(entry["_id"])
            if "timestamp" in entry and isinstance(entry["timestamp"], datetime):
                entry["timestamp"] = safe_bson_date(entry["timestamp"])
    return {"memory": memory_data}

@app.get("/traits")
async def get_user_traits(user_id: str = Depends(verify_token)):
    traits = get_traits(user_id)
    return {"traits": traits}

@app.delete("/memory/{entry_id}")
async def delete_memory_entry(entry_id: str, user_id: str = Depends(verify_token)):
    if delete_message_by_id(user_id, entry_id): return {"message": "Deleted"}
    raise HTTPException(404, "Message not found or not yours")

@app.patch("/memory/{entry_id}")
async def update_memory(entry_id: str, body: dict, user_id: str = Depends(verify_token)):
    if update_message_by_id(user_id, entry_id, body.get("content", "")): return {"message": "Updated"}
    raise HTTPException(404, "Message not found or not yours")

@app.post("/reset-memory")
def reset_memory():
    entries_collection.delete_many({})
    return {"message": "All memory entries wiped"}

@app.post("/reset-traits")
def reset_traits():
    traits_collection.delete_many({})
    return {"message": "All user traits wiped"}

@app.post("/safe-space-mode")
def toggle_safe_space(enabled: bool, user_id: str = Depends(verify_token)):
    set_safe_space_mode(user_id, bool(enabled))
    return {"status": "ok", "safe_space_mode": enabled}
