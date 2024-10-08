# pylint: skip-file
# mypy: ignore-errors
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import pytest
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry import Schema

from aqueductcore.backend.context import ServerContext, UserInfo, UserScope
from aqueductcore.backend.models import orm
from aqueductcore.backend.models.experiment import (
    ExperimentCreate,
    ExperimentRead,
    TagCreate,
    TagRead,
)
from aqueductcore.backend.routers.graphql.inputs import IDType
from aqueductcore.backend.routers.graphql.query_schema import Query
from aqueductcore.backend.services.experiment import get_all_tags
from aqueductcore.backend.services.utils import (
    experiment_model_to_orm,
    experiment_orm_to_model,
    tag_model_to_orm,
)
from aqueductcore.backend.services.validators import (
    MAX_EXPERIMENT_TAGS_ALLOWED_IN_FILTER,
    MAX_EXPERIMENT_TITLE_FILTER_LENGTH,
    MAX_EXPERIMENTS_PER_REQUEST,
    MAX_TAGS_PER_REQUEST,
)
from aqueductcore.backend.settings import settings

single_experiment_query = """
query MyQuery($experimentIdentifier: ExperimentIdentifierInput!) {
    experiment(experimentIdentifier: $experimentIdentifier) {
        files {
            path
            name
            modifiedAt
        }
        description
        createdAt
        createdBy
        eid
        uuid
        tags
        title
        updatedAt
    }
}
"""

all_experiments_query = """
{
    experiments (
        limit: 10
        offset: 0
    ) {
        experimentsData {
            uuid
            title
            files {
                path
                name
                modifiedAt
            }
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
    }
}
"""

all_experiments_query_filter_by_date = """
query MyQuery($filters: ExperimentFiltersInput!) {
    experiments (
        limit: 10
        offset: 0
        filters: $filters
    ) {
        experimentsData {
            uuid
            title
            files {
                path
                name
                modifiedAt
            }
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
    }
}
"""

all_experiments_invalid_limit_query = (
    """
{
    experiments (
        limit: """
    + str(MAX_EXPERIMENTS_PER_REQUEST + 1000)
    + """
        offset: 0
    ) {
        experimentsData {
            uuid
            title
            files {
                path
                name
                modifiedAt
            }
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
    }
}
"""
)

all_experiments_invalid_title_filter_query = (
    """
{
    experiments (
        limit: 10
        offset: 0,
        filters: {
            title: \""""
    + "a" * (MAX_EXPERIMENT_TITLE_FILTER_LENGTH + 1)
    + """\"
        }
    ) {
        experimentsData {
            uuid
            title
            files {
                path
                name
                modifiedAt
            }
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
    }
}
"""
)

all_tags_query = """
    query TestQuery($dangling:Boolean!) {
        tags(
            filters: {
                includeDangling: $dangling
            }) {
            tagsData
            totalTagsCount
        }
    }
    """

all_experiments_over_limit_tags_filter_query = (
    """
{
    experiments (
        limit: 10
        offset: 0,
        filters: {
            tags: ["""
    + ",".join(f'"{tag}"' for tag in range(MAX_EXPERIMENT_TAGS_ALLOWED_IN_FILTER + 1))
    + """]
        }
    ) {
        experimentsData {
            title
            description
        }
        totalExperimentsCount
    }
}
"""
)

all_experiments_invalid_tags_filter_query = """
{
    experiments (
        limit: 10
        offset: 0,
        filters: {
            tags: ["tag$1"]
        }
    ) {
        experimentsData {
            title
            description
        }
        totalExperimentsCount
    }
}
"""

tags_pagination_query = """
    query TestQuery {
        tags (limit: 2, offset: 0) {
            tagsData
            totalTagsCount
        }
    }
    """

tags_pagination_over_limit_query = (
    """
    query TestQuery {
        tags (limit: """
    + str(MAX_TAGS_PER_REQUEST + 1)
    + """, offset: 0) {
            tagsData
            totalTagsCount
        }
    }
    """
)

filter_by_tag_query = """
    {
        experiments (
            limit: 10
            offset: 0
            filters: {
                tags: [
                    "tag1"
                ]
            }
        ) {
        experimentsData {
            uuid
            title
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
        }
    }
"""


filter_by_title_query = """
    {
        experiments (
            limit: 100
            offset: 0
            filters: {
                title: "qubit"
            }
        ) {
        experimentsData {
            uuid
            title
            description
            createdAt
            createdBy
            updatedAt
            eid
            tags
        }
        totalExperimentsCount
        }
    }
"""

