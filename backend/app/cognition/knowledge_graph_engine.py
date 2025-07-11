# backend/app/cognition/knowledge_graph_engine.py

import logging
import spacy
import re
from collections import Counter
from app.services.graph_db_connector import graph_db_connector

# Load the spaCy model
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
    """
    def __init__(self):
        self.db_connector = graph_db_connector
        self.supported_entity_labels = {
            "PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART"
        }

    def _create_or_update_node(self, tx, label, name):
        query = (
            f"MERGE (n:{label} {{name: $name}}) "
            "ON CREATE SET n.created_at = timestamp(), n.mentions = 1 "
            "ON MATCH SET n.mentions = n.mentions + 1"
        )
        tx.run(query, name=name.strip())

    def _create_relationship(self, tx, source_name, source_label, target_name, target_label, relation):
        query = (
            f"MATCH (a:{source_label} {{name: $source_name}}), (b:{target_label} {{name: $target_name}}) "
            # Use MERGE to avoid duplicate relationships
            f"MERGE (a)-[r:{relation}]->(b)"
        )
        tx.run(query, source_name=source_name.strip(), target_name=target_name.strip())

    def _extract_relationships(self, sentence: str) -> list:
        """
        A simplified relationship extractor using patterns.
        This simulates a more complex NLP model.
        Returns a list of (subject, relation, object) triplets.
        """
        doc = nlp(sentence)
        triplets = []
        
        # Pattern: [ENTITY] is a [ENTITY] -> (ENTITY)-[:IS_A]->(ENTITY)
        # Example: "The Prisoner's Dilemma is a classic example of Game Theory."
        matches = re.findall(r'(.+?) is a (.+)', sentence)
        for match in matches:
            subj = nlp(match[0])
            obj = nlp(match[1])
            if subj.ents and obj.ents:
                subject_name = subj.ents[0].text
                object_name = obj.ents[0].text
                triplets.append((subject_name, "IS_A", object_name))

        # Pattern: [ENTITY] developed/created/invented [ENTITY] -> (ENTITY)-[:DEVELOPED]->(ENTITY)
        # Example: "John von Neumann developed the concept."
        matches = re.findall(r'(.+?) (?:developed|created|invented) (.+)', sentence)
        for match in matches:
            subj = nlp(match[0])
            obj = nlp(match[1])
            if subj.ents and obj.ents:
                subject_name = subj.ents[0].text
                object_name = obj.ents[0].text
                triplets.append((subject_name, "DEVELOPED", object_name))

        return triplets

    def process_and_load_text(self, text: str, source_topic: str) -> list:
        """
        The core function that turns unstructured text into a structured graph.
        NOW with relationship extraction.
        """
        logger.info(f"SynthesizerAgent (Lvl 2) processing text for topic: {source_topic}")
        if not self.db_connector or not self.db_connector._driver:
            logger.error("Database connector not available. Aborting.")
            return []

        doc = nlp(text)
        
        # Process sentence by sentence for relationship extraction
        for sentence in doc.sents:
            triplets = self._extract_relationships(sentence.text)
            if triplets:
                with self.db_connector._driver.session() as session:
                    for subj, rel, obj in triplets:
                        # For simplicity, we assume extracted parts are 'Concepts' if not otherwise typed by spaCy
                        # A more advanced system would have better type detection.
                        subj_doc = nlp(subj)
                        obj_doc = nlp(obj)
                        
                        subj_label = next((ent.label_ for ent in subj_doc.ents), "Concept")
                        obj_label = next((ent.label_ for ent in obj_doc.ents), "Concept")

                        session.write_transaction(self._create_or_update_node, subj_label, subj)
                        session.write_transaction(self._create_or_update_node, obj_label, obj)
                        session.write_transaction(self._create_relationship, subj, subj_label, obj, obj_label, rel)
                        logger.info(f"Created Relationship: ({subj})-[:{rel}]->({obj})")
        
        # Fallback for entities without found relationships
        entities_in_text = {ent.text.strip().capitalize(): ent.label_ for ent in doc.ents if ent.label_ in self.supported_entity_labels}
        with self.db_connector._driver.session() as session:
            session.write_transaction(self._create_or_update_node, "Topic", source_topic)
            for name, label in entities_in_text.items():
                session.write_transaction(self._create_or_update_node, label, name)
                session.write_transaction(
                    self._create_relationship,
                    name, label,
                    source_topic, "Topic",
                    "MENTIONED_IN"
                )
        
        logger.info(f"Loaded {len(entities_in_text)} total entities for topic '{source_topic}'.")

        # Serendipitous Discovery (remains the same)
        nouns = [token.text.capitalize() for token in doc if token.pos_ == "NOUN" and len(token.text) > 3]
        common_nouns = Counter(nouns).most_common(5)
        discovered_topics = [noun for noun, count in common_nouns if count > 2 and noun.lower() != source_topic.lower()]
        if discovered_topics:
            logger.info(f"Discovered potential new topics: {discovered_topics}")
        
        return discovered_topics

# Singleton instance
synthesizer_agent = SynthesizerAgent()