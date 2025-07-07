# app/models/belief_model.py

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# ✅ 1. Belief Model
class Belief(BaseModel):
    user_id: str
    belief: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    topic_tags: List[str] = []
    source: str = "inference"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    history: List[str] = []

    def to_mongo(self):
        return self.dict()

# ✅ 2. Goal Model
class Goal(BaseModel):
    user_id: str
    goal: str
    status: str = "in_progress"  # or: "complete", "failed"
    strategy: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    linked_beliefs: List[str] = []
    nudged: bool = False
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo(self):
        return self.dict()

# ✅ 3. Internal Monologue (private thoughts)
class Monologue(BaseModel):
    user_id: str
    input_id: Optional[str] = None
    thought: str
    doubt_level: float = 0.0
    desire: Optional[str] = None
    emotion_trigger: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo(self):
        return self.dict()
