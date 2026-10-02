"""PHASE 6 — the production lifecycle must be executable without Slice-0011.

The productized Flow R2V seam (boundary + runtime + render lifecycle +
reference adoption) is generic: no Slice-0011 module, authority ID, or
historical state may be required to run an ordinary shot through it.
Structural guards pin the source level; a fresh-interpreter import proves
the generic modules load with zero slice modules present.
"""
import ast
import subprocess
import sys
from pathlib import Path

import film_pipeline.flow_r2v_boundary as boundary
import film_pipeline.flow_r2v_runtime as runtime
from film_pipeline.providers import flow_reference_binding as binding

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "flow_r2v_boundary": boundary,
    "flow_r2v_runtime": runtime,
    "flow_reference_binding": binding,
}


def test_production_seam_modules_never_import_slice0011():
    for name, module in MODULES.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for imported in names:
                assert "slice0011" not in imported, (name, imported)
        assert "slice0011" not in source.replace("Slice-0011", ""), name


def test_production_seam_sources_carry_no_slice_authority_literals():
    for name, module in MODULES.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        for literal in ("successor_authority_id", "supersedes_attempt",
                        "owner_brief_sha256", "historical_snapshot_sha256"):
            assert literal not in source, (name, literal)


def test_generic_runtime_constructs_without_any_slice_module_in_process():
    """Fresh interpreter: import the generic seam, construct the runtime with
    a runtime store, and assert no slice0011 module was pulled in."""
    code = (
        "import sys;"
        f"sys.path.insert(0, r'{ROOT / 'src'}');"
        "from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime;"
        "from film_pipeline.store import SQLiteStore;"
        "runtime = FlowR2VShotRuntime("
        "SQLiteStore(r'" + str(ROOT / "scratch" / "genericity_probe.sqlite") + "'),"
        "project_id='11111111-2222-3333-4444-555555555555',"
        "account_id='genericity-probe');"
        "assert runtime.RENDER_DROP_PERSISTENCE_THRESHOLD >= 2;"
        "leaked = [m for m in sys.modules if 'slice0011' in m];"
        "assert not leaked, leaked;"
        "print('GENERIC_SEAM_CLEAN')"
    )
    completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                               capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr[-600:]
    assert "GENERIC_SEAM_CLEAN" in completed.stdout
