from typing import Annotated, Union

from pydantic import Field

from .standard import EmptyTask, PythonTask

Register = Annotated[
    Union[
        EmptyTask,
        PythonTask,
    ],
    Field(
        discriminator="type",
        description="A tasks or a group of tasks.",
    ),
]
