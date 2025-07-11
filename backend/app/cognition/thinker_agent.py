# backend/app/cognition/thinker_agent.py

import logging
import re
from typing import Tuple, List

from app.services.graph_db_connector import graph_db_connector
from app.utils import generate_gemini_response
# --- THIS IS THE FIX ---
# Instead of importing from 'app.cognition', we import from the local directory.
from . import belief_engine 

logger = logging.getLogger(__name__)

class ThinkerAgent:
    def __init__(self, coherence_threshold=7):
        self.db_connector = graph_db_connector
        self.coherence_threshold = coherence_threshold

    def _get_core_concepts(self, topic: str) -> list:
        query = f"MATCH (t:Topic {{name: $topic}})<-[:MENTIONED_IN]-(c) RETURN c.name, c.mentions AS mentions ORDER BY mentions DESC LIMIT 5"
        try:
            results = self.db_connector.run_query(query, parameters={"topic": topic})
            return [record["c.name"] for record in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get core concepts for {topic}: {e}")
            return []

    def _critique_hypothesis(self, hypothesis: str) -> Tuple[bool, str]:
        prompt = f"""
        You are a skeptical, rigorous logician. Analyze the following creative hypothesis.
        Provide your output in this exact format:
        Critique: [Your brief critique here]
        Coherence Score: [A single number from 1 to 10]
        """
        response = generate_gemini_response(prompt)
        try:
            critique = re.search(r"Critique: (.*)", response, re.DOTALL).group(1).strip()
            score = int(re.search(r"Coherence Score: (\d+)", response).group(1).strip())
            is_coherent = score >= self.coherence_threshold
            return is_coherent, critique
        except Exception as e:
            logger.error(f"Could not parse logician's critique: {e}")
            return False, "Failed to parse critique."
    
    def _select_best_pair_for_synthesis(self, domains: List[str]) -> Tuple[str, str]:
        if len(domains) == 2:
            return domains[0], domains[1]
            
        prompt = f"""
        From the list of knowledge domains, select the two most promising for a surprising creative synthesis.
        Domains: {domains}
        Return the two selected domains as a Python list of strings.
        """
        response_str = generate_gemini_response(prompt)
        try:
            match = re.search(r'\[.*?\]', response_str)
            pair = eval(match.group(0)) if match else []
            if len(pair) == 2:
                return pair[0], pair[1]
        except:
            pass
        return domains[0], domains[1]

    def generate_cross_domain_synthesis(self, user_id: str, domains: List[str]) -> str:
        if len(domains) < 2:
            return "I need at least two mastered topics to generate a meaningful synthesis."
            
        topic_a, topic_b = self._select_best_pair_for_synthesis(domains)
        logger.info(f"🎨 [Thinker Agent] Synthesizing '{topic_a}' and '{topic_b}'.")
        
        concepts_a = self._get_core_concepts(topic_a)
        concepts_b = self._get_core_concepts(topic_b)

        if not concepts_a or not concepts_b:
            return f"My apologies, I haven't mastered '{topic_a}' or '{topic_b}' enough to form a novel connection yet."

        muse_prompt = f"""
        Generate a novel, non-obvious hypothesis connecting two fields.
        Field A: {topic_a} (Core Concepts: {', '.join(concepts_a)})
        Field B: {topic_b} (Core Concepts: {', '.join(concepts_b)})
        Propose a speculative hypothesis with a creative name and clear explanation. Be unconventional.
        """
        novel_synthesis = generate_gemini_response(muse_prompt)
        if not novel_synthesis:
            return "My 'muse' is on a break. I couldn't generate an initial idea."

        is_coherent, critique = self._critique_hypothesis(novel_synthesis)

        if is_coherent:
            belief_text = f"Prometheus Contemplation: {novel_synthesis}"
            belief_engine.form_belief(
                user_id=user_id,
                belief_text=belief_text,
                source="thinker_agent_synthesis",
                confidence=0.6,
                topic_tags=[topic_a.lower(), topic_b.lower(), "synthesis"]
            )
            return f"After some internal debate, I've developed a coherent hypothesis connecting '{topic_a}' and '{topic_b}':\n\n{novel_synthesis}"
        else:
            return f"I generated an idea connecting '{topic_a}' and '{topic_b}', but my 'inner logician' found it incoherent, pointing out that: \"{critique}\". I'll keep thinking about it."

thinker_agent = ThinkerAgent()