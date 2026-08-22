from collections import namedtuple

import pytest
from jinja2 import UndefinedError
from jinja2.exceptions import TemplateSyntaxError

from domino.renderer import JinjaRender, PreserveUndefined, is_jinja
from domino.utils import DotDict

# ---------------------------------------------------------------------------
# is_jinja
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "pure", "expected"),
    [
        ("{{ x }}", True, True),
        ("{% if x %}{% endif %}", True, True),
        ("{# c #}", True, True),
        ("hello {{ x }}", True, False),
        ("plain text", True, False),
        ("", True, False),
        ("hello {{ x }}", False, True),
        ("plain text", False, False),
    ],
)
def test_is_jinja(value, pure, expected):
    assert is_jinja(value, pure=pure) is expected


# ---------------------------------------------------------------------------
# PreserveUndefined
# ---------------------------------------------------------------------------


def test_preserve_undefined_str_raises():
    u = PreserveUndefined(name="missing")
    with pytest.raises(UndefinedError):
        str(u)


# ---------------------------------------------------------------------------
# render_partial — parametrized behaviors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("template_str", "expected"),
    [
        # Unresolved single-whole tags → preserved verbatim.
        ("{{ test }}", "{{ test }}"),
        ("{{ test | upper }}", "{{ test | upper }}"),
        ("{{ vars('test') }}", "{{ vars('test') }}"),
        (
            "{{ logical_date | fmt('%Y-%m-%d') }}",
            "{{ logical_date | fmt('%Y-%m-%d') }}",
        ),
        (
            "{{'512m' if ti.try_number == 1 else '1024m'}}",
            "{{'512m' if ti.try_number == 1 else '1024m'}}",
        ),
        ("{{ a.attr }}", "{{ a.attr }}"),
        ("{{ d['key'] }}", "{{ d['key'] }}"),
        ("{{ a[0] }}", "{{ a[0] }}"),
        ("{{ macro_call(1, 2) }}", "{{ macro_call(1, 2) }}"),
        ("{{ test | unknown_filter }}", "{{ test | unknown_filter }}"),
        ("{{ test is divisibleby(3) }}", "{{ test is divisibleby(3) }}"),
        ("{{ a or b }}", "{{ a or b }}"),
        # Mixed inline templates preserve per-expression.
        ("{{ a }}-{{ b }}", "{{ a }}-{{ b }}"),
        ("{{ a }} and {{ b }} and {{ c }}", "{{ a }} and {{ b }} and {{ c }}"),
        # Whole-only (block/comment) templates.
        ("{% for item in items %}{% endfor %}", None),
        ("{% set some_var = 'some_var' %}", None),
        ("{% set some_int = 19 %}", None),
        (
            "{% if loop.index is divisibleby(3) %}{% endif %}",
            "{% if loop.index is divisibleby(3) %}{% endif %}",
        ),
        ("{% raw %}", None),
        ("{%- for item in items -%}{%- endfor -%}", None),
        ("{# just a comment #}", None),
        # Resolvable single-whole tags → native Python types.
        ("{{ 'Update' if test else 'Continue' }}", "Continue"),
        ("{{ test and vars('demo') or 'Continue' }}", "Continue"),
        ("{{ 1 + 2 }}", 3),
        ("{{ 1 == 1 }}", True),
        ("{{ 'hello' }}", "hello"),
        ("{{ [1, 2, 3] | length }}", 3),
        # Non-Jinja strings pass through unchanged.
        ("% for item in items", "% for item in items"),
        ("", ""),
        ("   ", "   "),
        ("plain text no jinja", "plain text no jinja"),
        # {% raw %} — the block bypasses Jinja parsing so its
        # contents survive as literal text. Historically this
        # tripped ``NativeEnvironment.literal_eval`` (e.g. ``{{ 1 }}``
        # parses as an unhashable set-of-set); the plain-env
        # fallback covers all these cases.
        ("{% raw %}{{ 1 }}{% endraw %}", "{{ 1 }}"),
        ("{% raw %}{{ x }}{% endraw %}", "{{ x }}"),
        ("{% raw %}some text{% endraw %}", "some text"),
        (
            "{% raw %}{{ a }} and {{ b }}{% endraw %}",
            "{{ a }} and {{ b }}",
        ),
        (
            "{% raw %}{% for i in items %}{{ i }}{% endfor %}{% endraw %}",
            "{% for i in items %}{{ i }}{% endfor %}",
        ),
        # {% raw %} outputs that would trip literal_eval with each
        # of the three unhashable-container flavors.
        ("{% raw %}{ {1} }{% endraw %}", "{ {1} }"),  # set of set
        ("{% raw %}{ {'a': 1} }{% endraw %}", "{ {'a': 1} }"),  # set of dict
        ("{% raw %}{ [1, 2] }{% endraw %}", "{ [1, 2] }"),  # set of list
        ("{% raw %}{{ }}{% endraw %}", "{{ }}"),  # set of empty dict
    ],
)
def test_render_partial_preserves_unresolved(template_str, expected):
    renderer = JinjaRender(template_fields=("key",))
    assert renderer.render_partial(template_str) == expected


