# pylint: skip-file
"""Common test fixtures"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aqueductcore.backend.context import UserScope
from aqueductcore.backend.models import orm
from aqueductcore.backend.models.experiment import ExperimentCreate
from aqueductcore.backend.models.task import TaskCreate
from aqueductcore.backend.settings import settings
from tests.unittests.initial_data import experiment_data, task_data, user_data

async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

async_session = async_sessionmaker(bind=async_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Session for SQLAlchemy."""
    # await create_tables(engine)
    async with async_session() as session:
        async with async_engine.begin() as conn:
            await conn.run_sync(orm.Base.metadata.create_all)

        yield session

    async with async_engine.begin() as conn:
        await conn.run_sync(orm.Base.metadata.drop_all)

    await async_engine.dispose()


@pytest.fixture()
def experiments_data() -> List[ExperimentCreate]:
    data = experiment_data
    return data


@pytest.fixture()
def tasks_data() -> List[TaskCreate]:
    data = task_data
    return data


@pytest.fixture()
def users_data() -> List[orm.User]:
    return user_data


@pytest_asyncio.fixture
async def temp_experiment_files(db_session: AsyncSession, experiments_data: List[ExperimentCreate]):
    experiment_files: Dict[UUID, List[Tuple[str, datetime]]] = {}

    for experiment in experiments_data:
        Path(os.path.join(settings.experiments_dir_path, str(experiment.uuid))).mkdir(
            parents=True, exist_ok=True
        )

        experiment_files[experiment.uuid] = []
        for idx in range(5):
            file_name = f"file_{experiment.uuid}_{idx}"
            file_path = os.path.join(settings.experiments_dir_path, str(experiment.uuid), file_name)
            Path(file_path).touch(exist_ok=False)
            experiment_files[experiment.uuid].append(
                (
                    file_name,
                    datetime.fromtimestamp(Path(file_path).stat().st_mtime, tz=timezone.utc),
                )
            )

    yield experiment_files

    for experiment_uuid in experiment_files.keys():
        shutil.rmtree(os.path.join(settings.experiments_dir_path, str(experiment_uuid)))


class Scopes:
    """Presets of scopes"""

    @staticmethod
    def admin_scope():
        return set(UserScope)

    @staticmethod
    def manager_scope():
        return {
            UserScope.EXPERIMENT_CREATE_OWN,
            UserScope.EXPERIMENT_VIEW_OWN,
            UserScope.EXPERIMENT_VIEW_ALL,
            UserScope.EXPERIMENT_EDIT_OWN,
            UserScope.JOB_CREATE,
            UserScope.JOB_VIEW_ALL,
            UserScope.JOB_VIEW_OWN,
            UserScope.JOB_CANCEL_OWN,
        }

    @staticmethod
    def user_scope():
        return {
            UserScope.EXPERIMENT_CREATE_OWN,
            UserScope.EXPERIMENT_VIEW_OWN,
            UserScope.EXPERIMENT_EDIT_OWN,
            UserScope.JOB_CREATE,
            UserScope.JOB_VIEW_OWN,
            UserScope.JOB_CANCEL_OWN,
        }

    @staticmethod
    def mighty_user_scope():
        return {
            UserScope.EXPERIMENT_CREATE_OWN,
            UserScope.EXPERIMENT_VIEW_OWN,
            UserScope.EXPERIMENT_EDIT_OWN,
            UserScope.JOB_CREATE,
            UserScope.JOB_VIEW_OWN,
            UserScope.JOB_VIEW_ALL,
            UserScope.JOB_CANCEL_OWN,
        }

    @staticmethod
    def blind_jobs_scope():
        return {
            UserScope.EXPERIMENT_CREATE_OWN,
            UserScope.EXPERIMENT_VIEW_OWN,
            UserScope.EXPERIMENT_EDIT_OWN,
            UserScope.JOB_CREATE,
            UserScope.JOB_CANCEL_OWN,
        }

    @staticmethod
    def blind_experiments_scope():
        return {
            UserScope.EXPERIMENT_CREATE_OWN,
            UserScope.JOB_VIEW_OWN,
            UserScope.EXPERIMENT_EDIT_OWN,
            UserScope.JOB_CREATE,
            UserScope.JOB_CANCEL_OWN,
        }