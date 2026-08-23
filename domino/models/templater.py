import logging
import re
from typing import Any, ClassVar, Final

from pydantic import BaseModel, ValidationInfo
from pydantic.functional_validators import model_validator
from pydantic_core import PydanticUndefined

from ..renderer import JinjaRender

logger = logging.getLogger("domino")

# The global variable pattern will match with
#   - {{ vars('glob_variable') }}
#   - {{ some_var + vars("glob_some_id") | fmt }}
#   - "gs://{{ vars('glob_spark_log_gcs_bucket') }}/spark"
GLOB_VAR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    \{\{
      [^}]*                         # Match any characters except }
      vars
      \(
        \s?
        ['\"]
        (?P<glob>glob_\w+)          # Capture glob variable name
        ['\"]
        \s?
        (?P<default>,\s?[^}]*\))?   # Capture default
        \s?
      [^}]*                         # Allow end with filter
    }}
    """,
    re.VERBOSE,
)


class Templater(BaseModel):
    """Templater model.

    This model is a base model that will be used for any model that need to render
    Jinja template fields. It will provide a method to render the template fields
    using the provided Jinja renderer.
    """

    # The base template fields that will fix the fields that need to render Jinja
    #   template.
    base_template_fields: ClassVar[tuple[str, ...]] = ()

    # The dynamic template field class variables set
    template_fields: ClassVar[tuple[str, ...]] = ()
    template_fields_ext: ClassVar[dict[str, str]] = {}

    @classmethod
    def render_field(
        cls,
        name: str,
        data: Any,
        renderer: JinjaRender,
        *,
        is_glob_from_default: bool = False,
    ) -> Any:
        """Render a template field using the provided Jinja renderer.

        Args:
            name (str): The name of the template field.
            data (Any): The data to be rendered.
            renderer (JinjaRender): The Jinja renderer instance.
            is_glob_from_default (bool): Flag for allow to check the value of global
                variable that set from default need to set before create DAG
                object.

        Returns:
            Any: The rendered data.
        """
        data: Any = renderer.render_partial(
            data,
            template_ext=cls.template_fields_ext.get(name),
        )

        # NOTE: Check the render result cannot resolve the Global variable
        #   pattern. This case will raise a ValueError because we expect that
        #   all global variables that set default on Pydantic should be set
        #   before rendering the template field and then create Airflow's DAG object.
        if (
            isinstance(data, str)
            and (match := GLOB_VAR_PATTERN.search(data))
            and is_glob_from_default
        ):
            value: str = match.group("glob")
            logger.warning(
                "The Global variables %r are not settled yet.",
                value,
            )
            raise ValueError(
                f"The Global variables {value!r} are "
                f"not settled yet. "
                "Please make sure all settled default global variables are set "
                "before building Airflow's DAG."
            )

        return data

    @model_validator(mode="before")
    @classmethod
    def render_template_fields(
        cls,
        data: Any,
        info: ValidationInfo,
    ) -> Any:  # NOSONAR
        """Render template fields model validator.

        Args:
            data (Any): A model data that will validate.
            info (ValidationInfo): A validation info object that contains
                context data.

        Returns:
            dict | Any: A model data after render the template fields.
        """
        # Check the ``jinja_renderer`` object was passed to the Pydantic validation
        #   information before start render the Jinja template.
        if (
            cls.base_template_fields + cls.template_fields
            and isinstance(data, dict)
            and info.context
            and "jinja_renderer" in info.context
        ):
            renderer: JinjaRender = info.context["jinja_renderer"]
            for field_name in tuple(
                # Keep order of tuple of template fields
                dict.fromkeys(cls.base_template_fields + cls.template_fields)
            ):
                field_value: Any = data.get(field_name)
                is_glob_from_default: bool = False

                # Pre-set default to the value that using glob variable
                #   if the field value is None. This is to avoid rendering issues
                #   with glob variables.
                if (
                    field_value is None
                    and (field := cls.model_fields.get(field_name)) is not None
                    and (default := field.default) is not PydanticUndefined
                    and isinstance(default, str)
                    and GLOB_VAR_PATTERN.search(default)
                ):
                    logger.debug(
                        "Presetting default glob variable for %r",
                        field_name,
                    )
                    field_value: str = default
                    is_glob_from_default: bool = True

                # Only render if ``field_value`` is not None or empty
                if field_value:
                    data[field_name] = cls.render_field(
                        field_name,
                        field_value,
                        renderer,
                        is_glob_from_default=is_glob_from_default,
                    )
        return data
