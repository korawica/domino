import json
from pathlib import Path
from typing import Annotated, Any, Union

from pydantic import Field, TypeAdapter


def get_model_adapter() -> TypeAdapter:
    from domino.models.dag import Dag
    from domino.models.variable import Variable

    model = Annotated[
        Union[Dag, Variable],
        Field(
            discriminator="type",
            description="A type of the model.",
        ),
    ]

    return TypeAdapter(model)


def json_schema(output_path: Path) -> dict[str, Any]:
    """Get JSON Schema for Domino Models."""
    schema = get_model_adapter().json_schema(by_alias=True)

    with open(output_path, mode="w", encoding="utf-8") as f:
        f.write(json.dumps(schema))

    return schema
