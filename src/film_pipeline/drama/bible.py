"""Drama P0 #5 — character reference images bound to each generation.

Every character gets an approved front / three-quarter / profile set. The
set is hash-pinned: a file edited after approval no longer verifies. Only
virtual (synthetic) people are allowed — never a photo of a real person.

``attachment_plan`` is the ordered list the dispatcher uploads with the
scene; ``reference_strategy_for`` returns the matching prompt-side
``ReferenceStrategy`` so the prompt never claims references that were not
attached.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from ..narrative.prompting import ReferenceStrategy

RefAngle = Literal["FRONT", "THREE_QUARTER", "PROFILE"]
REQUIRED_ANGLES: tuple[RefAngle, ...] = ("FRONT", "THREE_QUARTER", "PROFILE")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReferenceImage(ContractModel):
    angle: RefAngle
    path: str                 # relative to the bible root
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: bool = False
    approved_by: str = ""
    approved_at: str = ""


class CharacterReferenceSet(ContractModel):
    character_id: str
    name: str
    synthetic_person: bool = False   # attested: generated, not a real person
    look_id: str = ""                # wardrobe/hair look this set shows
    images: list[ReferenceImage] = Field(default_factory=list)

    def image(self, angle: RefAngle) -> ReferenceImage | None:
        return next((i for i in self.images if i.angle == angle), None)

    def problems(self, root: Path) -> list[str]:
        """Empty list == usable for generation."""
        found: list[str] = []
        if not self.synthetic_person:
            found.append(f"{self.name}: not attested as a synthetic person")
        if not self.look_id:
            found.append(f"{self.name}: no look_id")
        for angle in REQUIRED_ANGLES:
            image = self.image(angle)
            if image is None:
                found.append(f"{self.name}: missing {angle} reference")
                continue
            if not image.approved:
                found.append(f"{self.name}: {angle} reference not approved")
            path = root / image.path
            if not path.is_file():
                found.append(f"{self.name}: {angle} file missing: "
                             f"{image.path}")
            elif hash_file(path) != image.sha256:
                found.append(f"{self.name}: {angle} file changed after "
                             f"approval: {image.path}")
        return found


def register_reference(root: Path, *, angle: RefAngle,
                       relative_path: str) -> ReferenceImage:
    """Hash a file on disk; approval is a separate Owner action."""
    return ReferenceImage(angle=angle, path=relative_path,
                          sha256=hash_file(root / relative_path))


def attachment_plan(sets: list[CharacterReferenceSet], *,
                    angles: tuple[RefAngle, ...] = REQUIRED_ANGLES,
                    max_images: int | None = None) -> list[dict]:
    """Ordered uploads: per character (scene order), FRONT then 3/4 then
    PROFILE. ``max_images`` trims angles from the back, keeping every
    character's FRONT first, so a provider limit never drops a person."""
    ordered: list[dict] = []
    for angle in angles:
        for ref_set in sets:
            image = ref_set.image(angle)
            if image is not None:
                ordered.append({"character": ref_set.name, "angle": angle,
                                "path": image.path, "sha256": image.sha256,
                                "label": f"@{ref_set.name}"})
    if max_images is not None:
        ordered = ordered[:max_images]
    return ordered


def reference_strategy_for(sets: list[CharacterReferenceSet], *,
                           provider_supports_image_ref: bool,
                           max_images: int | None = None
                           ) -> ReferenceStrategy:
    plan = attachment_plan(sets, max_images=max_images)
    lineage = [f"{p['character']}:{p['angle']}:{p['sha256'][:16]}"
               for p in plan]
    if provider_supports_image_ref and lineage:
        return ReferenceStrategy(mode="IMAGE_REFERENCE",
                                 supports_image_ref=True, lineage=lineage)
    return ReferenceStrategy(mode="TEXT_ANCHOR_ONLY",
                             supports_image_ref=provider_supports_image_ref,
                             lineage=lineage)
