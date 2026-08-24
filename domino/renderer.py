from __future__ import annotations

import logging
from re import DOTALL, VERBOSE, Pattern, compile

from jinja2 import DebugUndefined, Environment
from jinja2.nativetypes import NativeEnvironment

logger = logging.getLogger("domino")


JINJA_PATTERN: Pattern[str] = compile(
    r"""(
        \{\{.*?}}       # {{ ... }} expression
        |\{%.*?%}       # {% ... %} statement
        |\{\#.*?\#}     # {# ... #} comment (# escaped: VERBOSE-mode)
    )""",
    DOTALL | VERBOSE,
)


def is_jinja(s: str, pure: bool = True) -> bool:
    """Check whether a string contains a Jinja tag.

    Args:
        s (str): The string to inspect.
        pure (bool, default ``True``):
            If ``True`` , the whole string must consist of
            Jinja tags. If ``False``, any string containing at least
            one tag qualifies.

    Returns:
        ``True`` if ``s`` matches the criterion, ``False`` otherwise.

    Examples:
        >>> is_jinja("{{ x }}")
        True
        >>> is_jinja("hello {{ x }}")
        False
        >>> is_jinja("hello {{ x }}", pure=False)
        True
        >>> is_jinja("no jinja here", pure=False)
        False
    """
    if not pure:
        return JINJA_PATTERN.search(s) is not None
    covered = sum(m.end() - m.start() for m in JINJA_PATTERN.finditer(s))
    return 0 < covered == len(s)


class JinjaRenderer:
    """Jinja renderer object that using for rendering Jinja template fields in
    the model.
    """

    __slots__ = ("env",)

    def __init__(self) -> None:
        self.env: Environment = NativeEnvironment(
            undefined=DebugUndefined,
            autoescape=False,
            trim_blocks=False,
            lstrip_blocks=False,
        )
