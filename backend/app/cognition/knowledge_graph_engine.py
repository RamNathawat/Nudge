# backend/app/cognition/knowledge_graph_engine.py

import logging
import spacy
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
        # Define entity labels that we are interested in from spaCy
        self.supported_entity_labels = {
            "PERSON", "ORG", "GPE", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE",
            "DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL"
        }

    def _create_or_update_node(self, tx, label, name):
        """Helper function to create a node if it doesn't exist."""
        query = (
            f"MERGE (n:{label} {{name: $name}}) "
            "ON CREATE SET n.created_at = timestamp(), n.mentions = 1 "
            "ON MATCH SET n.mentions = n.mentions + 1"
        )
        tx.run(query, name=name)

    def _create_relationship(self, tx, source_name, source_label, target_name, target_label, relation):
        """Helper function to create a relationship between two nodes."""
        query = (
            f"MATCH (a:{source_label} {{name: $source_name}}), (b:{target_label} {{name: $target_name}}) "
            f"MERGE (a)-[r:{relation}]->(b)"
        )
        tx.run(query, source_name=source_name, target_name=target_name)

    def process_and_load_text(self, text: str, source_topic: str) -> list:
        """
        The core function that turns unstructured text into a structured graph.
        """
        logger.info(f"SynthesizerAgent processing text for topic: {source_topic}")
        
        if not self.db_connector or not self.db_connector._driver:
            logger.error("Database connector not available. Aborting.")
            return []

        doc = nlp(text)
        
        # 1. Extract Entities (Nodes)
        entities = []
        for ent in doc.ents:
            if ent.label_ in self.supported_entity_labels:
                # Normalize text: capitalize first letter, strip whitespace
                normalized_text = ent.text.strip().capitalize()
                entities.append((normalized_text, ent.label_))
        
        # 2. Extract Relationships (This is a simplified approach)
        # Production-ready relationship extraction is a very complex NLP task.
        # Here, we'll create a simple relationship: linking all entities to the source topic.
        
        with self.db_connector._driver.session() as session:
            # Create the source topic node
            session.write_transaction(self._create_or_update_node, "Topic", source_topic)
            
            for name, label in set(entities): # Use set to avoid duplicate nodes in one run
                # Create the entity node
                session.write_transaction(self._create_or_update_node, label, name)
                # Create a relationship from the entity to the source topic
                session.write_transaction(
                    self._create_relationship,
                    name, label,
                    source_topic, "Topic",
                    "MENTIONED_IN"
                )

        logger.info(f"Loaded {len(set(entities))} unique entities into the graph for topic '{source_topic}'.")

        # 3. Serendipitous Discovery
        # Find the most common nouns that aren't already a source topic or a major entity.
        # This is a basic way to find new, interesting concepts.
        nouns = [token.text.capitalize() for token in doc if token.pos_ == "NOUN" and len(token.text) > 3]
        common_nouns = Counter(nouns).most_common(5)
        
        discovered_topics = []
        for noun, count in common_nouns:
            # If a noun appears multiple times and isn't the main topic, it might be a new learning path.
            if count > 2 and noun.lower() != source_topic.lower():
                discovered_topics.append(noun)
        
        if discovered_topics:
            logger.info(f"Discovered potential new topics: {discovered_topics}")
        
        return discovered_topics

# Singleton instance
synthesizer_agent = SynthesizerAgent()