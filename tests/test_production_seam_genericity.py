"""PHASE 6 — the production lifecycle must be executable without Slice-0011.

The productized Flow R2V seam (boundary + runtime + render lifecycle +
reference adoption) is generic: no Slice-0011 module, authority ID, or
historical state may be required to run an ordinary shot through it. The
offline vertical already proves executability; these guards pin the
structural side so a future import cannot silently reintroduce the coupling.
"""
import ast
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


def test_offline_vertical_needs_only_generic_components():
    """The generic modules are importable and constructible without any
    slice/history store present in the process."""
    import sys

    for name in [m for m in sys.modules if m.startswith("film_pipeline.slice0011")]:
        del sys.modules[name]
    import importlib

    for module in (boundary, runtime, binding):
        importlib.reload(module)
    assert FlowR2VShotRuntime_is_constructible()


def FlowR2VShotRuntime_is_constructible() -> bool:
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime

    runtime_obj = FlowR2VShotRuntime(
        __import__("film_pipeline.store", fromlist=["SQLiteStore"]).SQLiteStore(
            Path(__file__).parent / "does-not-exist-yet.sqlite"),
        project_id="11111111-2222-3333-4444-555555555555",
        account_id="any-runtime-account")
    assert runtime_obj.RENDER_DROP_PERSISTENCE_THRESHOLD >= 2
    return True
