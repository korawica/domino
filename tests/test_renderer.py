import pytest

from domino.renderer import JinjaRenderer
from domino.utils.dotdict import DotDict


@pytest.fixture(scope="function")
def renderer():
    dotdict = DotDict(
        {
            "bucket": "some-bucket",
            "project": "some-project",
        }
    )
    return JinjaRenderer(user_defined_macros={"vars": dotdict.get_raise})


@pytest.mark.parametrize(
    ("template_str", "expected_output"),
    [
        ("Hello, {{ name }}!", "Hello, {{ name }}!"),
        (
            "The sum of {{ a }} and {{ b }} is {{ a + b }}.",
            "The sum of {{ a }} and {{ b }} is {{ a + b }}.",
        ),
        (
            "{% if condition %}Condition is true{% else %}Condition is false{% endif %}",
            "{% if condition %}Condition is true{% else %}Condition is false{% endif %}",
        ),
    ],
)
def test_renderer(renderer, template_str, expected_output):
    assert renderer.render(template_str) == expected_output
