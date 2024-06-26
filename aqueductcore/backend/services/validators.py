"""Validator functions to validate different inputs and parameters"""

from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

from aqueductcore.backend.errors import AQDValidationError
from aqueductcore.backend.services.utils import is_tag_valid

MAX_EXPERIMENTS_PER_REQUEST = 500
MAX_TAGS_PER_REQUEST = 500

MAX_EXPERIMENT_TITLE_LENGTH = 256
MAX_EXPERIMENT_DESCRIPTION_LENGTH = 5000
MAX_EXPERIMENT_TAG_LENGTH = 64
MAX_EXPERIMENT_TAGS_NUM = 64

MAX_EXPERIMENT_TITLE_FILTER_LENGTH = 64
MAX_EXPERIMENT_SHOULD_INCLUDE_TAGS_NUM = 6
MAX_EXPERIMENT_TAGS_ALLOWED_IN_FILTER = 10


def validate_title(title: str, max_len: int) -> str:
    """Validate title to have a specified maximum length"""
    if len(title) > max_len:
        raise AQDValidationError(f"Title should be maximum {max_len} characters long.")

    return title


def validate_description(description: str, max_len: int) -> str:
    """Validate description to have a specified maximum length"""
    if len(description) > max_len:
        raise AQDValidationError(f"Description should be maximum {max_len} characters long.")

    return description


def validate_tag(tag: str, max_len: int) -> str:
    """Validate tag to have a specified maximum length and allowed characters only"""
    if not tag:
        raise AQDValidationError(
            "Tag cannot be empty"
        )

    if len(tag) > max_len:
        raise AQDValidationError(
            f"Tag should be less than {max_len} characters long "
        )

    if not is_tag_valid(tag):
        raise AQDValidationError(
            "Tag can only contain alphanumeric characters, colons, hyphens, underscores and slashes"
        )

    return tag


ExperimentTitle = Annotated[
    str, AfterValidator(lambda v: validate_title(v, max_len=MAX_EXPERIMENT_TITLE_LENGTH))
]
ExperimentTitleFilter = Annotated[
    str, AfterValidator(lambda v: validate_title(v, max_len=MAX_EXPERIMENT_TITLE_FILTER_LENGTH))
]
ExperimentDescription = Annotated[
    str,
    AfterValidator(lambda v: validate_description(v, max_len=MAX_EXPERIMENT_DESCRIPTION_LENGTH)),
]
ExperimentTag = Annotated[
    str, AfterValidator(lambda v: validate_tag(v, max_len=MAX_EXPERIMENT_TAG_LENGTH))
]
