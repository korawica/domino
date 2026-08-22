from typing import Annotated, Any, Literal, Union

from pydantic import Field

from domino.models.builder import BaseBuilder

from .standard import EmptyTask, PythonTask

Task = Annotated[
    Union[
        EmptyTask,
        PythonTask,
    ],
    Field(
        discriminator="type",
        description="A tasks or a group of tasks.",
    ),
]
