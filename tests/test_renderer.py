from collections import namedtuple

import pytest
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from domino.renderer import JinjaRender, _is_splittable, is_jinja


@pytest.mark.parametrize(
    ("template_str", "expected"),
    [
        ("{{ test }}", "{{ test }}"),
        ("{{ test | upper }}", "{{ test | upper }}"),
        (
            "{{ date | days_ago(days=1) | upper }}",
            "{{ date | days_ago(days=1) | upper }}",
        ),
        ("{{ vars('test') }}", "{{ vars('test') }}"),
        (
            "{{ logical_date | fmt('%Y-%m-%d') }}",
            "{{ logical_date | fmt('%Y-%m-%d') }}",
        ),
        (
            "{{ logical_date | fmt('%Y-%m-%d') }}",
            "{{ logical_date | fmt('%Y-%m-%d') }}",
        ),
        (
            "{{'512m' if ti.try_number == 1 else '1024m'}}",
            "{{'512m' if ti.try_number == 1 else '1024m'}}",
        ),
        ("% for item in items", "% for item in items"),
        ("{% for item in items %}{% endfor %}", None),
        ("{% set some_var = 'some_var' %}", None),
        ("{% set some_int = 19 %}", None),
        (
            "{% if loop.index is divisibleby(3) %}{% endif %}",
            "{% if loop.index is divisibleby(3) %}{% endif %}",
        ),
        ("{% raw %}", None),
        ("{{ 'Update' if test else 'Continue' }}", "Continue"),
        ("{{ test and vars('demo') or 'Continue' }}", "Continue"),
        ("{# just a comment #}", None),
        ("{{ a }}-{{ b }}", "{{ a }}-{{ b }}"),
        ("{{ a }} and {{ b }} and {{ c }}", "{{ a }} and {{ b }} and {{ c }}"),
        ("{{ a.attr }}", "{{ a.attr }}"),
        ("{{ d['key'] }}", "{{ d['key'] }}"),
        ("{{ a[0] }}", "{{ a[0] }}"),
        ("{{ macro_call(1, 2) }}", "{{ macro_call(1, 2) }}"),
        ("{{ test | unknown_filter }}", "{{ test | unknown_filter }}"),
        ("{{ test is divisibleby(3) }}", "{{ test is divisibleby(3) }}"),
        ("{{ a or b }}", "{{ a or b }}"),
        ("{%- for item in items -%}{%- endfor -%}", None),
        ("", ""),
        ("   ", "   "),
        ("plain text no jinja", "plain text no jinja"),
        ("{{ 1 + 2 }}", 3),
        ("{{ 1 == 1 }}", True),
        ("{{ 'hello' }}", "hello"),
        ("{{ [1, 2, 3] | length }}", 3),
    ],
)
def test_render_partial_preserves_unresolved(template_str, expected):
    renderer = JinjaRender(template_fields=("key",))
    assert renderer.render_partial(template_str) == expected


def test_render_partial_uses_registered_context():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    assert renderer.render_partial("{{ pkg_var }}-{{ runtime_var }}") == (
        "abc-{{ runtime_var }}"
    )


def test_render_partial_raises_on_syntax_error():
    renderer = JinjaRender()
    with pytest.raises(TemplateSyntaxError):
        renderer.render_partial("{{ 1 + }}")


def test_render_normal_raises_on_undefined():
    renderer = JinjaRender()
    with pytest.raises(UndefinedError):
        renderer.render("{{ vars('test') }}")


def test_render_normal_resolves_registered_macros():
    renderer = JinjaRender(user_defined_macros={"greet": "hi"})
    assert renderer.render("{{ greet }}") == "hi"


def test_two_layer_flow():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    partial = renderer.render_partial("{{ pkg_var }}-{{ runtime_var }}")

    renderer.set_globals({"runtime_var": "xyz"})
    assert renderer.render(partial) == "abc-xyz"


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


def test_is_jinja_pure_true():
    assert is_jinja("{{ x }}") is True
    assert is_jinja("hello {{ x }}") is False


def test_render_template_non_dict_falls_back_to_render():
    renderer = JinjaRender(template_fields=("a",))
    assert renderer.render_template("{{ 1 + 1 }}") == 2


def test_render_template_skips_missing_and_excluded_fields():
    renderer = JinjaRender(
        template_fields=("missing", "excluded", "kept"),
        template_fields_excluded=("excluded",),
    )
    data = {"excluded": "{{ 1 }}", "kept": "{{ 2 }}"}
    result = renderer.render_template(data)
    assert result == {"excluded": "{{ 1 }}", "kept": 2}


def test_render_strict_returns_plain_text_unchanged():
    renderer = JinjaRender()
    assert renderer.render("plain text") == "plain text"


def test_walk_handles_nested_collections():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    Point = namedtuple("Point", ["x", "y"])
    value = {
        "list": ["{{ pkg_var }}", 1],
        "set": {"{{ pkg_var }}"},
        "tuple": ("{{ pkg_var }}",),
        "named": Point("{{ pkg_var }}", "{{ pkg_var }}"),
    }
    result = renderer.render(value)
    assert result["list"] == ["abc", 1]
    assert result["set"] == {"abc"}
    assert result["tuple"] == ("abc",)
    assert result["named"] == Point("abc", "abc")


def test_walk_cycle_guard_returns_same_object():
    renderer = JinjaRender()
    cyclic: list = ["{{ 1 }}"]
    cyclic.append(cyclic)
    result = renderer.render(cyclic)
    assert result[0] == 1
    assert result[1] is cyclic  # cycle guard returns the original object


def test_render_split_skips_none_valued_part():
    renderer = JinjaRender()
    result = renderer.render_partial("{{ none }}-{{ runtime_var }}")
    assert result == "-{{ runtime_var }}"


def test_is_splittable_no_match_returns_false():
    assert _is_splittable("plain text") is False
