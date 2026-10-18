from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field, HttpUrl

class TaskStatus(StrEnum):
    queued="queued"; inspecting="inspecting"; planning="planning"; awaiting_approval="awaiting_approval"; executing="executing"; completed="completed"; failed="failed"

class CreateTask(BaseModel):
    repository_url: HttpUrl
    # An empty request is a valid "inspect this repository" operation.
    request: str = Field(default="", max_length=10000)
    branch: str = "main"

class Approval(BaseModel):
    publish: bool = False
    create_pull_request: bool = False

class TaskView(BaseModel):
    id: str; repository_url: str; request: str; branch: str; status: TaskStatus
    created_at: datetime; updated_at: datetime
    plan: dict | None = None; result: dict | None = None; error: str | None = None

class GraphNode(BaseModel): id: str; label: str; name: str; properties: dict = {}
class GraphEdge(BaseModel): source: str; target: str; type: str
class GraphView(BaseModel): nodes: list[GraphNode]; edges: list[GraphEdge]
