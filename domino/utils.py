from pathlib import Path
from typing import Any, Self

from airflow.configuration import conf
from airflow.sdk import Label

from .const import NOTSET
from .models.context import TaskContext


def get_dags_path() -> Path | None:
    """Get the Airflow DAGs folder path from the Airflow configuration.

    Returns:
        str: The Airflow DAGs folder path.
    """
    path_str: str | None = conf.get("core", "dags_folder", fallback=None)
    if path_str:
        return Path(path_str)
    return None


def set_upstream_and_teardown(
    tasks: dict[str, TaskContext],
    label_sep_on_task_id: str = "::",
) -> None:  # NOSONAR
    """Set Upstream and Teardown Task for each tasks in mapping.

    Args:
        tasks (dict[str, TaskContext]): A mapping of task ID and TaskContext dict
            object.
        label_sep_on_task_id (str, optional): A separator string for the task ID
            to split the label from the task ID. Defaults to "::".
    """
    for task in tasks:
        task_mapped: TaskContext = tasks[task]

        # Set upstream task if it is defined in the template.
        if upstream := task_mapped["upstream"]:
            for t in upstream:
                try:
                    if label_sep_on_task_id in t:
                        t, label = t.split(
                            label_sep_on_task_id,
                            maxsplit=1,
                        )
                        if label:
                            task_mapped["task"].set_upstream(
                                tasks[t]["task"], edge_modifier=Label(label)
                            )
                            continue

                    # Default case without edge modifier
                    task_mapped["task"].set_upstream(tasks[t]["task"])
                except KeyError as e:
                    raise KeyError(
                        f"Task ids, {e}, does not found from the template.\n"
                        f"The current task key: {list(tasks.keys())}"
                    ) from e
        # Set setup & teardown task if it is defined in the template.
        if teardown := task_mapped.get("teardown"):
            try:
                task_mapped["task"].as_teardown(setups=tasks[teardown]["task"])
            except KeyError as e:
                raise KeyError(
                    f"Setups task id, {e}, does not found from the template.\n"
                    f"The current task key: {list(tasks.keys())}"
                ) from e


class DotDict(dict):
    """Dictionary with dot-notation get/set methods.

    Supports nested key lookup/set using dot-separated strings

    - Strict mode: raises KeyError if missing
    - Safe mode: use '?' to skip missing keys

    !!! examole

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

            if isinstance(value, dict) and key in value:
                value = value[key]
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

    def set(self, key, value: Any | None) -> None:
        """Setter dict method.

        Args:
            key (str): A dotted key path.
            value (Any | None): A value to set at the key path.

        Raises:
            KeyError: If strict mode is enabled and a key in the path is missing.
            TypeError: If a non-dict is encountered in the path.
        """

        if not isinstance(key, str):
            self[key] = value
            return

        if "." not in key:
            self[key] = value
            return

        keys: list[str] = key.split(".")
        d = self
        strict: bool = True

        for k in keys[:-1]:
            safe = k.endswith("?")
            if safe:
                strict = False
                k = k[:-1]

            if k not in d:
                if strict:
                    raise KeyError(f"Key path '{key}' not found")
                d[k] = {}
            d = d[k]

            if not isinstance(d, dict):
                raise TypeError(f"Path '{k}' is not a dict")

        last_key = keys[-1]
        if last_key.endswith("?"):
            strict: bool = False
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
        has_default: bool = default != NOTSET

        if not isinstance(key, str):
            if key in self:
                return super().__getitem__(key)
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

        # Non-dotted key
        is_safe: bool = key.endswith("?")
        lookup: str = key[:-1] if is_safe else key

        if lookup in self:
            return super().__getitem__(lookup)
        if is_safe or has_default:
            return default if has_default else None
        raise KeyError(key)
