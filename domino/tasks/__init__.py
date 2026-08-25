from typing import Annotated, Union

from pydantic import Field

from .domino import DominoTask, ErrorTask, OperatorTask, SensorTask
from .standard import (
    BashTask,
    BranchPythonTask,
    EmptyTask,
    PythonTask,
    SmoothTask,
    TriggerDagRunTask,
)

Task = Annotated[
    Union[
        EmptyTask,
        SmoothTask,
        BashTask,
        PythonTask,
        BranchPythonTask,
        TriggerDagRunTask,
        DominoTask,
        ErrorTask,
        OperatorTask,
        SensorTask,
    ],
    Field(
        discriminator="type",
        description="A tasks or a group of tasks.",
    ),
]
