import os
from datetime import timedelta


def get_bool_env(value: str) -> bool:
    """Get the boolean value from the environment variable.

    Args:
        value (str): The environment variable name.

    Returns:
        bool: The boolean value from the environment variable.
    """
    return os.getenv(value, "").strip().lower() in {"true", "yes", "1", "y"}


def int2seconds(value: int | None) -> timedelta | None:
    """Convert integer value to seconds.

    Args:
        value (int | None): The integer value.

    Returns:
        timedelta | None: The converted value in seconds.
    """
    if value is None:
        return None

    return timedelta(seconds=int(value))
