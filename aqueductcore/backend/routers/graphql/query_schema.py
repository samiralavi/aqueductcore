"""GraphQL Query Controller."""

from __future__ import annotations

from typing import List, Optional, cast
from uuid import UUID

import strawberry
from strawberry.types import Info

from aqueductcore.backend.context import ServerContext
from aqueductcore.backend.routers.graphql.inputs import (
    ExperimentFiltersInput,
    ExperimentIdentifierInput,
    TagsFilters,
    TasksFilterInput,
)
from aqueductcore.backend.routers.graphql.resolvers.experiment_resolver import (
    get_current_user_info,
    get_experiment,
    get_expriments,
)
from aqueductcore.backend.routers.graphql.resolvers.tags_resolver import get_tags
from aqueductcore.backend.routers.graphql.resolvers.task_resolver import (
    get_task,
    get_tasks,
)
from aqueductcore.backend.routers.graphql.types import (
    ExperimentData,
    Experiments,
    ExtensionInfo,
    Tags,
    TaskData,
    Tasks,
    UserInfo,
)
from aqueductcore.backend.services.extensions_executor import ExtensionsExecutor


@strawberry.type
class Query:
    """GraphQL query controller."""

    @strawberry.field
    async def get_current_user_info(self, info: Info) -> UserInfo:
        """Resolver for getting the currently logged in user info."""
        context = cast(ServerContext, info.context)

        return get_current_user_info(context=context)

    @strawberry.field
    async def experiments(
        self, info: Info, offset: int, limit: int, filters: Optional[ExperimentFiltersInput] = None
    ) -> Experiments:
        """Resolver for the experiments."""
        context = cast(ServerContext, info.context)
        experiments = await get_expriments(
            context=context, offset=offset, limit=limit, filters=filters
        )
        return experiments

    @strawberry.field
    async def experiment(
        self, info: Info, experiment_identifier: ExperimentIdentifierInput
    ) -> Optional[ExperimentData]:
        """Resolver for a single experiment."""
        context = cast(ServerContext, info.context)
        experiment = await get_experiment(
            context=context, experiment_identifier=experiment_identifier
        )
        return experiment

    @strawberry.field
    async def tags(
        self,
        info: Info,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        filters: Optional[TagsFilters] = None,
    ) -> Tags:
        """Resolver for the tags."""
        context = cast(ServerContext, info.context)
        tags = await get_tags(context=context, limit=limit, offset=offset, filters=filters)
        return tags

    @strawberry.field
    async def extensions(self) -> List[ExtensionInfo]:
        """List of extensions available now"""
        return list(map(ExtensionInfo.from_extension, ExtensionsExecutor.list_extensions()))

    @strawberry.field
    async def task(
        self,
        info: Info,
        task_id: UUID,
    ) -> Optional[TaskData]:
        """Returns information about the task with a given identifier.
        If id is unknown, returns None.
        """
        return await get_task(context=cast(ServerContext, info.context), task_id=task_id)

    @strawberry.field
    async def tasks(
        self, info: Info, offset: int, limit: int, filters: Optional[TasksFilterInput] = None
    ) -> Tasks:
        """Returns information about all tasks."""
        return await get_tasks(
            context=cast(ServerContext, info.context), filters=filters, offset=offset, limit=limit
        )
