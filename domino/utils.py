from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Self

from airflow.configuration import conf
from airflow.sdk import Label
from pendulum import DateTime

from .models.context import TaskContext


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


def get_airflow_version() -> tuple[int, int, int]:
    """Get the Airflow version as a tuple of integers.

    Returns:
        tuple[int, int, int]: The Airflow version.
    """
    from airflow import version

    versions = list(map(int, version.split(".")))
    return versions[0], versions[1], versions[2]


def get_dags_path() -> Path | None:
    """Get the Airflow DAGs folder path from the Airflow configuration.

    Returns:
        Path | None: The Airflow DAGs folder path.
    """
    path_str: str | None = conf.get("core", "dags_folder", fallback=None)
    if path_str:
        return Path(path_str)
    return None


def set_upstream_and_teardown(
    tasks: dict[str, TaskContext],
    label_seperator: str = "::",
) -> None:  # NOSONAR
    """Set Upstream and Teardown Task for each tasks in mapping.

    Args:
        tasks (dict[str, TaskContext]): A mapping of task ID and TaskContext dict
            object.
        label_seperator (str, optional): A separator string for the task ID
            to split the label from the task ID. Defaults to "::".
    """
    for task in tasks:
        task_context: TaskContext = tasks[task]

        # Set upstream task if it is defined in the template.
        if upstream := task_context["upstreams"]:
            for t in upstream:
                try:
                    if label_seperator in t:
                        t, label = t.split(
                            label_seperator,
                            maxsplit=1,
                        )
                        if label:
                            task_context["task"].set_upstream(
                                tasks[t]["task"], edge_modifier=Label(label)
                            )
                            continue

                    # Default case without edge modifier
                    task_context["task"].set_upstream(tasks[t]["task"])
                except KeyError as e:
                    raise KeyError(
                        f"Task ids, {e}, does not found from the template.\n"
                        f"The current task key: {list(tasks.keys())}"
                    ) from e
        # Set setup & teardown task if it is defined in the template.
        if teardown := task_context.get("teardown"):
            try:
                task_context["task"].as_teardown(setups=tasks[teardown]["task"])
            except KeyError as e:
                raise KeyError(
                    f"Setups task id, {e}, does not found from the template.\n"
                    f"The current task key: {list(tasks.keys())}"
                ) from e


# Sentinel used instead of a two-step `key in d` + `d[key]` (2 hash lookups)
# so every traversal step costs exactly one hash lookup instead of two.
_MISSING = object()

# Distinct sentinel for get_raise(): marks "caller passed no default at all",
# as opposed to _MISSING which marks "key not found in the dict". Needed so
# get_raise(key, default=None) (explicit None) can be told apart from
# get_raise(key) (no default -> should raise on a truly missing key).
NOTSET = object()


