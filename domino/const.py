import os
from typing import Final

MAX_THREADS_BUILD_TASK_GROUP: Final[int] = int(
    os.getenv("MAX_THREADS_BUILD_TASK_GROUP", "10")
)

NOTSET: Final[str] = "__notset__"

VAR_DOMINO_UNITTEST_MODE: Final[str] = "DOMINO_UNITTEST_MODE"
