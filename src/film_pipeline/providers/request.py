"""Provider-neutral generation request (docs/production/PROVIDER_INDEPENDENCE.md section 3 item 1).

Shared code speaks in shots, frames, references, seconds and money; only an adapter turns a ``GenerationRequest`` into a
provider's own vocabulary (Flow argv, MiniMax ``content[]``, an OpenAI-style ``/v1/videos`` body).
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ..core import ContractModel

Tier = Literal["TEST", "FINAL"]
AudioMode = Literal["NATIVE_DIALOGUE", "SILENT", "AMBIENT"]
# what a reference image/clip stands for; adapters map these onto their own roles
ReferenceRole = Literal["character", "look", "voice", "location", "prop"]


class FrameRef(ContractModel):
    path: str = Field(min_length=1)
    sha256: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")  # "" = file missing at build time


class ReferenceRef(ContractModel):
    role: ReferenceRole
    path: str = Field(min_length=1)
    sha256: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")
    subject: str = ""  # e.g. the character name


class GenerationRequest(ContractModel):
    film_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    take_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duration_s: int = Field(gt=0)
    aspect: str = "16:9"
    tier: Tier = "TEST"
    first_frame: FrameRef | None = None
    last_frame: FrameRef | None = None
    references: list[ReferenceRef] = Field(default_factory=list)
    audio_mode: AudioMode = "SILENT"
    output: str = Field(min_length=1)  # where the adapter must write the clip (never overwritten)

    @model_validator(mode="after")
    def _last_needs_first(self) -> "GenerationRequest":
        if self.last_frame is not None and self.first_frame is None:
            raise ValueError("a last frame needs a first frame")
        return self

    @property
    def frame_roles(self) -> list[str]:
        return [r for r, f in (("first_frame", self.first_frame), ("last_frame", self.last_frame)) if f is not None]

    @property
    def output_path(self) -> Path:
        return Path(self.output)
