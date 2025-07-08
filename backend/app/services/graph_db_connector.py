# backend/app/services/graph_db_connector.py

import os
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class GraphDBConnector:
    """
    A dedicated connector to handle all interactions with the Neo4j Graph Database.
    """
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            logger.info("✅ Neo4j Graph Database driver initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Neo4j driver: {e}")
            self._driver = None

    def close(self):
        if self._driver is not None:
            self._driver.close()
            logger.info("Neo4j driver connection closed.")

    def run_query(self, query, parameters=None):
        if self._driver is None:
            logger.error("Cannot run query, driver not initialized.")
            return None
            
        with self._driver.session() as session:
            try:
                result = session.run(query, parameters)
                return [record for record in result]
            except Exception as e:
                logger.error(f"❌ Graph query failed: {e}")
                return None

# Singleton instance to be used across the application
graph_db_connector = GraphDBConnector()