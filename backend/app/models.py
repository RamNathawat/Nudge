from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MemoryEntry(BaseModel):
    user_id: str
    content: str
    sender: str
    emotion: Optional[str] = None
    emotional_intensity: float = 0.0
    timestamp: datetime
    salience: float = 0.0
    repetition_score: float = 0.0
    topic_tags: Optional[list[str]] = []
    task_reference: Optional[str] = None
    reply_to_id: Optional[str] = None  # ✅ NEW