all_extensions_query = """
  {
    extensions {
        authors, description, name
        actions {
            description, name, experimentVariableName,
            parameters {
                name, displayName, description, dataType, defaultValue
            }
        }
    }
  }
"""


def check_tag_values(tag_res: Dict, sample_tag: TagRead):
    assert sample_tag.name == tag_res


def check_experiment_values(
    experiment_res: Dict,
    sample_experiment: ExperimentRead,
    files: Optional[List[Tuple[str, datetime]]] = None,
):
    assert sample_experiment.uuid == UUID(experiment_res["uuid"])
    assert sample_experiment.title == experiment_res["title"]
    assert sample_experiment.eid == experiment_res["eid"]
    assert sample_experiment.description == experiment_res["description"]
    assert sample_experiment.created_by == experiment_res["createdBy"]
    assert sample_experiment.created_at == datetime.fromisoformat(experiment_res["createdAt"])
    assert sample_experiment.updated_at == datetime.fromisoformat(experiment_res["updatedAt"])

    if files is not None:
        assert set([item[0] for item in files]) == set(
            [item["name"] for item in experiment_res["files"]]
        )
        assert set([item[1] for item in files]) == set(
            [datetime.fromisoformat(item["modifiedAt"]) for item in experiment_res["files"]]
        )
        paths = set([item["path"] for item in experiment_res["files"]])
        assert len(paths) == 1  # all files should reside at the same path
        assert (
            next(iter(paths))  # required to access the first item for sets
            == f"{settings.api_prefix}{settings.files_route_prefix}/{str(sample_experiment.uuid)}"
        )


@pytest.mark.asyncio
async def test_query_all_experiments(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):

    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(all_experiments_query, context_value=context)

    assert resp.errors is None
    assert resp.data is not None

    experiment_uuids_order = [
        UUID(experiment["uuid"]) for experiment in resp.data["experiments"]["experimentsData"]
    ]
    db_experiments = [
        experiment for experiment in db_experiments if experiment.uuid in experiment_uuids_order
    ]
    db_experiments = sorted(db_experiments, key=lambda exp: experiment_uuids_order.index(exp.uuid))

    for idx, item in enumerate(resp.data["experiments"]["experimentsData"]):
        check_experiment_values(
            experiment_res=item,
            sample_experiment=await experiment_orm_to_model(db_experiments[idx]),
            files=temp_experiment_files[db_experiments[idx].uuid],
        )


@pytest.mark.parametrize(
    "time_zone",
    random.sample(pytz.all_timezones, 10),
)
@pytest.mark.asyncio
async def test_query_filter_by_date(db_session: AsyncSession, time_zone: str):

    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    experiment_creation_datetime = datetime.now(timezone.utc) + timedelta(days=100)

    tz_experiment_creation_datetime = experiment_creation_datetime.astimezone(
        pytz.timezone(time_zone)
    )
    experiment_uuid = uuid4()
    db_experiment = orm.Experiment(
        uuid=experiment_uuid,
        title="test filter by date",
        description="test filter by date",
        eid="test filter by date",
        created_at=tz_experiment_creation_datetime,
        updated_at=tz_experiment_creation_datetime,
    )
    db_experiment.created_by_user = db_user
    db_session.add(db_experiment)
    await db_session.commit()
    await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    filters = {
        "startDate": f"{(tz_experiment_creation_datetime -timedelta(days=1)).strftime('%Y-%m-%d')}",
        "endDate": f"{(tz_experiment_creation_datetime +timedelta(days=1)).strftime('%Y-%m-%d')}",
    }
    resp = await schema.execute(
        all_experiments_query_filter_by_date,
        context_value=context,
        variable_values={"filters": filters},
    )

    assert resp.errors is None
    assert resp.data is not None

    assert len(resp.data["experiments"]["experimentsData"]) == 1

    experiment = resp.data["experiments"]["experimentsData"][0]

    check_experiment_values(
        experiment_res=experiment,
        sample_experiment=await experiment_orm_to_model(db_experiment),
    )

    # check no start date
    filters = {
        "endDate": f"{(tz_experiment_creation_datetime+timedelta(days=1)).strftime('%Y-%m-%d')}",
    }
    resp = await schema.execute(
        all_experiments_query_filter_by_date,
        context_value=context,
        variable_values={"filters": filters},
    )

    assert resp.errors is None
    assert resp.data is not None

    assert len(resp.data["experiments"]["experimentsData"]) == 1
    check_experiment_values(
        experiment_res=experiment,
        sample_experiment=await experiment_orm_to_model(db_experiment),
    )

    # check no end date
    filters = {
        "startDate": f"{(tz_experiment_creation_datetime -timedelta(days=1)).strftime('%Y-%m-%d')}",
    }
    resp = await schema.execute(
        all_experiments_query_filter_by_date,
        context_value=context,
        variable_values={"filters": filters},
    )

    assert resp.errors is None
    assert resp.data is not None

    assert len(resp.data["experiments"]["experimentsData"]) == 1
    check_experiment_values(
        experiment_res=experiment,
        sample_experiment=await experiment_orm_to_model(db_experiment),
    )

    # check no experiment
    filters = {
        "startDate": f"{(tz_experiment_creation_datetime +timedelta(days=1)).strftime('%Y-%m-%d')}",
        "endDate": f"{(tz_experiment_creation_datetime+timedelta(days=2)).strftime('%Y-%m-%d')}",
    }
    resp = await schema.execute(
        all_experiments_query_filter_by_date,
        context_value=context,
        variable_values={"filters": filters},
    )

    assert resp.errors is None
    assert resp.data is not None

    assert len(resp.data["experiments"]["experimentsData"]) == 0