def test_render_partial_empty_raw_returns_none():
    # ``NativeEnvironment`` collapses empty output to ``None``.
    # Documented here so the behavior is intentional.
    assert JinjaRender().render_partial("{% raw %}{% endraw %}") is None


# ---------------------------------------------------------------------------
# NativeEnvironment literal_eval fallback — non-raw sources that also
# render to strings ast.literal_eval mangles into unhashable containers.
#
# NOTE: We cannot write ``{{ '{{ x }}' }}`` directly — Jinja's lexer
# closes the outer expression on the first ``}}`` it sees, regardless
# of quoting. Instead we exercise the same code path via macros /
# string concatenation whose *result* is a template-shaped string.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("template_str", "expected"),
    [
        # Expression returns a string that literal_eval reads as
        # an unhashable container.
        ("{{ '{ {1} }' }}", "{ {1} }"),
        ("{{ '{ [1, 2] }' }}", "{ [1, 2] }"),
        ("{{ '{ {\"a\": 1} }' }}", '{ {"a": 1} }'),
        # String concat producing a template-shaped literal.
        ("{{ '{' ~ '{ x ' ~ '}' }}", "{{ x }"),
    ],
)
def test_render_partial_native_typeerror_fallback(template_str, expected):
    assert JinjaRender().render_partial(template_str) == expected


def test_render_partial_macro_returning_template_text():
    # A macro whose value is a template-shaped string must not
    # trip literal_eval, and must not be re-parsed as a template.
    renderer = JinjaRender(user_defined_macros={"tmpl": "{{ inner }}"})
    assert renderer.render_partial("{{ tmpl }}") == "{{ inner }}"


def test_render_partial_split_expression_native_typeerror():
    # The splittable branch renders each expression individually;
    # the TypeError fallback must apply per-expression too.
    renderer = JinjaRender(user_defined_macros={"tmpl": "{{ inner }}"})
    assert renderer.render_partial("prefix {{ tmpl }} suffix") == (
        "prefix {{ inner }} suffix"
    )


def test_render_partial_raw_with_surrounding_text_is_whole_only():
    # {% raw %} contains '{%' so the whole string is treated as
    # one block — surrounding literal text survives with it.
    renderer = JinjaRender()
    assert (
        renderer.render_partial("before {% raw %}{{ x }}{% endraw %} after")
        == "before {{ x }} after"
    )


def test_render_partial_uses_registered_context():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    assert renderer.render_partial("{{ pkg_var }}-{{ runtime_var }}") == (
        "abc-{{ runtime_var }}"
    )


def test_render_partial_raises_on_syntax_error():
    renderer = JinjaRender()
    with pytest.raises(TemplateSyntaxError):
        renderer.render_partial("{{ 1 + }}")


def test_render_partial_single_tag_with_literal_splits():
    renderer = JinjaRender(user_defined_macros={"x": "1"})
    # Single tag but not covering the whole string → splittable branch.
    assert renderer.render_partial("prefix {{ x }}") == "prefix 1"


def test_render_partial_split_skips_none_value():
    renderer = JinjaRender()
    # `{{ none }}` renders to None; the split loop drops it.
    assert renderer.render_partial("{{ none }}-{{ runtime_var }}") == (
        "-{{ runtime_var }}"
    )


def test_render_partial_registered_user_filter():
    renderer = JinjaRender(user_defined_filters={"double": lambda x: x * 2})
    assert renderer.render_partial("{{ 3 | double }}") == 6


# ---------------------------------------------------------------------------
# render (strict)
# ---------------------------------------------------------------------------


def test_render_strict_raises_on_undefined():
    renderer = JinjaRender()
    with pytest.raises(UndefinedError):
        renderer.render("{{ vars('test') }}")


def test_render_strict_resolves_registered_macros():
    renderer = JinjaRender(user_defined_macros={"greet": "hi"})
    assert renderer.render("{{ greet }}") == "hi"


def test_render_strict_returns_plain_text_unchanged():
    assert JinjaRender().render("plain text") == "plain text"


@pytest.mark.parametrize(
    ("template_str", "expected"),
    [
        # Strict mode must also survive NativeEnvironment's
        # literal_eval TypeError on legitimately rendered text.
        ("{% raw %}{{ 1 }}{% endraw %}", "{{ 1 }}"),
        ("{% raw %}{{ }}{% endraw %}", "{{ }}"),
        ("{% raw %}{ [1, 2] }{% endraw %}", "{ [1, 2] }"),
        ("{{ '{ {1} }' }}", "{ {1} }"),
    ],
)
def test_render_strict_native_typeerror_fallback(template_str, expected):
    assert JinjaRender().render(template_str) == expected


# ---------------------------------------------------------------------------
# Two-step flow (partial → real)
# ---------------------------------------------------------------------------


