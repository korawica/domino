from __future__ import annotations

import logging
from pathlib import Path
from re import DOTALL, VERBOSE, Pattern, compile
from typing import Any

from jinja2 import DebugUndefined, Environment, Undefined, UndefinedError
from jinja2.exceptions import TemplateAssertionError
from jinja2.loaders import FileSystemLoader
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
    """An ``Undefined`` that raises on ``__str__``, ``__bool__``, or ``__iter__``
    instead of re-emitting.

        `jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes
    ``{{ X }}``. Raising instead lets `JinjaRenderer` catch the error and return
    the source text unchanged.

        Also raises on ``__bool__`` so that undefined variables in
    ``{% if condition %}`` blocks cause the whole block to be preserved
    instead of evaluating the else branch.

        Raises on ``__iter__`` so that undefined variables in
    ``{% for item in items %}`` blocks cause the whole block to be preserved
    instead of rendering nothing.
    """

    __slots__ = ()

    def __str__(self) -> str:
        self._fail_with_undefined_error()

    def __bool__(self) -> bool:
        self._fail_with_undefined_error()

    def __iter__(self):
        self._fail_with_undefined_error()


class JinjaRenderer:
    """Jinja renderer object that using for rendering Jinja template fields in
    the model.

        This renderer object focus on the partial rendering of the Jinja template fields.
    It will try to render with the current context and if it failed, it will
    return the original string without raising an error.
    This is useful for rendering the Jinja template fields in the model that may
    contain undefined variables or filters that are not available in the current
    context.
    """

    __slots__ = (
        "user_defined_macros",
        "user_defined_filters",
        "template_searchpath",
        "_env",
        "_env_str",
    )

    def __init__(
        self,
        *,
        user_defined_macros: dict[str, Any] | None = None,
        user_defined_filters: dict[str, Any] | None = None,
        template_searchpath: tuple[str | Path, ...] | None = None,
    ) -> None:
        """Initialize the Jinja renderer object.

        Args:
            user_defined_macros (dict[str, Any], optional):
                A dictionary of user-defined macros to be added to the Jinja environment.
            user_defined_filters (dict[str, Any], optional):
                A dictionary of user-defined filters to be added to the Jinja environment.
            template_searchpath (tuple[str | Path, ...], optional):
                A tuple of paths to search for template files.
                Required when using template file loading via ``template_ext``.
        """
        self.user_defined_macros: dict[str, Any] = user_defined_macros or {}
        self.user_defined_filters: dict[str, Any] = user_defined_filters or {}
        self.template_searchpath: list[str] | None = (
            [str(p) for p in template_searchpath]
            if template_searchpath is not None
            else None
        )
        self._env: Environment | None = None
        self._env_str: Environment | None = None
        self.post_init()

    def post_init(self) -> None:
        """Post-initialization method to set up the Jinja2 environment."""
        if self.user_defined_macros:
            self.env.globals.update(self.user_defined_macros)

        if self.user_defined_filters:
            self.env.filters.update(self.user_defined_filters)

    @property
    def env(self) -> Environment:
        """Return a Jinja2 Environment object for rendering templates."""
        env: Environment | None = self._env
        if env is None:
            loader: FileSystemLoader | None = (
                FileSystemLoader(self.template_searchpath)
                if self.template_searchpath is not None
                else None
            )
            env: Environment = NativeEnvironment(
                loader=loader,
                undefined=PreserveUndefined,
                extensions=["jinja2.ext.do"],
                autoescape=False,
                trim_blocks=False,
                lstrip_blocks=False,
                cache_size=0,
            )
            self._env = env
        return env

    @property
    def env_str(self) -> Environment:
        """Return a Jinja2 Environment object for rendering templates from strings."""
        env_str: Environment | None = self._env_str
        if env_str is None:
            env_str: Environment = Environment(
                undefined=PreserveUndefined,
                autoescape=False,
            )
            self._env_str = env_str
        return env_str

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
                        k: self._walk(v, _seen=_seen, template_ext=template_ext)
                        for k, v in value.items()
                    }
                if isinstance(value, list):
                    return [
                        self._walk(e, _seen=_seen, template_ext=template_ext)
                        for e in value
                    ]
                return {
                    self._walk(e, _seen=_seen, template_ext=template_ext)
                    for e in value
                }
            finally:
                _seen.discard(oid)

        if isinstance(value, tuple):
            items = [
                self._walk(e, _seen=_seen, template_ext=template_ext)
                for e in value
            ]
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
        if template_ext and value.endswith(template_ext):
            logger.debug("👀 Render Template File: %s", value)
            return self.env.get_template(value).render()

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
                #   Fall back to regular Environment for string output.
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
