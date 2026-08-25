from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from domino.renderer import JinjaRenderer
from domino.utils.dotdict import DotDict


@pytest.fixture(scope="function")
def renderer():
    dotdict = DotDict(
        {
            "bucket": "some-bucket",
            "project": "some-project",
            "payloads": [{"id": 1}, {"id": 2}],
        }
    )
    return JinjaRenderer(user_defined_macros={"vars": dotdict.get_raise})


@pytest.mark.parametrize(
    ("template_str", "expected_output"),
    [
        # ----------------------------------------------------------------------
        # Resolvable literals - should evaluate
        # ----------------------------------------------------------------------
        ("{{ 1 }}", 1),
        ("{{ 'hello' }}", "hello"),
        ("{{ 1 + 2 }}", 3),
        ("{{ 10 * 5 }}", 50),
        ("{{ [1, 2, 3] | length }}", 3),
        # ----------------------------------------------------------------------
        # Resolvable variables - should evaluate
        # ----------------------------------------------------------------------
        ("{{ vars('bucket') }}", "some-bucket"),
        ("{{ vars('project') }}", "some-project"),
        ("{{ vars('payloads')[0].id }}", 1),
        ("{{ vars('payloads')[1].id }}", 2),
        ("{{ vars('payloads') | length }}", 2),
        ("{{ vars('not_exists', None) }}", None),
        ("{{ vars('not_exists?.nested_key') }}", None),
        (
            dedent(
                """
                {%- if vars('bucket') == 'some-bucket' -%}
                Success: Bucket is some-bucket
                {%- endif -%}
                """.strip("\n")
            ),
            "Success: Bucket is some-bucket",
        ),
        (
            dedent(
                """
                {% for payload in vars('payloads') -%}
                Payload ID: {{ payload.id }}
                {% endfor %}
                """.strip("\n")
            ),
            dedent(
                """
                Payload ID: 1
                Payload ID: 2
                """.strip("\n")
            ),
        ),
        # ----------------------------------------------------------------------
        # Simple expressions - undefined variables should be preserved
        # ----------------------------------------------------------------------
        ("Hello, {{ name }}!", "Hello, {{ name }}!"),
        ("Value: {{ x }}", "Value: {{ x }}"),
        # ----------------------------------------------------------------------
        # Arithmetic with undefined - should be preserved
        # ----------------------------------------------------------------------
        (
            "The sum of {{ a }} and {{ b }} is {{ a + b }}.",
            "The sum of {{ a }} and {{ b }} is {{ a + b }}.",
        ),
        ("{{ x + 2 + 1 }}", "{{ x + 2 + 1 }}"),
        ("{{ x + y + z }}", "{{ x + y + z }}"),
        ("{{ count * 2 }}", "{{ count * 2 }}"),
        # ----------------------------------------------------------------------
        # If statements - undefined conditions should preserve the whole block
        # ----------------------------------------------------------------------
        (
            dedent(
                """
                {% if condition %}
                Condition is true
                {% else %}
                Condition is false
                {% endif %}
                """.strip("\n")
            ),
            dedent(
                """
                {% if condition %}
                Condition is true
                {% else %}
                Condition is false
                {% endif %}
                """.strip("\n")
            ),
        ),
        (
            "{% if enabled %}enabled{% endif %}",
            "{% if enabled %}enabled{% endif %}",
        ),
        (
            "{% if count > 0 %}positive{% else %}non-positive{% endif %}",
            "{% if count > 0 %}positive{% else %}non-positive{% endif %}",
        ),
        (
            "{% if a and b %}both true{% endif %}",
            "{% if a and b %}both true{% endif %}",
        ),
        (
            "{% if a or b %}at least one{% endif %}",
            "{% if a or b %}at least one{% endif %}",
        ),
        # ----------------------------------------------------------------------
        # If with literal True - should evaluate
        # ----------------------------------------------------------------------
        ("{% if True %}always{% endif %}", "always"),
        ("{% if 1 %}one{% endif %}", "one"),
        # ----------------------------------------------------------------------
        # For loops - undefined iterables should preserve the whole block
        # ----------------------------------------------------------------------
        (
            dedent(
                """
                {% for item in items %}
                    Item: {{ item }}
                {% endfor %}
                """.strip("\n")
            ),
            dedent(
                """
                {% for item in items %}
                    Item: {{ item }}
                {% endfor %}
                """.strip("\n")
            ),
        ),
        (
            "{% for i in numbers %}{{ i }}{% endfor %}",
            "{% for i in numbers %}{{ i }}{% endfor %}",
        ),
        # ----------------------------------------------------------------------
        # For with literal list - should evaluate (NativeEnvironment returns int)
        # ----------------------------------------------------------------------
        ("{% for i in [1, 2, 3] %}{{ i }}{% endfor %}", 123),
        # ----------------------------------------------------------------------
        # Set statements - undefined variables should preserve the statement
        # ----------------------------------------------------------------------
        ("{% set x = value %}{{ x }}", "{% set x = value %}{{ x }}"),
        # ----------------------------------------------------------------------
        # Filters on undefined - should be preserved
        # ----------------------------------------------------------------------
        ("{{ name | upper }}", "{{ name | upper }}"),
        ("{{ text | trim }}", "{{ text | trim }}"),
        # ----------------------------------------------------------------------
        # Filters with fallback - should use fallback value
        # ----------------------------------------------------------------------
        ("{{ value | default('none') }}", "none"),
        ("{{ items | length }}", 0),
        # ----------------------------------------------------------------------
        # Attribute/item access on undefined - should be preserved
        # ----------------------------------------------------------------------
        ("{{ obj.attr }}", "{{ obj.attr }}"),
        ("{{ user.name }}", "{{ user.name }}"),
        ("{{ items[0] }}", "{{ items[0] }}"),
        ("{{ data['key'] }}", "{{ data['key'] }}"),
        # ----------------------------------------------------------------------
        # Logical operators with undefined - should be preserved
        # ----------------------------------------------------------------------
        ("{{ a or b }}", "{{ a or b }}"),
        ("{{ a and b }}", "{{ a and b }}"),
        ("{{ not flag }}", "{{ not flag }}"),
        # ----------------------------------------------------------------------
        # Ternary expressions with undefined - should be preserved
        # ----------------------------------------------------------------------
        ("{{ 'yes' if flag else 'no' }}", "{{ 'yes' if flag else 'no' }}"),
        (
            "{{ value if defined else 'default' }}",
            "{{ value if defined else 'default' }}",
        ),
        # ----------------------------------------------------------------------
        # Multiple undefined expressions - each should be preserved
        # ----------------------------------------------------------------------
        ("{{ a }} and {{ b }}", "{{ a }} and {{ b }}"),
        ("{{ x }} - {{ y }} - {{ z }}", "{{ x }} - {{ y }} - {{ z }}"),
        # ----------------------------------------------------------------------
        # Nested blocks - should preserve entire structure
        # ----------------------------------------------------------------------
        (
            "{% if outer %}{% if inner %}nested{% endif %}{% endif %}",
            "{% if outer %}{% if inner %}nested{% endif %}{% endif %}",
        ),
        (
            "{% for row in rows %}{% for cell in row %}{{ cell }}{% endfor %}{% endfor %}",
            "{% for row in rows %}{% for cell in row %}{{ cell }}{% endfor %}{% endfor %}",
        ),
        # ----------------------------------------------------------------------
        # Mixed: defined and undefined - defined parts should resolve
        # ----------------------------------------------------------------------
        (
            "{{ vars('bucket') }} - {{ undefined }}",
            "some-bucket - {{ undefined }}",
        ),
        (
            "prefix {{ vars('project') }} suffix {{ x }}",
            "prefix some-project suffix {{ x }}",
        ),
        (
            dedent(
                """
                {{ vars('bucket') }} and {{ undefined }}
                {%- if vars('bucket') == 'some-bucket' -%}
                Success: Bucket is some-bucket
                {%- endif -%}
                """.strip("\n")
            ),
            dedent(
                """
                {{ vars('bucket') }} and {{ undefined }}
                {%- if vars('bucket') == 'some-bucket' -%}
                Success: Bucket is some-bucket
                {%- endif -%}
                """.strip("\n")
            ),
        ),
        # ----------------------------------------------------------------------
        # Raw blocks - should pass through content unchanged
        # ----------------------------------------------------------------------
        ("{% raw %}{{ x }}{% endraw %}", "{{ x }}"),
        ("{% raw %}{% if a %}{% endif %}{% endraw %}", "{% if a %}{% endif %}"),
        # ----------------------------------------------------------------------
        # Non-Jinja strings - should pass through unchanged
        # ----------------------------------------------------------------------
        ("plain text", "plain text"),
        ("no jinja here", "no jinja here"),
        ("", ""),
    ],
)
def test_renderer_render(
    renderer: JinjaRenderer,
    template_str: str,
    expected_output: Any,
):
    assert renderer.render(template_str) == expected_output


def test_renderer_file_render(tmp_path: Path):
    template_file = tmp_path / "template.j2"
    template_file.write_text(
        dedent(
            """
            Hello, {{ vars('name', 'World') }}!
            {% if vars('show_message', False) %}
            This is a message.
            {% endif %}
            """
        )
    )

    # Create a renderer with variables
    dotdict = DotDict({"name": "Alice", "show_message": True})
    renderer = JinjaRenderer(
        user_defined_macros={"vars": dotdict.get_raise},
        template_searchpath=(tmp_path,),
    )

    # Render the template file
    rendered_content = renderer.render("template.j2", template_ext=("j2",))

    # Expected output
    expected_output = dedent(
        """
        Hello, Alice!

        This is a message.
        """
    ).strip()

    assert rendered_content.strip() == expected_output
