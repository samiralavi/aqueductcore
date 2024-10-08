"""GraphQL Query Controller."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from aqueductcore.backend.context import ServerContext
from aqueductcore.backend.errors import AQDValidationError
from aqueductcore.backend.routers.graphql.inputs import TasksFilterInput, IDType
from aqueductcore.backend.routers.graphql.types import (
    TaskData,
    Tasks,
    task_model_to_node,
)
from aqueductcore.backend.services.task_executor import get_all_tasks, get_task_by_uuid
from aqueductcore.backend.services.validators import MAX_EXPERIMENTS_PER_REQUEST


async def get_tasks(
    context: ServerContext,
    offset: int,
    limit: int,
    filters: Optional[TasksFilterInput] = None,
) -> Tasks:
    """Resolve all tasks."""

    if limit > MAX_EXPERIMENTS_PER_REQUEST:
        raise AQDValidationError(
            f"Maximum allowed limit for experiments is {MAX_EXPERIMENTS_PER_REQUEST}"
        )

    experiment = None
    if filters is not None:
        experiment = filters.experiment
        if experiment is not None and experiment.type != IDType.UUID:
            raise AQDValidationError(
                "Only UUID is supported as experiment identifier in Task filter"
            )

    tasks = await get_all_tasks(
        user_info=context.user_info,
        db_session=context.db_session,
        start_date=filters.start_date if filters else None,
        end_date=filters.end_date if filters else None,
        extension_name=filters.extension_name if filters else None,
        action_name=filters.action_name if filters else None,
        username=filters.username if filters else None,
        experiment_uuid=experiment.value if experiment else None,  # type: ignore
        order_by_creation_date=True,
    )
    task_nodes = [task_model_to_node(value=item) for item in tasks][offset : offset + limit]
    return Tasks(tasks_data=task_nodes, total_tasks_count=len(tasks))


async def get_task(context: ServerContext, task_id: UUID) -> Optional[TaskData]:
    """Resolve a single task."""

    task = await get_task_by_uuid(
        user_info=context.user_info,
        db_session=context.db_session,
        task_id=task_id,
    )

    return task_model_to_node(task)
