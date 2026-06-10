"""Learning path API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.content import LessonBlock


class LearningPathProgress(BaseModel):
    """Computed progress for a user's learning path."""

    total_modules: int = Field(ge=0)
    read_modules: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)
    is_completed: bool
    next_module_id: int | None = None


class LearningPathTitle(BaseModel):
    """Lightweight path metadata for frontend title selectors."""

    id: int
    title: str
    topic: str
    progress_percent: int = Field(ge=0, le=100)
    is_completed: bool
    updated_at: datetime


class LearningPathSummary(LearningPathTitle):
    """Learning path summary for library views."""

    summary: str
    total_modules: int = Field(ge=0)
    read_modules: int = Field(ge=0)
    estimated_minutes: int = Field(ge=0)
    next_module_id: int | None = None
    created_at: datetime


class LearningPathModuleRead(BaseModel):
    """Learning module with the current user's read state."""

    id: int
    order: int = Field(ge=1)
    title: str
    learning_objective: str
    estimated_minutes: int = Field(ge=1)
    blocks: list[LessonBlock]
    is_read: bool = False
    read_at: datetime | None = None


class LearningPathDetail(BaseModel):
    """Complete learning path payload for a course-like learning experience."""

    id: int
    topic: str
    title: str
    summary: str
    estimated_minutes: int = Field(ge=0)
    progress: LearningPathProgress
    modules: list[LearningPathModuleRead]
    created_at: datetime
    updated_at: datetime


class LearningHistoryStats(BaseModel):
    """Aggregate learning stats across all of a user's learning paths."""

    total_paths: int = Field(ge=0)
    completed_paths: int = Field(ge=0)
    in_progress_paths: int = Field(ge=0)
    total_modules: int = Field(ge=0)
    read_modules: int = Field(ge=0)
    minutes_read: int = Field(ge=0)


class LearningHistoryActivity(BaseModel):
    """A single module-read event for the dashboard activity feed."""

    learning_path_id: int
    learning_path_title: str
    module_id: int
    module_title: str
    module_order: int = Field(ge=1)
    read_at: datetime


class LearningHistory(BaseModel):
    """Dashboard payload with learning stats, recent paths, and activity."""

    stats: LearningHistoryStats
    recent_paths: list[LearningPathSummary]
    recent_activity: list[LearningHistoryActivity]


class LearningPathModuleProgressUpdate(BaseModel):
    """Request body for setting module read state."""

    is_read: bool = True


class LearningPathModuleProgressResult(BaseModel):
    """Response after changing a module's read state."""

    module_id: int
    is_read: bool
    read_at: datetime | None
    progress: LearningPathProgress
