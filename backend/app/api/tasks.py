import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas import CreateTask, TaskView, Approval
from app.db.database import get_session
from app.db.models import Task
from app.services.repository import validate_github_url, RepositoryError
from app.services.github import fetch_branches
from app.services.orchestrator import process, execute_approved
router=APIRouter(prefix="/api/tasks",tags=["tasks"])
def view(x:Task)->TaskView: return TaskView.model_validate(x,from_attributes=True)
@router.get("/repository/branches")
async def branches(repository_url: str):
    """Validate and list selectable remote branches before task creation."""
    try:
        validate_github_url(repository_url)
        return await fetch_branches(repository_url)
    except RepositoryError as e:
        raise HTTPException(422,str(e))
@router.post("",response_model=TaskView,status_code=202)
async def create(data:CreateTask,background:BackgroundTasks,db:AsyncSession=Depends(get_session)):
    try: validate_github_url(str(data.repository_url))
    except RepositoryError as e: raise HTTPException(422,str(e))
    task=Task(repository_url=str(data.repository_url),request=data.request,branch=data.branch); db.add(task); await db.commit(); await db.refresh(task)
    background.add_task(process,task.id); return view(task)
@router.get("",response_model=list[TaskView])
async def list_tasks(limit:int=100, db:AsyncSession=Depends(get_session)):
    """Persistent investigation history, newest first."""
    limit=max(1,min(limit,200))
    return [view(x) for x in (await db.scalars(select(Task).order_by(Task.created_at.desc()).limit(limit))).all()]

@router.get("/history",response_model=list[TaskView])
async def history(limit:int=100, db:AsyncSession=Depends(get_session)):
    return await list_tasks(limit, db)
@router.get("/{task_id}",response_model=TaskView)
async def get_task(task_id:str,db:AsyncSession=Depends(get_session)):
    task=await db.get(Task,task_id)
    if not task: raise HTTPException(404,"Task not found")
    return view(task)
@router.post("/{task_id}/approval",response_model=TaskView)
async def approve(task_id:str,approval:Approval,background:BackgroundTasks,db:AsyncSession=Depends(get_session)):
    task=await db.get(Task,task_id)
    if not task: raise HTTPException(404,"Task not found")
    if task.status!="awaiting_approval": raise HTTPException(409,"Task is not awaiting approval")
    # Publishing/PR integration is deliberately gated; approval is durable audit evidence.
    if approval.publish or approval.create_pull_request:
        raise HTTPException(501,"Publishing and PR creation need an explicit GitHub integration deployment; no remote write is performed.")
    task.result={**(task.result or {}),"approval":approval.model_dump()}; task.status="executing"; await db.commit(); background.add_task(execute_approved,task.id); return view(task)
