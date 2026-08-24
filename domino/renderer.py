from __future__ import annotations

import logging
from collections.abc import Callable
from re import DOTALL, VERBOSE, Pattern, compile
from typing import Any, Self, cast

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

    :class:`jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes
    ``{{ X }}``. Raising instead lets :class:`JinjaRender` catch the
    error and return the source text unchanged.
    """

    __slots__ = ()

    def __str__(self) -> str:
        self._fail_with_undefined_error()


class JinjaRender:
    """Two-step Jinja renderer for partial → real rendering flows.

    The renderer builds two :class:`~jinja2.nativetypes.NativeEnvironment`
    instances (native-type preserving) sharing the same globals and
    filters:

    - :attr:`env` — strict mode; unresolved names raise.
    - :attr:`partial_env` — partial mode; unresolved names round-trip
      as literal text so the output can be rendered again later.

    Examples:
        >>> r = JinjaRender(user_defined_macros={"pkg_var": "abc"})
        >>> partial = r.render_partial("{{ pkg_var }}-{{ runtime_var }}")
        >>> partial
        'abc-{{ runtime_var }}'
        >>> _ = r.set_globals({"runtime_var": "xyz"})
        >>> r.render(partial)
        'abc-xyz'

        Airflow two-step flow — render your macros first, then let
        Airflow render its DAG Run context at execution time::

            >>> r = JinjaRender(user_defined_macros={"pkg_var": "abc"})
            >>> r.render_partial("{{ pkg_var }}/dt={{ logical_date }}")
            'abc/dt={{ logical_date }}'
            >>> # step 2: Airflow later renders '{{ logical_date }}'
    """

    __slots__ = (
        "template_fields",
        "template_fields_excluded",
        "user_defined_filters",
        "user_defined_macros",
        "env",
        "string_env",
        "partial_env",
        "partial_string_env",
    )

    def __init__(
        self,
        *,
        template_fields: tuple[str, ...] | None = None,
        template_fields_excluded: tuple[str, ...] | None = None,
        user_defined_filters: dict[str, Callable] | None = None,
        user_defined_macros: dict[str, Callable | Any] | None = None,
        extensions: list[str] | None = None,
    ) -> None:
        self.template_fields = template_fields or ()
        self.template_fields_excluded = template_fields_excluded or ()
        self.user_defined_filters = user_defined_filters or {}
        self.user_defined_macros = user_defined_macros or {}

        _extensions: list[str] = extensions or ["jinja2.ext.do"]

        self.env: Environment = NativeEnvironment(
            undefined=Undefined, extensions=_extensions
        )
        self.string_env: Environment = Environment(
            undefined=Undefined, extensions=_extensions
        )
        self.partial_env: Environment = NativeEnvironment(
            undefined=PreserveUndefined, extensions=_extensions
        )
        self.partial_string_env: Environment = Environment(
            undefined=PreserveUndefined, extensions=_extensions
        )
        for env in (
            self.env,
            self.string_env,
            self.partial_env,
            self.partial_string_env,
        ):
            env.globals.update(self.user_defined_macros)
            env.filters.update(self.user_defined_filters)

    def render(self, value: Any) -> Any:
        """Recursively render ``value`` in strict mode.

        Strings inside lists/dicts/sets/tuples are rendered; other
        types pass through unchanged. Unresolved names or syntax
        errors propagate.
        """
        return self._walk(value, partial=False)

    def render_partial(self, value: Any) -> Any:
        """Recursively render ``value`` in partial mode.

        Like :meth:`render`, but unresolved macros/filters/variables
        are left as literal Jinja text so the result can be rendered
        again later. ``TemplateSyntaxError`` still propagates.
        """
        return self._walk(value, partial=True)

    def render_template(self, data: Any) -> Any:
        """Strict-render only the keys listed in :attr:`template_fields`.

        Non-dict input is passed straight to :meth:`render`.
        """
        if not isinstance(data, dict):
            return self.render(data)
        excluded = self.template_fields_excluded
        for key in self.template_fields:
            if key in data and key not in excluded:
                data[key] = self.render(data[key])
        return data

    def render_template_partial(self, data: Any) -> Any:
        """Partial-render only the keys listed in :attr:`template_fields`.

        Non-dict input is passed straight to :meth:`render_partial`.
        """
        if not isinstance(data, dict):
            return self.render_partial(data)
        excluded = self.template_fields_excluded
        for key in self.template_fields:
            if key in data and key not in excluded:
                data[key] = self.render_partial(data[key])
        return data

    def set_globals(self, values: dict[str, Any]) -> Self:
        """Update every environment's globals in place. Returns ``self``."""
        self.user_defined_macros.update(values)
        self.env.globals.update(values)
        self.string_env.globals.update(values)
        self.partial_env.globals.update(values)
        self.partial_string_env.globals.update(values)
        return self

    def _walk(
        self,
        value: Any,
        *,
        partial: bool,
        _seen: set[int] | None = None,
    ) -> Any:
        """Recursively render Jinja templates inside ``value``.

        Traverses lists/dicts/sets/tuples (including NamedTuple),
        renders strings via :meth:`_render`, guards against cycles,
        and returns unknown types unchanged.
        """
        if isinstance(value, str):
            return self._render(value, partial=partial)

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
                        k: self._walk(v, partial=partial, _seen=_seen)
                        for k, v in value.items()
                    }
                if isinstance(value, list):
                    return [
                        self._walk(e, partial=partial, _seen=_seen)
                        for e in value
                    ]
                return {
                    self._walk(e, partial=partial, _seen=_seen) for e in value
                }
            finally:
                _seen.discard(oid)

        if isinstance(value, tuple):
            items = [self._walk(e, partial=partial, _seen=_seen) for e in value]
            return (
                tuple(items)
                if value.__class__ is tuple
                else value.__class__(*items)
            )

        return value

    def _render(self, value: str, *, partial: bool) -> Any:
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
        if not is_jinja(value, pure=False):
            return value
        logger.debug("👀 Render Template: %s", value)

        if not partial:
            try:
                return self.env.from_string(value).render()
            except TypeError:
                # ``NativeEnvironment`` runs ``ast.literal_eval`` on
                #   the rendered text and can raise ``TypeError`` for
                #   legit output like ``{{ 1 }}`` (from ``{% raw %}``)
                #   which parses as an unhashable set-of-set. Fall
                #   back to plain string rendering — same globals,
                #   same strict undefined.
                return self.string_env.from_string(value).render()

        def _try(source: str) -> Any:
            try:
                rendered = cast(
                    Any, self.partial_env.from_string(source).render()
                )
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
                    return self.partial_string_env.from_string(source).render()
                except (TemplateAssertionError, UndefinedError):
                    return source
            return source if isinstance(rendered, Undefined) else rendered

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