def test_two_step_flow_preserves_raw_content_across_steps():
    # {% raw %} content should survive step 1 as literal text and
    # step 2 must NOT re-parse it as a template (raw is gone by
    # then, so the string is just plain text with braces).
    renderer = JinjaRender()
    partial = renderer.render_partial("{% raw %}{{ x }}{% endraw %}")
    assert partial == "{{ x }}"

    # Step 2: strict render on the partial output. There is no
    # longer any {% raw %} guard, so `{{ x }}` becomes a real
    # template — with `x` registered it now resolves.
    renderer.set_globals({"x": "value"})
    assert renderer.render(partial) == "value"


# ---------------------------------------------------------------------------
# Two-step flow (partial → real)
# ---------------------------------------------------------------------------


def test_two_step_flow():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    partial = renderer.render_partial("{{ pkg_var }}-{{ runtime_var }}")

    result = renderer.set_globals({"runtime_var": "xyz"}).render(partial)
    assert result == "abc-xyz"


def test_set_globals_returns_self_and_syncs_macros():
    renderer = JinjaRender()
    assert renderer.set_globals({"k": 1}) is renderer
    assert renderer.user_defined_macros["k"] == 1
    assert renderer.env.globals["k"] == 1
    assert renderer.string_env.globals["k"] == 1
    assert renderer.partial_env.globals["k"] == 1
    assert renderer.partial_string_env.globals["k"] == 1


# ---------------------------------------------------------------------------
# render_template / render_template_partial
# ---------------------------------------------------------------------------


def test_render_template_only_touches_template_fields():
    renderer = JinjaRender(
        template_fields=("rendered",),
        user_defined_macros={"pkg_var": "abc"},
    )
    data = {"rendered": "{{ pkg_var }}", "skipped": "{{ pkg_var }}"}
    result = renderer.render_template(data)
    assert result == {"rendered": "abc", "skipped": "{{ pkg_var }}"}


def test_render_template_partial_preserves_unknowns():
    renderer = JinjaRender(
        template_fields=("a", "b"),
        user_defined_macros={"pkg_var": "abc"},
    )
    data = {"a": "{{ pkg_var }}", "b": "{{ runtime_var }}"}
    result = renderer.render_template_partial(data)
    assert result == {"a": "abc", "b": "{{ runtime_var }}"}


def test_render_template_non_dict_falls_back_to_render():
    renderer = JinjaRender(template_fields=("a",))
    assert renderer.render_template("{{ 1 + 1 }}") == 2


def test_render_template_partial_non_dict_falls_back():
    renderer = JinjaRender(template_fields=("a",))
    assert renderer.render_template_partial("{{ x }}") == "{{ x }}"


def test_render_template_skips_missing_and_excluded_fields():
    renderer = JinjaRender(
        template_fields=("missing", "excluded", "kept"),
        template_fields_excluded=("excluded",),
    )
    data = {"excluded": "{{ 1 }}", "kept": "{{ 2 }}"}
    result = renderer.render_template(data)
    assert result == {"excluded": "{{ 1 }}", "kept": 2}


def test_render_template_partial_skips_missing_and_excluded_fields():
    renderer = JinjaRender(
        template_fields=("missing", "excluded", "kept"),
        template_fields_excluded=("excluded",),
        user_defined_macros={"pkg_var": "abc"},
    )
    data = {"excluded": "{{ pkg_var }}", "kept": "{{ pkg_var }}"}
    result = renderer.render_template_partial(data)
    assert result == {"excluded": "{{ pkg_var }}", "kept": "abc"}


# ---------------------------------------------------------------------------
# _walk — collection traversal
# ---------------------------------------------------------------------------


def test_walk_handles_nested_collections():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    Point = namedtuple("Point", ["x", "y"])
    value = {
        "list": ["{{ pkg_var }}", 1],
        "set": {"{{ pkg_var }}"},
        "tuple": ("{{ pkg_var }}",),
        "named": Point("{{ pkg_var }}", "{{ pkg_var }}"),
        "int": 42,
        "none": None,
    }
    result = renderer.render(value)
    assert result["list"] == ["abc", 1]
    assert result["set"] == {"abc"}
    assert result["tuple"] == ("abc",)
    assert result["named"] == Point("abc", "abc")
    assert result["int"] == 42
    assert result["none"] is None


def test_walk_cycle_guard_returns_same_object():
    renderer = JinjaRender()
    cyclic: list = ["{{ 1 }}"]
    cyclic.append(cyclic)
    result = renderer.render(cyclic)
    assert result[0] == 1
    assert result[1] is cyclic  # cycle guard returns the original object


def test_walk_returns_unknown_type_untouched():
    class Opaque:
        pass

    obj = Opaque()
    assert JinjaRender().render(obj) is obj


@pytest.mark.parametrize(
    ("template_str", "expected"),
    (
        (
            """{% for item in items %}
            fullpath: {{ vars("bucket") }}/{{ item }}
            {% endfor %}
            """,
            """""",
        )
    ),
)
def test_render_template_partial_with_full_context(template_str, expected):
    _ = DotDict(
        {
            "bucket": "my-bucket",
            "items": ["file1.txt", "file2.txt"],
        }
    )
