"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 5): build the Owner
decision template from the frozen review set.

The template carries the immutable reviewed bindings; the Owner only
chooses decision + optional note later. Canonical production state stays
untouched — this only writes the template file.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.owner_review import (OwnerReviewRequest,
                                        build_decision_template)

D15 = ROOT / "projects/flow_owner_review_content_gates_015"


def main() -> None:
    review_set = json.loads((D15 / "owner_review_set_015.json").read_text(
        encoding="utf-8"))
    requests = [OwnerReviewRequest.model_validate(r)
                for r in review_set["requests"]]
    path = D15 / "owner_decisions_015.template.json"
    build_decision_template(requests, path,
                            review_set["review_set_sha256"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({"template": str(path), "sha256": digest,
                      "items": len(requests)}))


if __name__ == "__main__":
    main()
