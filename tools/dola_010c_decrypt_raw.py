"""010C analysis helper: decrypt a raw capture to scratch for offline analysis."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from dola_010c_session import dpapi_unprotect

src = Path(sys.argv[1])
dst = Path(sys.argv[2] if len(sys.argv) > 2 else "scratch/raw_analysis.jsonl")
blob = src.read_text(encoding="ascii")
dst.write_bytes(dpapi_unprotect(blob))
print("decrypted", src.name, "->", dst, dst.stat().st_size, "bytes")
