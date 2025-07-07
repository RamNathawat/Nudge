import os
import uuid
import json
import logging
import requests
import re
import concurrent.futures
from datetime import datetime
from typing import Optional, Dict, List

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

# --- Local project imports ---
from app.config import config
from app.web_scraper import scrape_search_engine, fetch_page_content
from app.utils import generate_gemini_response, generate_pdf, format_for_gemini, safe_bson_date
from app.auth import verify_token
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
    internal_monologue, belief_engine, goal_manager, curiosity_engine, dream_mode
)

# --- Proactive nudging ---
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.proactive_nudging import create_and_save_proactive_nudge

# ─────────────────────────────
# Setup
# ─────────────────────────────
load_dotenv()
GEMINI_URL = os.getenv("GEMINI_API_URL")
if not GEMINI_URL:
    raise RuntimeError("❌ GEMINI_API_URL not set in .env")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()
client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]

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
# Proactive Nudging + Dream Mode Scheduler
# ─────────────────────────────
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

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(
        check_for_proactive_nudges,
        trigger=IntervalTrigger(hours=1),
        id="proactive_nudge_job",
        name="Check and send proactive nudges",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: dream_mode.run_dream_cycle("ram_nathawat"), # Example user, should be dynamic if needed
        trigger=CronTrigger(hour=2, minute=30),
        id="dream_mode_job",
        name="NEMO nightly evolution",
        replace_existing=True
    )
    scheduler.start()
    logger.info("✅ Scheduler started (nudges + dream mode)")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logger.info("Scheduler shut down.")

# ─────────────────────────────
# Chat
# ─────────────────────────────
@app.post("/chat")
async def chat(message: Message, user_id: str = Depends(verify_token)):
    user_txt = message.message.strip()
    
    # ✅ Corrected: Removed timestamp argument
    add_message_to_memory(user_id=user_id, message=user_txt, sender="user")

    # --- Pre-computation ---
    flags = analyze_behavior(user_id, user_txt)
    emo_state = infer_emotional_state(user_txt, user_id)
    summary = summary_emotions(emo_state)
    for emotion, intensity in emo_state.items():
        update_trait(user_id, emotion, intensity)

    # --- NEMO Cognitive Cycle ---
    internal_monologue.generate_monologue(user_id, user_txt, summary)

    if "procrastinate" in user_txt.lower() or "again" in user_txt.lower():
        belief_engine.form_belief(
            user_id=user_id,
            belief_text="User struggles with task initiation under emotional fatigue",
            confidence=0.65,
            topic_tags=["habit", "emotion", "avoidance"]
        )

    goal_manager.evaluate_goals(user_id, user_txt)
    curiosity_engine.track_curiosity(user_id, user_txt, summary)

    # --- Context Preparation ---
    context_entries = get_relevant_memory(user_id)[:5]
    full_context = get_recent_history(user_id) + context_entries
    formatted_context = format_for_gemini(full_context)
    
    # --- System Prompt Injection ---
    formatted_context.insert(0, {
        "role": "user",
        "parts": [{
            "text": (
                "Important: Be concise, emotionally attuned, strategic, and sarcastic when needed. "
                "Always prioritize the user's growth, not comfort. 2-3 sentences max. "
                "Cut unnecessary filler, but keep personality intact. "
                "Be empathetic and supportive, but also witty and a bit sarcastic if you feel the user needs it or is sad or feeling negative emotions."
            )
        }]
    })
    formatted_context.append({"role": "user", "parts": [{"text": user_txt}]})

    # --- Gemini API Call ---
    headers = {"Content-Type": "application/json"}
    response_content = ""
    try:
        gemini_response_obj = {"contents": formatted_context}
        logger.info(f"Sending to Gemini API: {json.dumps(gemini_response_obj, indent=2)}")
        
        response = requests.post(GEMINI_URL, headers=headers, json=gemini_response_obj)
        response.raise_for_status()
        gemini_raw = response.json()
        logger.info(f"Raw Gemini API response: {json.dumps(gemini_raw, indent=2)}")

        if gemini_raw and "candidates" in gemini_raw and gemini_raw["candidates"]:
            parts = gemini_raw["candidates"][0].get("content", {}).get("parts", [])
            response_content = parts[0].get("text", "").strip() if parts else ""

        if not response_content:
            logger.warning("Gemini API returned an empty or unparseable response content.")
            response_content = "I'm thinking, but didn’t quite land that. Try again?"

    except requests.exceptions.RequestException as e:
        logger.error(f"Error communicating with Gemini API: {e}")
        raise HTTPException(status_code=500, detail=f"Error from Gemini API: {e}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from Gemini API response: {response.text}")
        raise HTTPException(status_code=500, detail="Invalid JSON response from Gemini API")
    except Exception as e:
        logger.error(f"[GEMINI ERROR] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Gemini API error")

    # --- Post-computation & Response ---
    # ✅ Corrected: Removed timestamp argument
    add_message_to_memory(user_id=user_id, message=response_content, sender="ai")
    return {"response": response_content}

# ─────────────────────────────
# NEMO Debug Endpoint
# ─────────────────────────────
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

# ─────────────────────────────
# Research Endpoints
# ─────────────────────────────
@app.post("/online_search")
async def online_search_endpoint(request: Request, user_id: str = Depends(verify_token)):
    try:
        data = await request.json()
        search_query = data.get('query', '')
        if not search_query:
            raise HTTPException(status_code=400, detail="No query provided")

        search_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            search_futures = [executor.submit(scrape_search_engine, search_query, engine) for engine in config.SEARCH_ENGINES]
            for future in concurrent.futures.as_completed(search_futures):
                search_results.extend(future.result())

        if not search_results:
            raise HTTPException(status_code=404, detail="No results found")
        
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
        
        # ✅ Corrected: Removed timestamp arguments
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
        if not search_query:
            raise HTTPException(status_code=400, detail="No query provided")

        all_summaries = []
        all_references = set()
        current_query = search_query
        
        for i in range(2):
            with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
                search_results = []
                search_futures = [executor.submit(scrape_search_engine, current_query, engine) for engine in config.SEARCH_ENGINES]
                for future in concurrent.futures.as_completed(search_futures):
                    search_results.extend(future.result())
                
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
                if refined_queries:
                    current_query = refined_queries[0].strip()

        report_prompt = config.DEEP_RESEARCH_REPORT_PROMPT.format(search_query=search_query, report_structure="**Structure:**\n- Introduction\n- Key Findings\n- Conclusion", summaries="\n\n".join(all_summaries))
        final_report = generate_gemini_response(report_prompt)

        pdf_buffer = generate_pdf(f"Deep Research Report: {search_query}", final_report, list(all_references))
        
        headers = {'Content-Disposition': f'attachment; filename="Nudge_Research_{search_query[:20]}.pdf"'}
        return StreamingResponse(iter([pdf_buffer.getvalue()]), media_type="application/pdf", headers=headers)

    except Exception as e:
        logging.error(f"Deep research error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────
# Memory and Trait Management
# ─────────────────────────────
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
    if delete_message_by_id(user_id, entry_id):
        return {"message": "Deleted"}
    raise HTTPException(404, "Message not found or not yours")

@app.patch("/memory/{entry_id}")
async def update_memory(entry_id: str, body: dict, user_id: str = Depends(verify_token)):
    if update_message_by_id(user_id, entry_id, body.get("content", "")):
        return {"message": "Updated"}
    raise HTTPException(404, "Message not found or not yours")

# ─────────────────────────────
# Utility & Admin Endpoints
# ─────────────────────────────
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