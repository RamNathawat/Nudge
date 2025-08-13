# backend/app/cognition/knowledge_graph_engine.py

import logging
import spacy
import re
from collections import Counter
from typing import List
from app.services.graph_db_connector import graph_db_connector
from app.utils import generate_gemini_response

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy model 'en_core_web_sm'...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

logger = logging.getLogger(__name__)

class SynthesizerAgent:
    """
    This agent is responsible for processing raw text, extracting knowledge,
    and loading it into the graph database as a structured knowledge graph.
    VERSION 3: Upgraded to LLM-based relationship extraction.
    """
    def __init__(self):
        self.db_connector = graph_db_connector
        self.supported_entity_labels = {
            "PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART"
        }

    def _create_relationship(self, tx, source_name, source_label, target_name, target_label, relation):
        """Creates a relationship between two nodes, merging the nodes if they don't exist."""
        query = (
            f"MERGE (a:{source_label} {{name: $source_name}}) "
            f"MERGE (b:{target_label} {{name: $target_name}}) "
            f"MERGE (a)-[r:{relation}]->(b)"
        )
        tx.run(query, source_name=source_name.strip(), target_name=target_name.strip())

    def _extract_relationships(self, sentence: str) -> list:
        """
        Uses an LLM to perform advanced relationship extraction, identifying
        (subject, relation, object) triplets from complex sentences.
        """
        prompt = f"""
        Analyze the following sentence and extract all meaningful relationships in the format [Subject, RELATION, Object].
        The RELATION should be a short, uppercase verb phrase (e.g., IS_A_CONCEPT_IN, INFLUENCED_BY, APPLIED_TO).
        Identify the most specific entities possible for Subject and Object.
        If no clear relationship is present, return an empty list.

        Sentence: "{sentence}"

        Example:
        Sentence: "The design of user interfaces in modern HCI is often influenced by psychological principles of cognitive load."
        Result: [["User Interfaces", "INFLUENCED_BY", "Psychological Principles"], ["Modern HCI", "APPLIES_CONCEPT_OF", "Cognitive Load"]]
        
        Result:
        """
        
        response_text = generate_gemini_response(prompt)
        triplets = []
        try:
            found = re.findall(r'\[\s*".*?"\s*,\s*".*?"\s*,\s*".*?"\s*\]', response_text)
            for item in found:
                triplet = eval(item)
                if isinstance(triplet, list) and len(triplet) == 3:
                    triplet[1] = str(triplet[1]).upper().replace(" ", "_")
                    triplets.append(tuple(triplet))
        except Exception as e:
            logger.error(f"Error parsing LLM response for relationship extraction: {e} - Response was: '{response_text}'")

        return triplets

    def process_and_load_text(self, text: str, source_topics: List[str]) -> list:
        """The core function that turns unstructured text into a structured graph."""
        logger.info(f"SynthesizerAgent (Lvl 3) processing text for topics: {source_topics}")
        if not self.db_connector or not self.db_connector._driver:
            logger.error("Database connector not available. Aborting.")
            return []

        doc = nlp(text)
        
        with self.db_connector._driver.session() as session:
            for topic in source_topics:
                session.write_transaction(lambda tx: tx.run(f"MERGE (t:Topic {{name: $name}})", name=topic))

            all_new_entities = set()

            for sentence in doc.sents:
                triplets = self._extract_relationships(sentence.text)
                if triplets:
                    for subj, rel, obj in triplets:
                        subj_label = next((ent.label_ for ent in nlp(subj).ents), "Concept")
                        obj_label = next((ent.label_ for ent in nlp(obj).ents), "Concept")
                        session.write_transaction(self._create_relationship, subj, subj_label, obj, obj_label, rel)
                        logger.info(f"Created Relationship: ({subj})-[:{rel}]->({obj})")
                        all_new_entities.add((subj, subj_label))
                        all_new_entities.add((obj, obj_label))
            
            entities_in_text = {ent.text.strip().capitalize(): ent.label_ for ent in doc.ents if ent.label_ in self.supported_entity_labels}
            for name, label in entities_in_text.items():
                all_new_entities.add((name, label))
            
            for name, label in all_new_entities:
                for topic in source_topics:
                    session.write_transaction(
                        self._create_relationship,
                        name, label,
                        topic, "Topic",
                        "MENTIONED_IN_CONTEXT_OF"
                    )
            
            logger.info(f"Processed and linked {len(all_new_entities)} total entities for topics '{', '.join(source_topics)}'.")

        nouns = [token.text.capitalize() for token in doc if token.pos_ == "NOUN" and len(token.text) > 3]
        common_nouns = Counter(nouns).most_common(5)
        discovered_topics = [noun for noun, count in common_nouns if count > 2 and noun.lower() not in [t.lower() for t in source_topics]]
        if discovered_topics:
            logger.info(f"Discovered potential new topics: {discovered_topics}")
        
        return discovered_topics

synthesizer_agent = SynthesizerAgent()