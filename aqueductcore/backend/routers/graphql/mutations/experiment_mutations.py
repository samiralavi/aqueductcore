"""GraphQL mutation controller"""

from uuid import UUID

from aqueductcore.backend.context import ServerContext
from aqueductcore.backend.routers.graphql.inputs import (
    ExperimentCreateInput,
    ExperimentRemoveInput,
    ExperimentTagInput,
    ExperimentTagsInput,
    ExperimentUpdateInput,
)
from aqueductcore.backend.routers.graphql.types import ExperimentData
from aqueductcore.backend.routers.graphql.utils import experiment_model_to_node
from aqueductcore.backend.services import experiment as experiment_service


async def create_experiment(
    context: ServerContext, create_experiment_input: ExperimentCreateInput
) -> ExperimentData:
    """Create experiment mutation"""

    experiment = await experiment_service.create_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        title=create_experiment_input.title,
        description=create_experiment_input.description,
        tags=create_experiment_input.tags,
    )
    return experiment_model_to_node(experiment)


async def update_experiment(
    context: ServerContext, experiment_id: UUID, experiment_update_input: ExperimentUpdateInput
) -> ExperimentData:
    """Update experiment mutation"""

    experiment = await experiment_service.update_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        experiment_id=experiment_id,
        title=experiment_update_input.title,
        description=experiment_update_input.description,
    )
    return experiment_model_to_node(experiment)


async def add_tag_to_experiment(
    context: ServerContext, experiment_tag_input: ExperimentTagInput
) -> ExperimentData:
    """Add tag to experiment mutation"""

    experiment = await experiment_service.add_tags_to_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        experiment_id=experiment_tag_input.experiment_id,
        tags=[experiment_tag_input.tag],
    )
    return experiment_model_to_node(experiment)


async def add_tags_to_experiment(
    context: ServerContext, experiment_tags_input: ExperimentTagsInput
) -> ExperimentData:
    """Add tag to experiment mutation"""

    experiment = await experiment_service.add_tags_to_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        experiment_id=experiment_tags_input.experiment_id,
        tags=experiment_tags_input.tags,
    )
    return experiment_model_to_node(experiment)


async def remove_tag_from_experiment(
    context: ServerContext, experiment_tag_input: ExperimentTagInput
) -> ExperimentData:
    """Remove tag from experiment mutation"""

    experiment = await experiment_service.remove_tag_from_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        experiment_id=experiment_tag_input.experiment_id,
        tag=experiment_tag_input.tag,
    )
    return experiment_model_to_node(experiment)


async def remove_experiment(
    context: ServerContext, experiment_remove_input: ExperimentRemoveInput
) -> UUID:
    """Remove experiment mutation"""

    deleted_experiment_id = await experiment_service.remove_experiment(
        user_info=context.user_info,
        db_session=context.db_session,
        experiment_id=experiment_remove_input.experiment_id,
    )
    return deleted_experiment_id
