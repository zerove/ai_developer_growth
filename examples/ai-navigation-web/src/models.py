from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class AssessmentResult(BaseModel):
    ai_comprehension: float = 0.0
    engineering_integration: float = 0.0
    learning_method: float = 0.0
    innovation_thinking: float = 0.0
    output_quality: float = 0.0
    overall: float = 0.0


class LearningProgress(BaseModel):
    id: int
    doc_path: str
    doc_title: str
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class ContributionCreate(BaseModel):
    doc_path: str
    doc_title: str
    content: str


class Contribution(BaseModel):
    id: int
    doc_path: str
    doc_title: str
    status: str
    submitted_at: str
    reviewed_at: Optional[str] = None
    reviewer_notes: Optional[str] = None


class LearningPath(BaseModel):
    id: int
    path_name: str
    target_level: str
    estimated_hours: float
    created_at: str


class Stats(BaseModel):
    total_users: int = 0
    total_assessments: int = 0
    total_documents: int = 0
    avg_score: float = 0.0
    active_learners: int = 0
