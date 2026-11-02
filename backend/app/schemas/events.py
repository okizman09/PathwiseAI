from typing import Literal

from pydantic import BaseModel


class EventCreateRequest(BaseModel):
    kind: Literal["prompt_copied"]
    workflow_id: int | None = None
    step_id: str | None = None