@pytest.mark.asyncio
async def test_query_all_experiments_invalid_limit(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(all_experiments_invalid_limit_query, context_value=context)

    assert resp.errors is not None
    assert (
        resp.errors[0].message
        == f"Maximum allowed limit for experiments is {MAX_EXPERIMENTS_PER_REQUEST}"
    )


@pytest.mark.asyncio
async def test_query_all_experiments_title_filter(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(all_experiments_invalid_title_filter_query, context_value=context)

    assert resp.errors is not None
    assert (
        resp.errors[0].message
        == f"Title should be maximum {MAX_EXPERIMENT_TITLE_FILTER_LENGTH} characters long."
    )


@pytest.mark.asyncio
async def test_query_all_experiments_max_tags_filter(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(all_experiments_invalid_title_filter_query, context_value=context)

    assert resp.errors is not None
    assert (
        resp.errors[0].message
        == f"Title should be maximum {MAX_EXPERIMENT_TITLE_FILTER_LENGTH} characters long."
    )


@pytest.mark.asyncio
async def test_query_single_experiment(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    experiment = experiments_data[0]
    db_experiment = experiment_model_to_orm(experiment)
    db_experiment.created_by_user = db_user
    db_experiments.append(db_experiment)
    db_session.add(db_experiment)
    await db_session.commit()
    await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )

    # check with UUID
    resp = await schema.execute(
        single_experiment_query,
        context_value=context,
        variable_values={
            "experimentIdentifier": {"type": IDType.UUID.value, "value": str(db_experiment.uuid)}
        },
    )

    assert resp.errors is None
    assert resp.data is not None

    check_experiment_values(
        experiment_res=resp.data["experiment"],
        sample_experiment=await experiment_orm_to_model(db_experiments[0]),
        files=temp_experiment_files[experiment.uuid],
    )

    # check with eid
    resp = await schema.execute(
        single_experiment_query,
        context_value=context,
        variable_values={
            "experimentIdentifier": {"type": IDType.EID.value, "value": db_experiment.eid}
        },
    )

    assert resp.errors is None
    assert resp.data is not None

    check_experiment_values(
        experiment_res=resp.data["experiment"],
        sample_experiment=await experiment_orm_to_model(db_experiments[0]),
        files=temp_experiment_files[experiment.uuid],
    )


@pytest.mark.asyncio
async def test_filter_by_tags_experiments(
    db_session: AsyncSession, experiments_data: List[ExperimentCreate]
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)

    await db_session.commit()

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(filter_by_tag_query, context_value=context)

    assert resp.errors is None
    assert resp.data is not None
    assert len(resp.data["experiments"]["experimentsData"]) == 1


@pytest.mark.asyncio
async def test_filter_by_title_experiments(
    db_session: AsyncSession, experiments_data: List[ExperimentCreate]
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)

    await db_session.commit()

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(filter_by_title_query, context_value=context)

    assert resp.errors is None
    assert resp.data is not None
    assert len(resp.data["experiments"]["experimentsData"]) == 3


@pytest.mark.asyncio
async def test_query_all_tags_all(
    db_session: AsyncSession, experiments_data: List[ExperimentCreate]
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    no_dangling_tags_expected = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        no_dangling_tags_expected.extend(experiment.tags)
        db_session.add(db_experiment)

    dangling_tags_expected = []
    for idx in range(3):
        new_tag = TagCreate(key=f"tag_dangling_{idx}", name=f"TAG_dangling_{idx}")
        db_tag = tag_model_to_orm(new_tag)
        dangling_tags_expected.append(new_tag)
        db_session.add(db_tag)

    schema = Schema(query=Query)

    # enable dangling tags
    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(
        all_tags_query,
        context_value=context,
        variable_values={"dangling": True},
    )

    tags = await get_all_tags(
        user_info=context.user_info, db_session=context.db_session, include_dangling=True
    )

    assert resp.errors is None
    assert resp.data is not None

    for idx, item in enumerate(resp.data["tags"]["tagsData"]):
        check_tag_values(
            tag_res=item,
            sample_tag=tags[idx],
        )

    # disable dangling tags
    resp = await schema.execute(
        all_tags_query,
        context_value=context,
        variable_values={"dangling": False},
    )

    tags = await get_all_tags(
        user_info=context.user_info, db_session=context.db_session, include_dangling=False
    )

    assert resp.errors is None
    assert resp.data is not None

    for idx, item in enumerate(resp.data["tags"]["tagsData"]):
        check_tag_values(
            tag_res=item,
            sample_tag=tags[idx],
        )


@pytest.mark.asyncio
async def test_query_all_tags_no_dangling(
    db_session: AsyncSession, experiments_data: List[ExperimentCreate]
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(
        all_tags_query,
        context_value=context,
        variable_values={"dangling": False},
    )

    tags = await get_all_tags(user_info=context.user_info, db_session=context.db_session)

    assert resp.errors is None
    assert resp.data is not None

    for idx, item in enumerate(resp.data["tags"]["tagsData"]):
        check_tag_values(
            tag_res=item,
            sample_tag=tags[idx],
        )


@pytest.mark.asyncio
async def test_query_over_limit_all_tags(
    db_session: AsyncSession,
    experiments_data: List[ExperimentCreate],
    temp_experiment_files: Dict[UUID, List[Tuple[str, datetime]]],
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    db_experiments = []
    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_experiments.append(db_experiment)
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(tags_pagination_over_limit_query, context_value=context)

    assert resp.errors is not None
    assert resp.errors[0].message == f"Maximum allowed limit for tags is {MAX_TAGS_PER_REQUEST}"


@pytest.mark.asyncio
async def test_query_pagination_tags(
    db_session: AsyncSession, experiments_data: List[ExperimentCreate]
):
    db_user = orm.User(uuid=UUID(int=0), username=settings.default_username)
    db_session.add(db_user)

    for experiment in experiments_data:
        db_experiment = experiment_model_to_orm(experiment)
        db_experiment.created_by_user = db_user
        db_session.add(db_experiment)
        await db_session.commit()
        await db_session.refresh(db_experiment)

    schema = Schema(query=Query)

    context = ServerContext(
        db_session=db_session,
        user_info=UserInfo(uuid=uuid4(), username=settings.default_username, scopes=set(UserScope)),
    )
    resp = await schema.execute(tags_pagination_query, context_value=context)

    tags = await get_all_tags(user_info=context.user_info, db_session=context.db_session)

    assert resp.errors is None
    assert resp.data is not None

    assert len(resp.data["tags"]["tagsData"]) == 2
    assert resp.data["tags"]["totalTagsCount"] == 6

    for idx, item in enumerate(resp.data["tags"]["tagsData"]):
        check_tag_values(
            tag_res=item,
            sample_tag=tags[idx],
        )


@pytest.mark.asyncio
async def test_extensions():
    schema = Schema(query=Query)
    resp = await schema.execute(all_extensions_query)
    assert resp.errors is None
    assert len(resp.data["extensions"]) == 3
    p_dummy = resp.data["extensions"][0]
    assert p_dummy["authors"] == "aqueduct@riverlane.com"
    assert len(p_dummy["actions"]) == 2
    echo = p_dummy["actions"][0]
    assert echo["experimentVariableName"] == "var4"
    assert echo["parameters"][1]["displayName"] == "some display name"
