from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Label(BaseModel):
    """Label model."""

    model_config = ConfigDict(extra="allow")

    team: str | None = Field(
        default=None,
        description="The team responsible for the task.",
    )
    system: str | None = Field(
        default=None,
        description="The system responsible for the task.",
    )
    priority: str | None = Field(
        default=None,
        description="The priority of the task.",
    )

    def merge_label(self, other: Label) -> Label:
        """Merge two Label model.

        Args
            other (Label): Another Label model to merge with the current one.

        Returns:
            Label: A new Label model that is the result of merging the current
                Label model with the other Label model.
        """
        return Label(
            **(
                self.model_dump(exclude_none=True)
                | other.model_dump(exclude_none=True)
            )
        )

    def make_tags(self) -> set[str]:
        """Make tags from labels."""
        return {
            f"{key}:{str(value)}"
            for key, value in (
                self.model_dump(exclude_none=True) | self.__pydantic_extra__
            ).items()
        }
