from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List


class BaseSchema(BaseModel):
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: (
                v.replace(tzinfo=timezone.utc).isoformat()
                if v.tzinfo is None
                else v.astimezone(timezone.utc).isoformat()
            )
        }


class AttachmentOut(BaseSchema):
    id: str
    filename: str
    mime_type: str
    kind: str
    size_bytes: int
    status: str
    error: Optional[str] = None
    page_count: Optional[int] = None
    token_estimate: Optional[int] = None
    summary_line: Optional[str] = None


class MessageOut(BaseSchema):
    id: int
    role: str
    content: str
    created_at: datetime
    sentiment_score: Optional[float] = None
    attachments: List[AttachmentOut] = []


class ConversationOut(BaseSchema):
    id: int
    title: Optional[str]
    summary: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    message_count: int


class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = []


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    attachment_ids: List[str] = Field(default_factory=list, max_length=10)
    # A skill the user picked from the composer's + menu: "store-prices" or a lookup skill id.
    skill: Optional[str] = Field(default=None, max_length=64)


class FactOut(BaseSchema):
    id: int
    category: str
    content: str
    confidence: float
    created_at: datetime
    updated_at: datetime
    memory_type: str = "long"
    expires_at: Optional[datetime] = None


class FactCreate(BaseModel):
    category: str
    content: str
    confidence: float = 1.0


class TaskOut(BaseSchema):
    id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    completed: bool
    priority: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"


class EventOut(BaseSchema):
    id: int
    title: str
    description: Optional[str]
    start_datetime: datetime
    end_datetime: Optional[datetime]
    recurring: Optional[str]
    location: Optional[str]


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    recurring: Optional[str] = None
    location: Optional[str] = None


class PersonalityOut(BaseSchema):
    verbosity: float
    formality: float
    humor: float
    depth: float
    emotional_support: float
    question_frequency: float
    current_mood: str
    mood_intensity: float
    energy_level: float
    total_interactions: int


class AppLaunchRequest(BaseModel):
    name: str


class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
