# backend/app/background_workers/learning_agent.py

import logging
import concurrent.futures
from app.cognition import goal_manager, knowledge_graph_engine, orchestrator_agent
from app.services.research_service import perform_deep_research

logger = logging.getLogger(__name__)

def process_single_goal(goal: dict):
    """Processes a single learning goal from start to finish."""
    user_id = goal.get("user_id")
    goal_text = goal.get("goal")
    
    topic_match = goal_text.split("Master Topic:")
    if len(topic_match) < 2:
        goal_manager.update_goal_status(user_id, goal_text, "failed")
        return

    topic = topic_match[1].strip()
    logger.info(f"🤖 [Learning Agent] Picked up goal: Master Topic '{topic}'")

    try:
        comprehensive_text = perform_deep_research(topic)
        if not comprehensive_text:
            goal_manager.update_goal_status(user_id, goal_text, "failed")
            return

        knowledge_graph_engine.synthesizer_agent.process_and_load_text(
            text=comprehensive_text, source_topic=topic
        )
        goal_manager.update_goal_status(user_id, goal_text, "complete")
        logger.info(f"✅ [Learning Agent] Successfully completed goal for topic: '{topic}'")
        
        orchestrator_agent.check_and_resolve_pending_questions(user_id)

    except Exception as e:
        logger.error(f"🤖 [Learning Agent] Error while processing topic '{topic}': {e}", exc_info=True)
        goal_manager.update_goal_status(user_id, goal_text, "failed")

def run_learning_cycle():
    """The main function for the learning agent, capable of parallel processing."""
    logger.info("🤖 [Parallel Learning Agent] Waking up to check for learning goals...")

    learning_goals = goal_manager.get_learning_goals(limit=5)
    if not learning_goals:
        logger.info("🤖 [Parallel Learning Agent] No active learning goals. Going back to sleep.")
        return

    logger.info(f"🤖 [Parallel Learning Agent] Found {len(learning_goals)} goals to process.")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_goal = {executor.submit(process_single_goal, goal): goal for goal in learning_goals}
        
        for future in concurrent.futures.as_completed(future_to_goal):
            goal = future_to_goal[future]
            try:
                future.result()
            except Exception as exc:
                logger.error(f"A goal for topic '{goal.get('goal')}' generated an exception: {exc}")

    logger.info("🤖 [Parallel Learning Agent] Finished processing current batch of goals.")