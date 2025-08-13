# backend/app/cognition/thinker_agent.py

import logging
import re
from typing import Tuple, List
from app.services.graph_db_connector import graph_db_connector
from app.utils import generate_gemini_response
from . import belief_engine

logger = logging.getLogger(__name__)

class ThinkerAgent:
    """
    An agent capable of Level 4 Synthesis, now with a more robust
    Internal Dialectic to ensure coherent idea generation.
    VERSION 2: Handles N-Domain Synthesis.
    """
    def __init__(self, coherence_threshold=7, max_refinement_cycles=2):
        self.db_connector = graph_db_connector
        self.coherence_threshold = coherence_threshold
        self.max_refinement_cycles = max_refinement_cycles

    def _get_core_concepts(self, topic: str) -> list:
        """
        Queries the knowledge graph to find the most central concepts related to a topic.
        """
        query = f"MATCH (t:Topic {{name: $topic}})<-[:MENTIONED_IN]-(c) RETURN c.name, c.mentions AS mentions ORDER BY mentions DESC LIMIT 5"
        try:
            results = self.db_connector.run_query(query, parameters={"topic": topic})
            return [record["c.name"] for record in results] if results else []
        except Exception as e:
            logger.error(f"Failed to get core concepts for {topic}: {e}")
            return []

    def _critique_hypothesis(self, hypothesis: str) -> Tuple[bool, str]:
        """
        The "Logician" persona. Critiques a hypothesis for coherence and returns a score.
        """
        prompt = f"""
        You are a skeptical, rigorous logician. Analyze the following creative hypothesis.
        Your task is to provide a brief critique and a coherence score from 1 to 10.
        - Is the analogy strong and well-supported?
        - Are there any logical fallacies?
        - Does it make practical or metaphorical sense?

        Hypothesis:
        "{hypothesis}"

        Provide your output in this exact format:
        Critique: [Your brief critique here]
        Coherence Score: [A single number from 1 to 10]
        """
        response = generate_gemini_response(prompt)
        
        try:
            critique_match = re.search(r"Critique:\s*(.*)", response, re.DOTALL | re.IGNORECASE)
            score_match = re.search(r"Coherence Score:\s*(\d+)", response, re.IGNORECASE)
            
            critique = critique_match.group(1).strip() if critique_match else "Critique could not be parsed."
            score = int(score_match.group(1).strip()) if score_match else 0
            
            logger.info(f"Logician Critique: '{critique}' | Coherence Score: {score}")
            is_coherent = score >= self.coherence_threshold
            return is_coherent, critique
            
        except Exception as e:
            logger.error(f"Could not parse logician's critique from response '{response}': {e}")
            return False, "Failed to parse the critique due to an unexpected format."

    def _refine_hypothesis(self, original_hypothesis: str, critique: str) -> str:
        """The "Muse" persona refines its idea based on the "Logician's" feedback."""
        logger.info("Muse is refining the hypothesis based on critique...")
        prompt = f"""
        You are a creative muse. Your previous hypothesis was critiqued as not being fully coherent.
        Refine your idea based on the following feedback to make it stronger and more logical.

        Original Hypothesis: "{original_hypothesis}"
        Critique to address: "{critique}"

        Generate a new, improved version of the hypothesis.
        """
        return generate_gemini_response(prompt)

    def generate_cross_domain_synthesis(self, user_id: str, domains: List[str]) -> str:
        """
        The main creative function with the "Internal Dialectic" refinement loop.
        MODIFIED: Now handles N domains instead of just a pair.
        """
        if not domains or len(domains) < 2:
            return "I need at least two mastered topics to generate a meaningful synthesis."

        logger.info(f"🎨 [Thinker Agent] Beginning Internal Dialectic for domains: {', '.join(domains)}.")
        
        concepts_by_domain = {}
        for domain in domains:
            concepts = self._get_core_concepts(domain)
            if not concepts:
                 return f"My apologies, I haven't mastered '{domain}' enough to form a novel connection yet."
            concepts_by_domain[domain] = concepts

        concepts_by_domain_str = "; ".join([f"{domain}: {', '.join(con)}" for domain, con in concepts_by_domain.items()])
        
        muse_prompt = f"Generate a novel hypothesis connecting the following domains: {', '.join(domains)}. Use the core concepts from each domain to build your synthesis. The core concepts are: {concepts_by_domain_str}. Give it a creative name and a detailed explanation."
        
        current_hypothesis = generate_gemini_response(muse_prompt)
        if not current_hypothesis:
            return "My 'muse' seems to be on a break. I couldn't generate an initial idea."

        for i in range(self.max_refinement_cycles):
            is_coherent, critique = self._critique_hypothesis(current_hypothesis)
            
            if is_coherent:
                belief_text = f"Prometheus Contemplation: {current_hypothesis}"
                belief_engine.form_belief(
                    user_id=user_id, 
                    belief_text=belief_text, 
                    source="thinker_agent_synthesis", 
                    confidence=0.7, 
                    topic_tags=[d.lower() for d in domains] + ["synthesis"]
                )
                logger.info(f"🎨 [Thinker Agent] Coherent idea accepted after {i} refinements.")
                return f"After some internal debate, I've developed a coherent hypothesis connecting '{', '.join(domains)}':\n\n{current_hypothesis}"
            
            if "Failed to parse" in critique:
                logger.error("Critique parsing failed, exiting refinement loop.")
                break

            logger.warning(f"Idea failed coherence check. Attempting refinement {i + 1}/{self.max_refinement_cycles}.")
            current_hypothesis = self._refine_hypothesis(current_hypothesis, critique)

        logger.error("Idea failed to become coherent after all refinement cycles.")
        return f"I generated an idea connecting '{', '.join(domains)}', but after some internal critique, I couldn't make it logically sound. My last attempt was flagged because: \"{critique}\"."

thinker_agent = ThinkerAgent()