class DotDict(dict):
    """Dictionary with dot-notation get/set methods.

    Supports nested key lookup/set using dot-separated strings

    - Strict mode: raises KeyError if missing
    - Safe mode: use '?' to skip missing keys

    !!! example

        Make dict to dotable:

        ``` py
        dot_dict = DotDict({"level1": {"level2": {"key": "value"}}})
        value = dot_dict["level1.level2.key"]  # "value"
        value = dot_dict.get("level1.level2.key")  # "value"
        value = dot_dict.get("level1.level2.missing_key?", default="default")  # "default"
        dot_dict.set("level1.level2.new_key", "new_value")
        new_value = dot_dict["level1.level2.new_key"]  # "new_value"
        ```
    """

    # DotDict never stores per-instance attributes beyond the dict's own
    # items, so this stops every instance from lazily growing a `__dict__`
    # (saves memory + a small amount of instantiation overhead).
    # Remove this line if you ever need `some_dot_dict.custom_attr = ...`.
    __slots__ = ()

    def _traverse(
        self,
        keys,
        default: Any = None,
        allow_safe: bool = True,
        raise_error: bool = True,
    ) -> Self | Any:
        """Traverse a dotted key path.

        Args:
            keys (list[str]): A list of keys to traverse.
            default (Any | None): A default value if the key path is missing.
            allow_safe (bool): Whether to allow safe mode with '?' suffix.
            raise_error (bool): Whether to raise KeyError on missing keys.

        Returns:
            Any | None: The value at the end of the key path or default.
        """
        value = self
        for key in keys:
            safe = False
            if allow_safe and key.endswith("?"):
                safe = True
                key = key[:-1]

            if isinstance(value, dict):
                # Single hash lookup via the unbound dict.get instead of
                # `key in value` followed by `value[key]` (2 lookups).
                # Using the unbound method also guarantees this stays a
                # plain dict lookup even if a nested value happens to be
                # a DotDict itself, instead of recursing into DotDict.get.
                found = dict.get(value, key, _MISSING)
                if found is _MISSING:
                    if safe:
                        return default
                    if raise_error:
                        raise KeyError(".".join(keys))
                    return default
                value = found
            else:
                if safe:
                    return default
                if raise_error:
                    raise KeyError(".".join(keys))
                return default
        return value

    def __getitem__(self, item: Any) -> Any:
        """Getter dict method with dot-notation support."""
        if isinstance(item, str) and "." in item:
            return self._traverse(
                item.split("."), allow_safe=True, raise_error=True
            )
        return super().__getitem__(item)

    def get(self, key, default: Any | None = None) -> Any | None:
        """Permissive get: always returns gracefully, never raises on missing keys.

        Unlike :meth:`get_raise`, a missing key always yields ``default``
        (``None`` when omitted) — there is no way to make this method raise
        via the public API.  Use this when a missing key is an acceptable
        outcome and a silent ``None`` is safe to propagate.

        Supports dotted key paths (e.g. ``"a.b.c"``) which are resolved by
        walking nested dicts via :meth:`_traverse`.  Non-string keys and
        plain (non-dotted) keys fall back to the standard ``dict.get``
        behavior.

        Args:
            key: A dotted key path string, or any non-string dict key.
            default: Returned when the key (or any segment of a dotted path)
                is missing.  Defaults to ``None``.

        Returns:
            The value at the end of the key path, or ``default`` if any
            segment is absent.
        """
        if not isinstance(key, str) or "." not in key:
            return super().get(key, default)
        return self._traverse(
            key.split("."), default=default, allow_safe=True, raise_error=False
        )

    def set(self, key, value: Any | None = None) -> None:
        """Setter dict method.

        Args:
            key (str): A dotted key path.
            value (Any | None): A value to set at the key path.

        Raises:
            KeyError: If strict mode is enabled and a key in the path is missing.
            TypeError: If a non-dict is encountered in the path.
        """
        # Combines the two original early-return checks
        # (`not isinstance(key, str)` and `"." not in key`) into one
        # short-circuited branch.
        if not isinstance(key, str) or "." not in key:
            self[key] = value
            return

        keys: list[str] = key.split(".")
        d = self
        strict: bool = True

        for k in keys[:-1]:
            if k.endswith("?"):
                strict = False
                k = k[:-1]

            # One hash lookup (dict.get) instead of `k not in d` + `d[k] = {}`
            # + `d = d[k]` (up to 3 lookups). When a new dict is created we
            # keep the reference directly instead of looking it back up.
            nxt = dict.get(d, k, _MISSING)
            if nxt is _MISSING:
                if strict:
                    raise KeyError(f"Key path '{key}' not found")
                nxt = {}
                d[k] = nxt
            elif not isinstance(nxt, dict):
                raise TypeError(f"Path '{k}' is not a dict")
            d = nxt

        last_key = keys[-1]
        if last_key.endswith("?"):
            strict = False
            last_key = last_key[:-1]

        if strict and last_key not in d:
            raise KeyError(f"Key path '{key}' not found")

        d[last_key] = value

    def get_raise(self, key, default: Any = NOTSET) -> Any:
        """Strict get: raise KeyError for missing keys when no default is given.

        This is the strict counterpart of :meth:`get`.  The two methods share
        the same dotted-path and safe-mode (``?``) logic, but differ in what
        happens when a key is absent:

        +------------------+---------------------+----------------------+
        | Situation        | ``get``             | ``get_raise``        |
        +==================+=====================+======================+
        | key found        | returns value       | returns value        |
        +------------------+---------------------+----------------------+
        | key missing,     | returns ``None``    | **raises KeyError**  |
        | no default given |                     |                      |
        +------------------+---------------------+----------------------+
        | key missing,     | returns ``default`` | returns ``default``  |
        | default given    |                     |                      |
        +------------------+---------------------+----------------------+
        | key ends with    | returns ``None``    | returns ``None``     |
        | ``?`` (safe mode)|                     | (no raise)           |
        +------------------+---------------------+----------------------+

        Intended for ``vars`` in RAW template rendering so
        ``vars('missing_key')`` fails loudly instead of producing a silent
        sentinel string that is hard to trace.

        Args:
            key: A dotted key path string.  Append ``?`` to any segment
                (or the whole key) to enable safe mode for that segment —
                a missing segment returns ``None`` / ``default`` instead
                of raising.
            default: Explicit fallback value.  When provided the method
                behaves identically to :meth:`get` and never raises.
                When omitted (``NOTSET``), a missing key raises
                ``KeyError``.

        Returns:
            The value at the end of the key path, or ``default`` if the key
            is absent and a default was given, or ``None`` in safe mode.

        Raises:
            KeyError: If the key is missing, no ``default`` was given, and
                safe mode (``?``) is not active.
        """
        has_default: bool = default is not NOTSET

        if not isinstance(key, str):
            # Single lookup via dict.get + sentinel, instead of
            # `key in self` followed by a second `super().__getitem__(key)`.
            found = dict.get(self, key, _MISSING)
            if found is not _MISSING:
                return found
            if has_default:
                return default
            raise KeyError(key)

        # Dotted key: _traverse handles '?' safe mode per segment.
        if "." in key:
            return self._traverse(
                key.split("."),
                default=default if has_default else None,
                allow_safe=True,
                raise_error=not has_default,
            )

        # Non-dotted key. NOTE: unlike get(), this strips a trailing '?'
        # even without a dot, so get_raise("foo?") checks "foo" rather than
        # a literal key named "foo?". get() does not do this for plain keys
        # (it only strips '?' inside dotted paths) -- so get_raise(key,
        # default=X) is not guaranteed identical to get(key, X) for a plain
        # key ending in '?'. Flagging this rather than silently unifying it,
        # since fixing it means changing get()'s existing behavior too.
        is_safe: bool = key.endswith("?")
        lookup: str = key[:-1] if is_safe else key

        found = dict.get(self, lookup, _MISSING)
        if found is not _MISSING:
            return found
        if is_safe or has_default:
            return default if has_default else None
        raise KeyError(key)


