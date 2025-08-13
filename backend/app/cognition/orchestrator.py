# backend/app/cognition/orchestrator.py

import logging
import re
from datetime import datetime
from pymongo import MongoClient
from app.services.graph_db_connector import graph_db_connector
from app.utils import generate_gemini_response
from . import goal_manager
from .thinker_agent import thinker_agent

logger = logging.getLogger(__name__)

client = MongoClient("mongodb://localhost:27017/")
db = client["nudge_db"]
pending_questions_collection = db["pending_questions"]

class Orchestrator:
    """
    A meta-agent that deconstructs complex, multi-domain problems and
    orchestrates other AI agents to learn the required knowledge and
    synthesize a solution.
    VERSION 4: Implements a more flexible 'mastery' check based on shared concepts.
    """
    def __init__(self):
        self.db_connector = graph_db_connector

    def _identify_knowledge_domains(self, question: str) -> list:
        """
        Uses an LLM to identify the necessary knowledge domains for a question.
        """
        try:
            prompt = f"""
            Analyze the following question and identify the distinct, high-level fields of knowledge required to answer it.
            For example, for "How can quantum mechanics explain consciousness?", the domains are ["Quantum Mechanics", "Neuroscience", "Philosophy of Mind"].

            Question: "{question}"

            Return the domains as a Python list of strings.
            """
            response_str = generate_gemini_response(prompt)
            match = re.search(r'\[.*?\]', response_str)
            if match:
                domains = eval(match.group(0))
                if domains:
                    logger.info(f"Orchestrator successfully identified domains via LLM: {domains}")
                    return domains
        except Exception as e:
            logger.error(f"Orchestrator: LLM-based domain identification failed: {e}. Proceeding to fallback.")

        logger.warning("Falling back to keyword-based domain extraction.")
        capitalized_words = re.findall(r'\b[A-Z][a-zA-Z]*\b', question)
        quoted_phrases = re.findall(r"'(.*?)'", question)
        
        fallback_domains = capitalized_words + quoted_phrases
        unique_domains = list(dict.fromkeys(d.strip() for d in fallback_domains if len(d) > 2))
        
        if unique_domains:
            logger.info(f"Orchestrator identified domains via fallback: {unique_domains}")
            return unique_domains
        else:
            return []

    def _is_topic_mastered(self, topic: str, context_domains: list = None) -> bool:
        """
        Checks if a topic is sufficiently learned.
        For synthesis tasks, mastery is defined by having a sufficient number
        of shared conceptual neighbors with other topics in the context.
        """
        if context_domains and len(context_domains) > 1:
            other_domains = [d for d in context_domains if d != topic]
            if not other_domains:
                pass
            else:
                query = """
                MATCH (t1:Topic {name: $topic})--(neighbor)
                MATCH (t2:Topic)--(neighbor)
                WHERE t2.name IN $other_domains
                RETURN count(DISTINCT neighbor) AS shared_neighbors
                """
                try:
                    results = self.db_connector.run_query(query, parameters={"topic": topic, "other_domains": other_domains})
                    if results and results[0]["shared_neighbors"] >= 2:
                        logger.info(f"✅ Orchestrator: Topic '{topic}' is considered mastered for synthesis (found {results[0]['shared_neighbors']} shared neighbors).")
                        return True
                    else:
                        logger.warning(f"Orchestrator: Topic '{topic}' is not yet mastered for synthesis. Shared neighbors: {results[0]['shared_neighbors'] if results else 0}.")
                        return False
                except Exception as e:
                    logger.error(f"Failed to check mastery path for topic '{topic}': {e}")
                    return False

        fallback_query = "MATCH (t:Topic {name: $topic}) OPTIONAL MATCH (t)<--(n) RETURN count(n) AS connections"
        try:
            results = self.db_connector.run_query(fallback_query, parameters={"topic": topic})
            if results and results[0]["connections"] >= 5:
                logger.info(f"✅ Orchestrator: Topic '{topic}' is considered mastered (found {results[0]['connections']} connections).")
                return True
        except Exception as e:
            logger.error(f"Failed to check fallback mastery for topic '{topic}': {e}")

        logger.warning(f"Orchestrator: Topic '{topic}' is not yet mastered (fallback check).")
        return False

    def solve_multi_domain_problem(self, user_id: str, question: str, domains_override: list = None) -> str:
        """The main orchestration function."""
        logger.info(f"Orchestrator: Solving multi-domain problem: '{question}'")

        domains = domains_override if domains_override else self._identify_knowledge_domains(question)
        if not domains:
            return "I'm having trouble understanding the core topics of your question. Could you rephrase it?"

        logger.info(f"Orchestrator: Using required domains: {domains}")
        
        unmastered_domains = [d for d in domains if not self._is_topic_mastered(d, context_domains=domains)]
        
        if unmastered_domains:
            goal_text = f"Synthesize a coherent insight connecting the following domains: {', '.join(unmastered_domains)}. This is to answer the user's question: '{question}'"
            
            existing_goal = goal_manager.goals_collection.find_one({
                "user_id": user_id,
                "goal": goal_text,
                "status": {"$in": ["in_progress", "failed", "paused"]}
            })

            if existing_goal:
                logger.warning(f"A goal for this synthesis already exists (status: {existing_goal.get('status')}). Not creating a new one.")
            else:
                 goal_manager.create_goal(
                    user_id=user_id,
                    goal_text=goal_text,
                    goal_type="deep_learning"
                )
            
            if not pending_questions_collection.find_one({"original_question": question, "status": "pending_learning"}):
                pending_questions_collection.insert_one({
                    "user_id": user_id, "original_question": question,
                    "required_domains": domains, "status": "pending_learning",
                    "created_at": datetime.utcnow()
                })
            domains_to_learn = ', '.join(unmastered_domains)
            return f"That's a fascinating question that connects multiple fields. I need to do some deep research on '{domains_to_learn}' before I can give you a thoughtful answer. Please ask me again in about 15-20 minutes."

        if len(domains) > 1:
            return thinker_agent.generate_cross_domain_synthesis(user_id, domains)
        
        from .inference_engine import inference_engine
        return inference_engine.answer_complex_question(question)

    def check_and_resolve_pending_questions(self, user_id: str):
        """Checks if any pending questions can now be answered and sends a proactive message."""
        logger.info(f"Orchestrator: Checking pending questions for user {user_id}...")
        pending_questions = list(pending_questions_collection.find({"user_id": user_id, "status": "pending_learning"}))

        for question_doc in pending_questions:
            required_domains = question_doc.get("required_domains", [])
            all_mastered = all(self._is_topic_mastered(domain, context_domains=required_domains) for domain in required_domains)

            if all_mastered:
                logger.info(f"All domains for question '{question_doc['_id']}' are now mastered. Answering proactively.")
                final_answer = self.solve_multi_domain_problem(user_id, question_doc["original_question"], domains_override=required_domains)

                if final_answer and "I need to do some deep research" not in final_answer:
                    from app.memory import add_message_to_memory
                    proactive_message = f"I've finished my research regarding your question about '{question_doc['original_question']}'. Here's what I've come up with:\n\n{final_answer}"
                    add_message_to_memory(user_id, proactive_message, sender="ai")
                    logger.info("Sent proactive answer to user for completed pending question.")
                    pending_questions_collection.update_one({"_id": question_doc["_id"]}, {"$set": {"status": "answered"}})

orchestrator_agent = Orchestrator()