# backend/app/background_workers/learning_agent.py

import logging
import concurrent.futures

# Import the necessary modules from our application
from app.cognition import goal_manager, knowledge_graph_engine
from app.web_scraper import scrape_search_engine, fetch_page_content
from app.config import config

logger = logging.getLogger(__name__)

def run_learning_cycle():
    """
    The main function for the learning agent.
    This is designed to be called periodically by a scheduler.
    """
    logger.info("🤖 [Learning Agent] Waking up to check for learning goals...")

    # 1. Fetch a learning goal from the queue
    learning_goals = goal_manager.get_learning_goals(limit=1)
    if not learning_goals:
        logger.info("🤖 [Learning Agent] No active learning goals. Going back to sleep.")
        return

    goal = learning_goals[0]
    user_id = goal.get("user_id")
    goal_text = goal.get("goal")
    
    # Extract the topic from the goal text "Master Topic: Black Holes"
    topic_match = goal_text.split("Master Topic:")
    if len(topic_match) < 2:
        logger.error(f"Could not parse topic from goal: {goal_text}")
        # Mark goal as failed to avoid getting stuck
        goal_manager.update_goal_status(user_id, goal_text, "failed")
        return

    topic = topic_match[1].strip()
    logger.info(f"🤖 [Learning Agent] Picked up goal: Master Topic '{topic}'")

    try:
        # 2. Perform exhaustive research (The "Librarian" task)
        search_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            # Scrape multiple search engines for comprehensive results
            search_futures = [executor.submit(scrape_search_engine, topic, engine) for engine in config.SEARCH_ENGINES]
            for future in concurrent.futures.as_completed(search_futures):
                search_results.extend(future.result())

        unique_urls = list(set(search_results))
        logger.info(f"📚 Found {len(unique_urls)} unique URLs for '{topic}'. Fetching content...")

        all_text_content = ""
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            # Fetch content from the top URLs
            fetch_futures = {executor.submit(fetch_page_content, url): url for url in unique_urls[:10]} # Limit to top 10 to be manageable
            for future in concurrent.futures.as_completed(fetch_futures):
                snippets, _ = future.result()
                if snippets:
                    all_text_content += "\n\n".join(snippets)

        if not all_text_content:
            logger.warning(f"No content fetched for topic '{topic}'. Marking goal as failed.")
            goal_manager.update_goal_status(user_id, goal_text, "failed")
            return

        # 3. Synthesize and load into Knowledge Graph
        # This calls the advanced prototype we built
        knowledge_graph_engine.synthesizer_agent.process_and_load_text(
            text=all_text_content,
            source_topic=topic
        )

        # 4. Mark goal as complete
        goal_manager.update_goal_status(user_id, goal_text, "complete")
        logger.info(f"✅ [Learning Agent] Successfully completed goal for topic: '{topic}'")

    except Exception as e:
        logger.error(f"🤖 [Learning Agent] Error while processing topic '{topic}': {e}", exc_info=True)
        goal_manager.update_goal_status(user_id, goal_text, "failed")