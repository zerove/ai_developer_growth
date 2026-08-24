from pydantic import BaseModel, Field


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
    started_at: str | None = None
    completed_at: str | None = None
    notes: str | None = None


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
    reviewed_at: str | None = None
    reviewer_notes: str | None = None


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