def to_bkk(dt: DateTime | None) -> DateTime | None:
    """Convert pendulum.DateTime object to Asia/Bangkok timezone.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.

    Returns:
        DateTime | None: A pendulum.DateTime object with Asia/Bangkok timezone
            or None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone("Asia/Bangkok")


def to_utc(dt: DateTime | None) -> DateTime | None:
    """Convert pendulum.DateTime object to UTC timezone.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.

    Returns:
        DateTime | None: A pendulum.DateTime object with UTC timezone or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone("UTC")


def date_add(
    dt: DateTime | None,
    years: int = 0,
    months: int = 0,
    weeks: int = 0,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: float = 0,
    microseconds: int = 0,
) -> DateTime | None:
    """Add time delta to pendulum.DateTime object.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.
        years (int): Number of years to add.
        months (int): Number of months to add.
        weeks (int): Number of weeks to add.
        days (int): Number of days to add.
        hours (int): Number of hours to add.
        minutes (int): Number of minutes to add.
        seconds (float): Number of seconds to add.
        microseconds (int): Number of microseconds to add.

    Returns:
        DateTime | None: A pendulum.DateTime object with added one day or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.add(
        years=years,
        months=months,
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
        microseconds=microseconds,
    )


def change_tz(dt: DateTime | None, tz: str = "UTC") -> DateTime | None:
    """Change timezone to pendulum.DateTime object.

    Args:
        dt (DateTime | None): A pendulum.DateTime object.
        tz (str): A timezone name that use to change.

    Returns:
        DateTime | None: A pendulum.DateTime object with changed timezone or
            None if dt is None.
    """
    if dt is None:
        return None
    return dt.in_timezone(tz)


def format_dt(
    dt: datetime | DateTime | None, fmt: str = "%Y-%m-%d %H:00:00%z"
) -> str | None:
    """Format string value on pendulum.DateTime or datetime object.

    Args:
        dt (datetime | DateTime | None): A datetime or pendulum.DateTime object.
        fmt (str): A format string that use with strftime method.

    Returns:
        str | None: A formatted string value or None if dt is None.
    """
    if dt is None:
        return None
    return dt.strftime(fmt)


def random_str(n: int = 6) -> str:
    """Random string charactor with specific length.

    Args:
        n (int): A length of random string.

    Returns:
        str: A random string charactor that generated from UUID4 and cut to n
            length.
    """
    return uuid.uuid4().hex[:n].lower()
