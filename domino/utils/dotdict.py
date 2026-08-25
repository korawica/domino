from typing import Any, Self

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
