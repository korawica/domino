from __future__ import annotations

import logging
from collections.abc import Callable
from re import DOTALL, VERBOSE, Pattern, compile
from typing import Any, Self, cast

from jinja2 import (
    DebugUndefined,
    Environment,
    Template,
    Undefined,
    UndefinedError,
)
from jinja2.exceptions import TemplateAssertionError
from jinja2.nativetypes import NativeEnvironment

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
    """Check whether a string contains a Jinja tag.

    Args:
        s: The string to inspect.
        pure: If ``True`` (default), the whole string must consist of
            Jinja tags for this to return ``True``. If ``False``, any
            string containing at least one tag qualifies.

    Returns:
        ``True`` if ``s`` matches the Jinja-tag criteria for the given
        ``pure`` mode, ``False`` otherwise.

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
    """An ``Undefined`` that raises on ``__str__`` instead of re-emitting.

    :class:`jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes
    ``{{ X }}``. Raising instead lets :class:`JinjaRender` catch the
    error and return the source text unchanged.
    """

    __slots__ = ()

    def __str__(self) -> str:
        """Raise ``UndefinedError`` instead of returning ``{{ var }}``.

        Raises:
            jinja2.UndefinedError: Always, via
                :meth:`~jinja2.Undefined._fail_with_undefined_error`.
        """
        self._fail_with_undefined_error()


class JinjaRender:
    """Two-mode Jinja renderer built on a native (type-preserving) environment.

    - :meth:`render` — standard Jinja. Any unresolved reference or
      syntax error propagates.
    - :meth:`render_partial` — returns the source text untouched for
      unknown macros, filters, or variables. Real
      :class:`~jinja2.TemplateSyntaxError` still propagates.

    In partial mode, mixed inline templates preserve *per expression*:
    ``"{{ pkg_var }}-{{ runtime_var }}"`` becomes
    ``"abc-{{ runtime_var }}"`` when only ``pkg_var`` is registered.
    Single-tag templates and templates containing ``{% ... %}`` blocks
    are rendered whole (all-or-nothing).

    Attributes:
        template_fields: Dict keys that :meth:`render_template` and
            :meth:`render_template_partial` will render in place.
        template_fields_excluded: Subset of ``template_fields`` to skip.
        user_defined_filters: Extra Jinja filters registered on both
            environments.
        user_defined_macros: Extra Jinja globals registered on both
            environments; also updated by :meth:`set_globals`.
        env: The strict-mode :class:`~jinja2.nativetypes.NativeEnvironment`.
        partial_env: The partial-mode environment, using
            :class:`PreserveUndefined` so unresolved names round-trip.

    Examples:
        >>> r = JinjaRender(user_defined_macros={"pkg_var": "abc"})
        >>> partial = r.render_partial("{{ pkg_var }}-{{ runtime_var }}")
        >>> partial
        'abc-{{ runtime_var }}'
        >>> _ = r.set_globals({"runtime_var": "xyz"})
        >>> r.render(partial)
        'abc-xyz'
    """

    __slots__ = (
        "template_fields",
        "template_fields_excluded",
        "user_defined_filters",
        "user_defined_macros",
        "env",
        "partial_env",
    )

    def __init__(
        self,
        *,
        template_fields: tuple[str, ...] | None = None,
        template_fields_excluded: tuple[str, ...] | None = None,
        user_defined_filters: dict[str, Callable] | None = None,
        user_defined_macros: dict[str, Callable | Any] | None = None,
    ) -> None:
        """Initialize the renderer and build its two Jinja environments.

        Args:
            template_fields: Dict keys that :meth:`render_template` and
                :meth:`render_template_partial` should render in place.
                Defaults to no fields.
            template_fields_excluded: Subset of ``template_fields`` to
                skip. Defaults to none excluded.
            user_defined_filters: Extra Jinja filters to register.
                Defaults to none.
            user_defined_macros: Extra Jinja globals to register.
                Defaults to none.
        """
        self.template_fields = template_fields or ()
        self.template_fields_excluded = template_fields_excluded or ()
        self.user_defined_filters = user_defined_filters or {}
        self.user_defined_macros = user_defined_macros or {}

        self.env: Environment = self._build_env(preserve=False)
        self.partial_env: Environment = self._build_env(preserve=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, value: Any) -> Any:
        """Recursively render ``value`` in strict (normal) mode.

        Strings, and strings nested in lists/dicts/sets/tuples, are
        rendered as Jinja templates. Any unresolved reference or
        syntax error propagates to the caller.

        Args:
            value: Any value to render. Non-string, non-collection
                values pass through unchanged.

        Returns:
            The same structure as ``value`` with contained strings
            rendered.

        Raises:
            jinja2.UndefinedError: If a template references an
                undefined name.
            jinja2.TemplateSyntaxError: If a template is malformed.
        """
        return self._walk(value, self._render_strict)

    def render_partial(self, value: Any) -> Any:
        """Recursively render ``value`` in partial mode.

        Like :meth:`render`, but unresolved macros, filters, or
        variables are left as literal Jinja text instead of raising,
        so the result can be rendered again later once more context
        is available.

        Args:
            value: Any value to render. Non-string, non-collection
                values pass through unchanged.

        Returns:
            The same structure as ``value`` with resolvable strings
            rendered and unresolved ones left verbatim.

        Raises:
            jinja2.TemplateSyntaxError: If a template is malformed
                (this always propagates, even in partial mode).
        """
        return self._walk(value, self._render_partial)

    def render_template(self, data: Any) -> Any:
        """Apply :meth:`render` to :attr:`template_fields` entries in ``data``.

        Args:
            data: A dict whose ``template_fields`` keys (excluding
                ``template_fields_excluded``) should be rendered.
                Non-dict input is passed straight to :meth:`render`.

        Returns:
            ``data`` with the selected fields rendered in place, or
            the result of :meth:`render` if ``data`` is not a dict.
        """
        return self._apply_template(data, self.render)

    def render_template_partial(self, data: Any) -> Any:
        """Apply :meth:`render_partial` to :attr:`template_fields` entries.

        Args:
            data: A dict whose ``template_fields`` keys (excluding
                ``template_fields_excluded``) should be rendered.
                Non-dict input is passed straight to
                :meth:`render_partial`.

        Returns:
            ``data`` with the selected fields rendered in place, or
            the result of :meth:`render_partial` if ``data`` is not
            a dict.
        """
        return self._apply_template(data, self.render_partial)

    def set_globals(self, values: dict[str, Any]) -> Self:
        """Update the globals of both Jinja environments in-place.

        Also merges ``values`` into :attr:`user_defined_macros` so
        the renderer's recorded configuration stays in sync.

        Args:
            values: Mapping of global names to values to register.

        Returns:
            ``self``, to allow chaining.
        """
        self.user_defined_macros.update(values)
        self.env.globals.update(values)
        self.partial_env.globals.update(values)
        return self

    # ------------------------------------------------------------------
    # Internals — environment
    # ------------------------------------------------------------------

    def _build_env(self, *, preserve: bool) -> Environment:
        """Build a Jinja environment.

        Args:
            preserve: If ``True``, use :class:`PreserveUndefined` so
                unresolved names round-trip instead of raising; used
                for :attr:`partial_env`. If ``False``, use plain
                :class:`~jinja2.Undefined`, used for :attr:`env`.

        Returns:
            A configured :class:`~jinja2.nativetypes.NativeEnvironment`
            with :attr:`user_defined_macros` and
            :attr:`user_defined_filters` registered.
        """
        env = NativeEnvironment(
            undefined=PreserveUndefined if preserve else Undefined,
            extensions=["jinja2.ext.do"],
            cache_size=0,
        )
        env.globals.update(self.user_defined_macros)
        env.filters.update(self.user_defined_filters)
        return env

    # ------------------------------------------------------------------
    # Internals — recursion
    # ------------------------------------------------------------------

    def _apply_template(
        self, data: Any, render_fn: Callable[[Any], Any]
    ) -> Any:
        """Render selected dict fields, or fall back to ``render_fn``.

        Args:
            data: The value to process. If it's not a dict, it's
                passed straight to ``render_fn``.
            render_fn: Either :meth:`render` or :meth:`render_partial`,
                applied to each selected field's value.

        Returns:
            ``data`` with :attr:`template_fields` entries (minus
            :attr:`template_fields_excluded`) rendered in place, or
            ``render_fn(data)`` if ``data`` is not a dict.
        """
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
        """Recursively render Jinja templates inside ``value``.

        Args:
            value: Any value. Strings are rendered via ``render_str``;
                lists, dicts, sets, and tuples (including NamedTuple)
                are traversed; other types pass through unchanged.
            render_str: Either :meth:`_render_strict` or
                :meth:`_render_partial`, applied to each string found.
            _seen: Internal cycle guard — object ids currently being
                walked. Callers should not pass this explicitly.

        Returns:
            A new structure mirroring ``value`` with contained strings
            rendered. Cyclic references are returned unchanged rather
            than causing infinite recursion.
        """
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
        """Render one string in strict mode.

        Args:
            value: The candidate string. Returned unchanged if it
                contains no Jinja tag.

        Returns:
            The rendered value (native Python type, thanks to
            :class:`~jinja2.nativetypes.NativeEnvironment`), or
            ``value`` unchanged if it has no Jinja tag.

        Raises:
            jinja2.UndefinedError: If the template references an
                undefined name.
            jinja2.TemplateSyntaxError: If the template is malformed.
        """
        if not is_jinja(value, pure=False):
            return value
        logger.debug("👀 Render Template: %s", value)
        return self.env.from_string(value).render()

    def _render_partial(self, value: str) -> Any:
        """Render one string in partial mode.

        Args:
            value: The candidate string. Returned unchanged if it
                contains no Jinja tag.

        Returns:
            The rendered value, ``value`` unchanged if it has no
            Jinja tag, or the original text (whole or per-expression)
            for parts that fail to resolve.

        Raises:
            jinja2.TemplateSyntaxError: If the template is malformed.
        """
        if not is_jinja(value, pure=False):
            return value
        if _is_splittable(value):
            return self._render_split(value)
        return self._try_source(value)

    def _try_source(self, source: str) -> Any:
        """Partial-render ``source`` from scratch.

        Args:
            source: A single Jinja expression or template body.

        Returns:
            The rendered value, or ``source`` unchanged if it
            references an unknown filter/test/macro or an undefined
            name.
        """
        try:
            template = self.partial_env.from_string(source)
        except TemplateAssertionError:
            # Unknown filter/test/macro at parse time. ``TemplateSyntaxError``
            # (its superclass) is *not* caught and always propagates.
            return source
        return self._try_render(template, source)

    @staticmethod
    def _try_render(template: Template, source: str) -> Any:
        """Render ``template``, falling back to ``source`` on undefined.

        Args:
            template: The parsed, ready-to-render template.
            source: The original text, returned verbatim if rendering
                hits an undefined name.

        Returns:
            The rendered value, or ``source`` if rendering raised
            ``UndefinedError`` or produced an ``Undefined`` result.
        """
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

        Args:
            value: A mixed inline template, e.g.
                ``"{{ a }}-{{ b }}"``.

        Returns:
            The concatenation of literal text and each expression's
            rendered (or, if unresolved, original) text.
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
    :class:`~jinja2.nativetypes.NativeEnvironment` can preserve native
    Python types.

    Args:
        value: A string already confirmed to contain at least one
            Jinja tag.

    Returns:
        ``True`` if ``value`` contains multiple tags, or a single tag
        mixed with literal text; ``False`` if it should be rendered
        whole.
    """
    if "{%" in value or "{#" in value:
        return False
    it = JINJA_PATTERN.finditer(value)
    first = next(it, None)
    if first is None:
        return False
    return next(it, None) is not None or first.span() != (0, len(value))
