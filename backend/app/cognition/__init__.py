# backend/app/cognition/__init__.py

from . import belief_engine
from . import belief_evolution
from . import belief_model
from . import curiosity_engine
from . import goal_manager
from . import internal_monologue
from . import knowledge_graph_engine

# Import agents that don't have circular dependencies first
from .thinker_agent import thinker_agent
from .inference_engine import inference_engine

# Import agents that depend on the above
from .orchestrator import orchestrator_agent
from . import dream_mode # Dream mode might depend on other agents