"""Durable, repository-scoped memory for the planning agent."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task


async def recent_repository_memory(
    db: AsyncSession, repository_url: str, exclude_task_id: str, limit: int = 5
) -> list[dict]:
    rows = (
        await db.scalars(
            select(Task)
            .where(Task.repository_url == repository_url, Task.id != exclude_task_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "task_id": task.id,
            "request": task.request[:500],
            "status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "plan_summary": (task.plan or {}).get("summary"),
        }
        for task in rows
    ]
