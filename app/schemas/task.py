from datetime import datetime

from pydantic import BaseModel, Field

from app.models.task import TaskStatus


class TaskBase(BaseModel):
    title: str = Field(..., max_length=255, examples=["Buy groceries"])
    description: str | None = Field(None, examples=["Milk, eggs, bread"])
    status: TaskStatus = Field(TaskStatus.todo, examples=["todo"])
    progress: int = Field(0, ge=0, le=100, examples=[0])


class TaskCreate(TaskBase):
    """Payload for POST /tasks."""
    pass


class TaskUpdate(BaseModel):
    """Payload for PATCH /tasks/{id}. All fields are optional."""

    title: str | None = Field(None, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    progress: int | None = Field(None, ge=0, le=100)


class TaskResponse(TaskBase):
    """Shape of a task returned from the API."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
