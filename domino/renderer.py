from __future__ import annotations

import logging
from collections.abc import Callable
from re import DOTALL, VERBOSE, Pattern, compile
from typing import Any, Self, cast

from jinja2 import (
    DebugUndefined,
    Environment,
    FileSystemLoader,
    Template,
    Undefined,
    UndefinedError,
)
from jinja2.exceptions import TemplateAssertionError
from jinja2.nativetypes import NativeEnvironment
from jinja2.sandbox import SandboxedEnvironment

logger = logging.getLogger("domino")

JINJA_PATTERN: Pattern[str] = compile(
    r"""(
        \{\{.*?}}       # {{ ... }} expression
        |\{%.*?%}       # {% ... %} statement
        |\{#.*?#}       # {# ... #} comment
    )""",
    DOTALL | VERBOSE,
)


def is_jinja(s: str, pure: bool = True) -> bool:
    """Check whether ``s`` contains a Jinja tag.

    ``pure=True`` (default) requires the whole string to consist of
    Jinja tags; ``pure=False`` accepts any string containing at least
    one tag.

    Examples:
        >>> is_jinja("{{ x }}", pure=True)
        True
        >>> is_jinja("hello {{ x }}", pure=True)
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
    """Undefined that raises on ``__str__``.

    :class:`jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes
    ``{{ X }}``. Raising instead lets :class:`JinjaRender` catch the
    error and return the source text unchanged.
    """

    __slots__ = ()

    def __str__(self) -> str:
        self._fail_with_undefined_error()


class JinjaRender:
    """Two-mode Jinja renderer.

    - :meth:`render` — standard Jinja. Any unresolved reference or
      syntax error propagates.
    - :meth:`render_debug` — returns the source text untouched for
      unknown macros, filters, or variables. Real
      :class:`TemplateSyntaxError` still propagates.

    In debug mode, mixed inline templates preserve *per expression*:
    ``"{{ pkg_var }}-{{ runtime_var }}"`` becomes
    ``"abc-{{ runtime_var }}"`` when only ``pkg_var`` is registered.
    Single-tag templates and templates containing ``{% ... %}`` blocks
    are rendered whole (all-or-nothing).

    !!! example

        ```py
        r = JinjaRender(user_defined_macros={"pkg_var": "abc"})
        partial = r.render_debug("{{ pkg_var }}-{{ runtime_var }}")
        # -> "abc-{{ runtime_var }}"

        r.set_globals({"runtime_var": "xyz"})
        r.render(partial)   # -> "abc-xyz"
        ```
    """

    __slots__ = (
        "template_fields",
        "template_ext",
        "template_fields_excluded",
        "template_searchpath",
        "user_defined_filters",
        "user_defined_macros",
        "jinja_environment_kwargs",
        "env_factory",
        "is_native",
        "env",
        "debug_env",
    )

    def __init__(
        self,
        *,
        template_fields: tuple[str, ...] | None = None,
        template_ext: tuple[str, ...] | None = None,
        template_fields_excluded: tuple[str, ...] | None = None,
        template_searchpath: tuple[str, ...] | None = None,
        user_defined_filters: dict[str, Callable] | None = None,
        user_defined_macros: dict[str, Callable | Any] | None = None,
        jinja_environment_kwargs: dict[str, Any] | None = None,
        env_factory: type[Environment] | None = None,
        is_native: bool = True,
    ) -> None:
        self.template_fields = template_fields or ()
        self.template_ext = template_ext or ()
        self.template_fields_excluded = template_fields_excluded or ()
        self.template_searchpath = template_searchpath or ()
        self.user_defined_filters = user_defined_filters or {}
        self.user_defined_macros = user_defined_macros or {}
        self.jinja_environment_kwargs = jinja_environment_kwargs or {}
        self.env_factory = env_factory
        self.is_native = is_native

        self.env: Environment = self._build_env(preserve=False)
        self.debug_env: Environment = self._build_env(preserve=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, value: Any) -> Any:
        """Normal-mode render. Any Jinja error propagates."""
        return self._walk(value, self._render_strict)

    def render_debug(self, value: Any) -> Any:
        """Debug-mode render. Unresolved references round-trip verbatim."""
        return self._walk(value, self._render_debug)

    def render_template(self, data: Any) -> Any:
        """Apply :meth:`render` to :attr:`template_fields` entries in ``data``."""
        return self._apply_template(data, self.render)

    def render_template_debug(self, data: Any) -> Any:
        """Apply :meth:`render_debug` to :attr:`template_fields` entries."""
        return self._apply_template(data, self.render_debug)

    def set_globals(self, values: dict[str, Any]) -> Self:
        """Update the globals of both Jinja environments in-place."""
        self.user_defined_macros.update(values)
        self.env.globals.update(values)
        self.debug_env.globals.update(values)
        return self

    def copy_override(
        self,
        *,
        template_fields: tuple[str, ...] | None = None,
        template_ext: tuple[str, ...] | None = None,
        template_fields_excluded: tuple[str, ...] | None = None,
        template_searchpath: tuple[str, ...] | None = None,
        user_defined_filters: dict[str, Callable] | None = None,
        user_defined_macros: dict[str, Callable | Any] | None = None,
        jinja_environment_kwargs: dict[str, Any] | None = None,
        env_factory: type[Environment] | None = None,
        is_native: bool | None = None,
    ) -> Self:
        """Return a new renderer with the given fields overridden.

        Collection-like arguments (filters, macros, searchpath, kwargs)
        are merged with the current instance so callers only supply
        the delta.
        """
        return self.__class__(
            template_fields=template_fields or self.template_fields,
            template_ext=template_ext or self.template_ext,
            template_fields_excluded=(
                template_fields_excluded or self.template_fields_excluded
            ),
            template_searchpath=(
                self.template_searchpath + (template_searchpath or ())
            ),
            user_defined_filters=(
                self.user_defined_filters | (user_defined_filters or {})
            ),
            user_defined_macros=(
                self.user_defined_macros | (user_defined_macros or {})
            ),
            jinja_environment_kwargs=(
                self.jinja_environment_kwargs | (jinja_environment_kwargs or {})
            ),
            env_factory=env_factory or self.env_factory,
            is_native=self.is_native if is_native is None else is_native,
        )

    # ------------------------------------------------------------------
    # Internals — environment
    # ------------------------------------------------------------------

    def _build_env(self, *, preserve: bool) -> Environment:
        """Build a Jinja environment. ``preserve`` picks the Undefined class."""
        options: dict[str, Any] = {
            "undefined": PreserveUndefined if preserve else Undefined,
            "extensions": ["jinja2.ext.do"],
            "cache_size": 0,
        }
        if self.template_searchpath:
            options["loader"] = FileSystemLoader(self.template_searchpath)
        options.update(self.jinja_environment_kwargs)

        env_cls: type[Environment] = self.env_factory or (
            NativeEnvironment if self.is_native else SandboxedEnvironment
        )
        env = env_cls(**options)
        env.globals.update(self.user_defined_macros)
        env.filters.update(self.user_defined_filters)
        return env

    # ------------------------------------------------------------------
    # Internals — recursion
    # ------------------------------------------------------------------

    def _apply_template(
        self, data: Any, render_fn: Callable[[Any], Any]
    ) -> Any:
        if not isinstance(data, dict):
            return render_fn(data)
        excluded = self.template_fields_excluded
        for key in self.template_fields:
            if key in data and key not in excluded:
                data[key] = render_fn(data[key])
        return data

    def _walk(
        self,
        value: Any,
        render_str: Callable[[str], Any],
        _seen: set[int] | None = None,
    ) -> Any:
        """Recursively render Jinja templates inside ``value``."""
        if isinstance(value, str):
            return render_str(value)

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
                        k: self._walk(v, render_str, _seen)
                        for k, v in value.items()
                    }
                if isinstance(value, list):
                    return [self._walk(e, render_str, _seen) for e in value]
                return {self._walk(e, render_str, _seen) for e in value}
            finally:
                _seen.discard(oid)

        if isinstance(value, tuple):
            # Immutable — no cycle guard needed. Handle NamedTuple too.
            items = [self._walk(e, render_str, _seen) for e in value]
            return (
                tuple(items)
                if value.__class__ is tuple
                else value.__class__(*items)
            )

        return value

    # ------------------------------------------------------------------
    # Internals — string rendering
    # ------------------------------------------------------------------

    def _render_strict(self, value: str) -> Any:
        """Render one string in normal mode."""
        if self.template_ext and value.endswith(self.template_ext):
            return self.env.get_template(value).render()
        if not is_jinja(value, pure=False):
            return value
        logger.debug("👀 Render Template: %s", value)
        return self.env.from_string(value).render()

    def _render_debug(self, value: str) -> Any:
        """Render one string in debug mode."""
        if self.template_ext and value.endswith(self.template_ext):
            return self._try_render(self.debug_env.get_template(value), value)
        if not is_jinja(value, pure=False):
            return value
        if _is_splittable(value):
            return self._render_split(value)
        return self._try_source(value)

    def _try_source(self, source: str) -> Any:
        """Debug-render ``source`` from scratch; return it verbatim on failure."""
        try:
            template = self.debug_env.from_string(source)
        except TemplateAssertionError:
            # Unknown filter/test/macro at parse time. ``TemplateSyntaxError``
            # (its superclass) is *not* caught and always propagates.
            return source
        return self._try_render(template, source)

    def _try_render(self, template: Template, source: str) -> Any:
        """Render ``template``; return ``source`` on undefined."""
        logger.debug("👀 Render Template: %s", source)
        try:
            # NativeEnvironment can return any Python value (including
            # an Undefined instance for a single-tag body — native_concat
            # skips ``str`` coercion), which Jinja's stub misses.
            result = cast(Any, template.render())
        except UndefinedError:
            return source
        return source if isinstance(result, Undefined) else result

    def _render_split(self, value: str) -> str:
        """Render each ``{{ ... }}`` in ``value`` independently and concat.

        ``JINJA_PATTERN`` uses a capturing group, so ``re.split`` alternates
        literal text (even indices) with Jinja tags (odd indices).
        """
        out: list[str] = []
        for i, part in enumerate(JINJA_PATTERN.split(value)):
            if not part:
                continue
            if i % 2 == 0:  # literal text
                out.append(part)
                continue
            rendered = self._try_source(part)
            if rendered is part:  # preserved: same object returned
                out.append(part)
            elif rendered is not None:
                out.append(str(rendered))
        return "".join(out)


def _is_splittable(value: str) -> bool:
    """Whether ``value`` is a mixed inline template safe to split.

    Block statements (``{% %}``) and comments (``{# #}``) share compile
    state across tokens, so those must be rendered whole. A string that
    is exactly one Jinja tag is also rendered whole so
    :class:`NativeEnvironment` can preserve native Python types.
    """
    if "{%" in value or "{#" in value:
        return False
    it = JINJA_PATTERN.finditer(value)
    first = next(it, None)
    if first is None:
        return False
    return next(it, None) is not None or first.span() != (0, len(value))
