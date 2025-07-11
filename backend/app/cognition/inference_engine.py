# backend/app/cognition/inference_engine.py

import logging
import re
from functools import lru_cache
from app.services.graph_db_connector import graph_db_connector
from app.utils import generate_gemini_response
from app.services.research_service import perform_deep_research

logger = logging.getLogger(__name__)

class InferenceEngine:
    """
    Final version of the Inference Engine, implementing a "Two-Pass" reasoning system.
    """
    def __init__(self, max_retries=1):
        self.db_connector = graph_db_connector
        self.max_retries = max_retries

    @lru_cache(maxsize=1)
    def _get_graph_schema(self) -> str:
        """
        Fetches a detailed schema from Neo4j, including node properties, for better context.
        """
        if not self.db_connector or not self.db_connector._driver:
            return "Schema unavailable: Database not connected."
        
        try:
            schema_query = "CALL db.schema.nodeTypeProperties()"
            records = self.db_connector.run_query(schema_query)
            
            if not records:
                return "Graph is currently empty."

            schema_map = {}
            for record in records:
                node_label = record.get('nodeLabels')[0]
                property_name = record.get('propertyName')
                
                if node_label not in schema_map:
                    schema_map[node_label] = []
                schema_map[node_label].append(property_name)

            schema_str = "\n".join([f"- :{label} {{ {', '.join(props)} }}" for label, props in schema_map.items()])
            logger.info("Dynamically fetched graph schema.")
            return schema_str
        except Exception as e:
            logger.error(f"Failed to fetch graph schema: {e}")
            return "Schema could not be retrieved."

    def _translate_question_to_cypher(self, question: str) -> str:
        """
        Uses an LLM to translate a natural language question into a robust Cypher query.
        """
        schema = self._get_graph_schema()
        prompt = f"""
        You are a Cypher query expert. Translate the user's question into a precise Cypher query for a Neo4j database.

        **Instructions:**
        1. **Strictly adhere to the provided schema.**
        2. **Use Case-Insensitive Matching:** For all `name` property lookups, use the `=~ '(?i)...'` regex syntax for case-insensitivity. This is critical.
        3. Omit node labels if you are uncertain to ensure broader matching on the `name` property.

        **SCHEMA:**
        {schema}

        **EXAMPLES:**
        - Question: "Who developed Game Theory?"
          Cypher: MATCH (p:Person)-[:DEVELOPED]->(t) WHERE t.name =~ '(?i)game theory' RETURN p.name
        - Question: "What is the relationship between 'Nash Equilibrium' and 'Game Theory'?"
          Cypher: MATCH (n)-[r]-(t) WHERE n.name =~ '(?i)nash equilibrium' AND t.name =~ '(?i)game theory' RETURN type(r)

        Translate the following question into a single, precise Cypher query.
        
        Question: "{question}"
        
        Cypher Query:
        """
        
        cypher_query = generate_gemini_response(prompt)
        if not cypher_query or "MATCH" not in cypher_query.upper():
            raise ValueError("LLM failed to generate a valid Cypher query.")
            
        logger.info(f"Translated '{question}' to Cypher: '{cypher_query}'")
        return cypher_query.strip().replace("`", "").replace("cypher", "").strip()

    def _format_results_to_natural_language(self, question: str, results: list) -> str:
        """
        Uses an LLM to convert structured query results into a human-readable answer.
        """
        if not results:
            return ""

        processed_results = [str(record.values()) for record in results]
        clean_data = ", ".join(processed_results)

        prompt = f"""
        Answer the user's original question based on the provided data from a knowledge graph.
        Original Question: "{question}"
        Data Found in Knowledge Graph: "{clean_data}"
        Synthesize this data into a direct, natural-sounding answer.
        """
        
        answer = generate_gemini_response(prompt)
        logger.info(f"Synthesized answer from graph results: '{answer}'")
        return answer

    def _extract_entities_from_question(self, question: str) -> list:
        """
        Uses an LLM to pull the key entities from the user's question.
        """
        prompt = f"From the question, extract the two primary entities being discussed. Return as a Python list of strings. Question: '{question}'"
        response_str = generate_gemini_response(prompt)
        try:
            match = re.search(r'\[.*?\]', response_str)
            return eval(match.group(0)) if match else eval(response_str)
        except Exception as e:
            logger.error(f"Could not parse entities from LLM response '{response_str}': {e}")
            return []

    def _infer_and_create_relationship(self, question: str) -> bool:
        """
        The "Thinker" agent. Infers and saves a relationship. Returns True on success.
        """
        logger.warning(f"No direct relationship found. Activating 'Thinker' agent for: {question}")
        
        entities = self._extract_entities_from_question(question)
        if len(entities) != 2:
            return False
        entity1, entity2 = entities[0], entities[1]
        logger.info(f"Thinker Agent: Identified entities '{entity1}' and '{entity2}'.")

        context_text = perform_deep_research(f"What is the relationship between {entity1} and {entity2}?")
        if not context_text:
            logger.error("Thinker Agent: Deep research for context returned no content.")
            return False

        rel_prompt = f"Based on the text, what is the relationship between '{entity1}' and '{entity2}'? Use a single, uppercase verb (e.g., IS_A_CONCEPT_IN). Text: \"{context_text}\" Relationship:"
        relationship_type = generate_gemini_response(rel_prompt).strip()
        if not relationship_type or " " in relationship_type:
            return False

        try:
            with self.db_connector._driver.session() as session:
                session.run("MERGE (a:Concept {name: $entity})", entity=entity1)
                session.run("MERGE (b:Concept {name: $entity})", entity=entity2)
                session.run(f"MATCH (a {{name: $entity1}}), (b {{name: $entity2}}) MERGE (a)-[:{relationship_type}]->(b)",
                            entity1=entity1, entity2=entity2)
            logger.info(f"Thinker Agent: Successfully self-healed graph with relationship: ({entity1})-[{relationship_type}]->({entity2})")
            return True
        except Exception as e:
            logger.error(f"Thinker Agent: Failed to self-heal graph: {e}")
            return False

    def _fallback_web_search(self, question: str) -> str:
        logger.warning(f"Final fallback to web search for question: '{question}'")
        return perform_deep_research(question)

    @lru_cache(maxsize=128)
    def answer_complex_question(self, question: str) -> str:
        """
        The main public method orchestrating the "Two-Pass" inference process.
        """
        if not self.db_connector or not self.db_connector._driver:
            return "My apologies, my knowledge base is currently offline."

        try:
            # --- PASS 1: Attempt to answer directly from the graph ---
            cypher_query = self._translate_question_to_cypher(question)
            query_results = self.db_connector.run_query(cypher_query)
            if query_results:
                final_answer = self._format_results_to_natural_language(question, query_results)
                if final_answer:
                    return final_answer
        except Exception as e:
            logger.error(f"Error during initial graph query: {e}")

        # --- THE "THINK" STEP: If Pass 1 fails, infer and self-heal ---
        inferred_successfully = self._infer_and_create_relationship(question)

        # --- PASS 2: Re-attempt the query after self-healing ---
        if inferred_successfully:
            logger.info("Re-attempting query after self-healing the graph.")
            try:
                cypher_query = self._translate_question_to_cypher(question) # Re-translate in case schema changed
                query_results = self.db_connector.run_query(cypher_query)
                if query_results:
                    final_answer = self._format_results_to_natural_language(question, query_results)
                    if final_answer:
                        return final_answer
            except Exception as e:
                logger.error(f"Error during second pass query: {e}")

        # Final fallback if all else fails
        return self._fallback_web_search(question)

# Singleton instance
inference_engine = InferenceEngine()