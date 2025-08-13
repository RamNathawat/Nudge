# backend/app/background_workers/learning_agent.py

import logging
import concurrent.futures
import re
from typing import List, Tuple
from app.cognition import goal_manager, knowledge_graph_engine, orchestrator_agent
from app.services.research_service import perform_deep_research

logger = logging.getLogger(__name__)

def _parse_synthesis_goal(goal_text: str) -> Tuple[List[str], str]:
    """
    Parses the goal text to extract topics and the original question.
    VERSION 2: Uses more robust regex to handle complex/messy goal text.
    """
    try:
        domain_match = re.search(r"domains:\s*(.*?)\.\s*This is to answer", goal_text, re.DOTALL)
        question_match = re.search(r"question:\s*'(.*?)'", goal_text, re.DOTALL)

        if domain_match and question_match:
            domains_str = domain_match.group(1).replace("\n", " ")
            domains = [d.strip().strip("'") for d in domains_str.split(',')]
            original_question = question_match.group(1)
            return domains, original_question
    except Exception as e:
        logger.error(f"Error during robust parsing of goal text: {e}")

    topic_match = goal_text.split("Master Topic:")
    if len(topic_match) > 1:
        topic = topic_match[1].strip()
        return [topic], f"General knowledge about {topic}"
        
    return None, None

def process_single_goal(goal: dict):
    """
    Processes a single learning goal from start to finish.
    VERSION 4: Simplifies research query and includes feedback loop.
    """
    user_id = goal.get("user_id")
    goal_text = goal.get("goal")
    
    topics, original_question = _parse_synthesis_goal(goal_text)
    
    if not topics:
        logger.error(f"🤖 [Learning Agent] Could not parse topics from goal: {goal_text}")
        goal_manager.update_goal_status(user_id, goal_text, "failed")
        return

    logger.info(f"🤖 [Learning Agent] Picked up goal for topics: {topics}")

    if len(topics) > 1:
        research_query = f"intersection of {', '.join(topics)}"
        logger.info(f"🤖 [Learning Agent] Performing simplified multi-domain research for: '{research_query}'")
    else:
        research_query = topics[0]
    
    try:
        comprehensive_text = perform_deep_research(research_query)
        if not comprehensive_text:
            logger.error(f"🤖 [Learning Agent] Deep research for query '{research_query}' returned no content. Failing goal.")
            goal_manager.update_goal_status(user_id, goal_text, "failed")
            return

        knowledge_graph_engine.synthesizer_agent.process_and_load_text(
            text=comprehensive_text, source_topics=topics
        )
        
        all_mastered = all(orchestrator_agent._is_topic_mastered(topic, context_domains=topics) for topic in topics)

        if all_mastered:
            goal_manager.update_goal_status(user_id, goal_text, "complete")
            logger.info(f"✅ [Learning Agent] Mastery achieved and goal completed for topics: {topics}")
            orchestrator_agent.check_and_resolve_pending_questions(user_id)
        else:
            logger.warning(f"⚠️ [Learning Agent] Research performed for topics {topics}, but mastery not yet achieved. The goal will be re-processed on the next cycle.")

    except Exception as e:
        logger.error(f"🤖 [Learning Agent] Error while processing goal '{goal_text}': {e}", exc_info=True)
        goal_manager.update_goal_status(user_id, goal_text, "failed")

def run_learning_cycle():
    """The main function for the learning agent."""
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