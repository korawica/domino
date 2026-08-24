from __future__ import annotations

import logging
from re import DOTALL, VERBOSE, Pattern, compile
from typing import Any

from jinja2 import DebugUndefined, Environment, Undefined, UndefinedError
from jinja2.exceptions import TemplateAssertionError
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


class PreserveUndefined(DebugUndefined):
    """An ``Undefined`` that raises on ``__str__`` instead of re-emitting.

        `jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes
    ``{{ X }}``. Raising instead lets `JinjaRenderer` catch the error and return
    the source text unchanged.
    """

    __slots__ = ()

    def __str__(self) -> str:
        self._fail_with_undefined_error()


class JinjaRenderer:
    """Jinja renderer object that using for rendering Jinja template fields in
    the model.
    """

    __slots__ = (
        "user_defined_macros",
        "user_defined_filters",
        "_env",
        "_env_str",
    )

    def __init__(
        self,
        user_defined_macros: dict[str, Any] | None = None,
        user_defined_filters: dict[str, Any] | None = None,
    ) -> None:
        self.user_defined_macros: dict[str, Any] = user_defined_macros or {}
        self.user_defined_filters: dict[str, Any] = user_defined_filters or {}
        self._env: Environment | None = None
        self._env_str: Environment | None = None

    def post_init(self) -> None:
        """Post-initialization method to set up the Jinja2 environment."""
        env = self.env
        env_str = self.env_str
        if self.user_defined_macros:
            env.globals.update(self.user_defined_macros)
            env_str.globals.update(self.user_defined_macros)

        if self.user_defined_filters:
            env.filters.update(self.user_defined_filters)
            env_str.filters.update(self.user_defined_filters)

    @property
    def env(self) -> Environment:
        """Return a Jinja2 Environment object for rendering templates."""
        env: Environment | None = self._env
        if env is None:
            env: Environment = NativeEnvironment(
                undefined=DebugUndefined,
                extensions=["jinja2.ext.do"],
                autoescape=False,
                trim_blocks=False,
                lstrip_blocks=False,
            )
            self._env = env
            return env
        return env

    @property
    def env_str(self) -> Environment:
        """Return a Jinja2 Environment object for rendering templates as strings."""
        env: Environment | None = self._env_str
        if env is None:
            env: Environment = NativeEnvironment(
                undefined=PreserveUndefined,
                extensions=["jinja2.ext.do"],
                autoescape=False,
                trim_blocks=False,
                lstrip_blocks=False,
            )
            self._env_str = env
            return env
        return env

    def render(
        self,
        value: Any,
        template_ext: tuple[str, ...] | None = None,
    ) -> Any:
        return self._walk(value, template_ext=template_ext)

    def _walk(
        self,
        value: Any,
        *,
        template_ext: tuple[str, ...] | None = None,
        _seen: set[int] | None = None,
    ) -> Any:
        """Recursively render Jinja templates inside ``value``.

        Traverses lists/dicts/sets/tuples (including NamedTuple),
        renders strings via :meth:`_render`, guards against cycles,
        and returns unknown types unchanged.
        """
        if isinstance(value, str):
            return self._render(value, template_ext=template_ext)

        if isinstance(value, (list, dict, set)):
            oid = id(value)
            if _seen is None:
                _seen = set()
            elif oid in _seen:
                return value  # cycle guard
            _seen.add(oid)
            try:
                if isinstance(value, dict):
                    return {
                        k: self._walk(v, _seen=_seen) for k, v in value.items()
                    }
                if isinstance(value, list):
                    return [self._walk(e, _seen=_seen) for e in value]
                return {self._walk(e, _seen=_seen) for e in value}
            finally:
                _seen.discard(oid)

        if isinstance(value, tuple):
            items = [self._walk(e, _seen=_seen) for e in value]
            return (
                tuple(items)
                if value.__class__ is tuple
                else value.__class__(*items)
            )

        return value

    def _render(
        self,
        value: str,
        *,
        template_ext: tuple[str, ...] | None = None,
    ) -> Any:
        """Render one string.

        - Strings without any Jinja tag pass through unchanged.
        - Strict mode: rendered via :attr:`env`; errors propagate.
        - Partial mode: mixed inline templates (multiple tags, or a
          single tag with surrounding literal text) are split and
          rendered per expression so resolvable parts survive.
          Templates with ``{% ... %}`` blocks or ``{# ... #}``
          comments — and single whole-string tags — are rendered as
          a unit (all-or-nothing) so ``NativeEnvironment`` can
          preserve native Python types.
        """
        _ = template_ext
        if not is_jinja(value, pure=False):
            return value

        logger.debug("👀 Render Template: %s", value)

        def _try(source: str) -> Any:
            try:
                _rendered = self.env.from_string(source).render()
            except TemplateAssertionError:
                # Unknown filter/test/macro at parse time.
                #   TemplateSyntaxError (parent) still propagates.
                return source
            except UndefinedError:
                return source
            except TypeError:
                # NativeEnvironment feeds the rendered text through
                #   ``ast.literal_eval``; some strings (e.g. ``{{ 1 }}``
                #   emitted by ``{% raw %}...{% endraw %}``) parse as
                #   unhashable literals and raise ``TypeError``.
                #   Fall back to a plain string render.
                try:
                    return self.env_str.from_string(source).render()
                except (TemplateAssertionError, UndefinedError):
                    return source
            return source if isinstance(_rendered, Undefined) else _rendered

        # Splittable = no blocks/comments AND (multiple tags OR one
        #   tag not covering the entire string). The regex has a
        #   capturing group, so re.split alternates literal text (even
        #   indices) with Jinja tags (odd indices).
        if "{%" not in value and "{#" not in value:
            matches = JINJA_PATTERN.findall(value)
            if len(matches) > 1 or (len(matches) == 1 and matches[0] != value):
                out: list[str] = []
                for i, part in enumerate(JINJA_PATTERN.split(value)):
                    if not part:
                        continue
                    if i % 2 == 0:
                        out.append(part)
                        continue
                    rendered = _try(part)
                    if rendered is part:
                        out.append(part)
                    elif rendered is not None:
                        out.append(str(rendered))
                return "".join(out)

        return _try(value)
