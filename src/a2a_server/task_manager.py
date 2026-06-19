"""
Task Manager for A2A-World Server
Manages the lifecycle and state history of A2A Protocol tasks in PostgreSQL.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging
import json
import asyncpg
from a2a_models import Task, Message, TaskState

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages the lifecycle and state of A2A Protocol tasks backed by PostgreSQL."""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    def set_pool(cls, pool: asyncpg.Pool):
        """Set the database connection pool."""
        cls._pool = pool

    @classmethod
    async def create_task(cls) -> Task:
        """Create a new task in the 'submitted' state in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        task = Task(state="submitted")
        
        async with cls._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO a2a_tasks (task_id, state, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                """,
                task.id, task.state, task.created_at, task.updated_at
            )
        
        logger.info(f"Task created: {task.id}")
        return task

    @classmethod
    async def get_task(cls, task_id: str) -> Optional[Task]:
        """Retrieve a task and its messages by ID."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT task_id, state, result, error, created_at, updated_at FROM a2a_tasks WHERE task_id = $1",
                task_id
            )
            
            if not row:
                return None
                
            task = Task(
                id=str(row["task_id"]),
                state=row["state"],
                result=json.loads(row["result"]) if row["result"] else None,
                error=json.loads(row["error"]) if row["error"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
            
            msg_rows = await conn.fetch(
                "SELECT role, parts, timestamp FROM a2a_messages WHERE task_id = $1 ORDER BY timestamp ASC",
                task_id
            )
            
            for msg_row in msg_rows:
                task.messages.append(Message(
                    role=msg_row["role"],
                    parts=json.loads(msg_row["parts"]),
                    timestamp=msg_row["timestamp"]
                ))
                
        return task

    @classmethod
    async def update_task_state(cls, task_id: str, new_state: TaskState) -> Optional[Task]:
        """Update the state of a task in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            await conn.execute(
                "UPDATE a2a_tasks SET state = $1, updated_at = NOW() WHERE task_id = $2",
                new_state, task_id
            )
        logger.info(f"Task {task_id} state updated to {new_state}")
        return await cls.get_task(task_id)

    @classmethod
    async def add_message(cls, task_id: str, message: Message) -> Optional[Task]:
        """Append a message to the task's history in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            parts_json = json.dumps([p.dict(exclude_none=True) for p in message.parts])
            await conn.execute(
                """
                INSERT INTO a2a_messages (task_id, role, parts, timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                task_id, message.role, parts_json, message.timestamp
            )
            await conn.execute("UPDATE a2a_tasks SET updated_at = NOW() WHERE task_id = $1", task_id)
            
        return await cls.get_task(task_id)

    @classmethod
    async def complete_task(cls, task_id: str, result: Dict) -> Optional[Task]:
        """Mark a task as completed with a result in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            await conn.execute(
                "UPDATE a2a_tasks SET state = 'completed', result = $1, updated_at = NOW() WHERE task_id = $2",
                json.dumps(result), task_id
            )
        logger.info(f"Task {task_id} completed")
        return await cls.get_task(task_id)

    @classmethod
    async def fail_task(cls, task_id: str, error: Dict) -> Optional[Task]:
        """Mark a task as failed with an error in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            await conn.execute(
                "UPDATE a2a_tasks SET state = 'failed', error = $1, updated_at = NOW() WHERE task_id = $2",
                json.dumps(error), task_id
            )
        logger.warning(f"Task {task_id} failed: {error}")
        return await cls.get_task(task_id)

    @classmethod
    async def cancel_task(cls, task_id: str) -> Optional[Task]:
        """Cancel a running task in the database."""
        if not cls._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with cls._pool.acquire() as conn:
            # Only cancel if it's currently running
            status = await conn.fetchval("SELECT state FROM a2a_tasks WHERE task_id = $1", task_id)
            if status in ["submitted", "working", "input-required"]:
                await conn.execute(
                    "UPDATE a2a_tasks SET state = 'canceled', updated_at = NOW() WHERE task_id = $1",
                    task_id
                )
                logger.info(f"Task {task_id} canceled")
                
        return await cls.get_task(task_id)
