"""Verify or regenerate docs/sot/film/MANIFEST.sha256.json.

Hash basis: the COMMITTED git blob bytes (LF, machine-independent), so the
manifest verifies identically on any checkout/EOL configuration:

    python tools/verify_sot_manifest.py            # verify against HEAD blobs
    python tools/verify_sot_manifest.py --regenerate  # rewrite manifest
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILM = ROOT / "docs" / "sot" / "film"
MANIFEST = FILM / "MANIFEST.sha256.json"


def blob_sha256(rel: str) -> str:
    import hashlib

    raw = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:docs/sot/film/{rel}"],
        cwd=ROOT, capture_output=True, check=True).stdout
    return hashlib.sha256(raw).hexdigest()


def main():
    regenerate = "--regenerate" in sys.argv
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if regenerate:
        entries = {rel: blob_sha256(rel) for rel in sorted(manifest)}
        MANIFEST.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"regenerated {len(entries)} entries over HEAD git-blob bytes")
        return
    bad = []
    for rel, expected in manifest.items():
        actual = blob_sha256(rel)
        if actual != expected:
            bad.append(rel)
    print(f"entries: {len(manifest)}; verified: {len(manifest) - len(bad)}; "
          f"mismatched: {bad if bad else 'NONE'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
