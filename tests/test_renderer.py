import pytest
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from domino.renderer import JinjaRender


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
    ],
)
def test_render_debug_preserves_unresolved(template_str, expected):
    renderer = JinjaRender(template_fields=("key",))
    assert renderer.render_debug(template_str) == expected


def test_render_debug_uses_registered_context():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    assert renderer.render_debug("{{ pkg_var }}-{{ runtime_var }}") == (
        "abc-{{ runtime_var }}"
    )


def test_render_debug_raises_on_syntax_error():
    renderer = JinjaRender()
    with pytest.raises(TemplateSyntaxError):
        renderer.render_debug("{{ 1 + }}")


def test_render_normal_raises_on_undefined():
    renderer = JinjaRender()
    with pytest.raises(UndefinedError):
        renderer.render("{{ vars('test') }}")


def test_render_normal_resolves_registered_macros():
    renderer = JinjaRender(user_defined_macros={"greet": "hi"})
    assert renderer.render("{{ greet }}") == "hi"


def test_two_layer_flow():
    renderer = JinjaRender(user_defined_macros={"pkg_var": "abc"})
    partial = renderer.render_debug("{{ pkg_var }}-{{ runtime_var }}")

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


def test_render_template_debug_preserves_unknowns():
    renderer = JinjaRender(
        template_fields=("a", "b"),
        user_defined_macros={"pkg_var": "abc"},
    )
    data = {"a": "{{ pkg_var }}", "b": "{{ runtime_var }}"}
    result = renderer.render_template_debug(data)
    assert result == {"a": "abc", "b": "{{ runtime_var }}"}
