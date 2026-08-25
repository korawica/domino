import os


def get_bool_env(value: str) -> bool:
    """Get the boolean value from the environment variable.

    Args:
        value (str): The environment variable name.

    Returns:
        bool: The boolean value from the environment variable.
    """
    return os.getenv(value, "").strip().lower() in {"true", "yes", "1", "y"}
