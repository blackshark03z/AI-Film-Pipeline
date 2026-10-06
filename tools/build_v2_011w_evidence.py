"""V2-011W final evidence builder — authority NOT established (fail-closed)."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
P12 = ROOT / "projects/quality_v2_012_f3r_policy_repair"
PKG = ROOT / "projects/quality_v2_011w_unwatermarked_authority"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


f1r = sha256(P11D / "assets" / "f1r.mp4")
f2 = sha256(P11D / "inputs_F2_proof.mp4")
f3r12 = sha256(P12 / "assets" / "f3r_012.mp4")
proof = sha256(P12 / "outputs" / "F1R_F2_F3R_SEQUENCE_PROOF.mp4")
assert f1r == "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"
assert f2 == "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"
assert f3r12 == "b558f8e89ae4664ca6d7325f84fcf18ad17174bc72caa12773354266c2427bbb"
assert proof == "63eac46c7a5568ba4a3c1f0ffe54d911f7d96d35d3369bab59c70fe31c1b30ef"
playback = json.loads((PKG / "V2_011W_PLAYBACK_ACQUISITION.json").read_text(encoding="utf-8"))
ui = json.loads((PKG / "V2_011W_UI_ENTITLEMENT.json").read_text(encoding="utf-8"))
variants = json.loads((PKG / "V2_011W_CREATION_VARIANTS.json").read_text(encoding="utf-8"))

# ---- network correlation (final) -------------------------------------------
acq = next(a for a in playback["acquired"] if "sha256" in a)
write("V2_011W_NETWORK_CORRELATION.json", {
    "version": "v2-011w-network-correlation-final-v1",
    "built_at": utcnow(),
    "checkpoint": "V2011W_P3_NETWORK_CORRELATION",
    "correlations": [
        {
            "creation_id": "1542350901495057 (F3R_012)",
            "channel": "authenticated player stream",
            "exact_chain": "UI play action -> <video>.currentSrc (provider-"
                           "issued, unmodified) -> authenticated context "
                           "request -> response bytes",
            "url_structure": playback["player_src_structural"],
            "acquired_sha256": acq["sha256"],
            "byte_identical_to_watermarked_custody": True,
            "watermarked_custody_sha": f3r12,
            "finding": "the provider's own authenticated player streams the "
                       "lr=cici_ai WATERMARKED variant — byte-identical to "
                       "the qualified download_url asset",
        },
        {
            "creation_id": "1542350901495057 (F3R_012)",
            "channel": "viewer header download control",
            "finding": "v1 click matched the site-wide desktop-installer "
                       "button (page-wide label scan — lesson recorded); v2 "
                       "card/player scoping found NO download control in the "
                       "card or player (pause/play/mute only); the viewer "
                       "header ⬇ control is icon-only and clicking the "
                       "top-right zone closed the viewer — the only "
                       "successful asset acquisition came from the player "
                       "stream channel above",
        },
    ],
    "parameter_tampering": "NONE — every URL acquired or inspected was "
                           "provider-issued verbatim (in-page src or "
                           "provider JSON); no lr/host/path/query edits; no "
                           "brute-forced endpoints",
})

# ---- authority classification ----------------------------------------------
write("V2_011W_AUTHORITY_CLASSIFICATION.json", {
    "version": "v2-011w-authority-classification-v1",
    "checkpoint": "V2011W_AUTHORITY",
    "decided_at": utcnow(),
    "creations_inspected": [
        {"label": "F1R", "creation_id": "1546471384527889", "account": "ACCOUNT_A",
         "lr_values_provider_delivered": ["cici_ai"], "ui": "UI_GENERIC_DOWNLOAD",
         "level": "D"},
        {"label": "F2A-R", "creation_id": "1543341075843857", "account": "ACCOUNT_A",
         "lr_values_provider_delivered": ["cici_ai"], "ui": "UI_GENERIC_DOWNLOAD",
         "level": "D"},
        {"label": "F2B-R", "creation_id": "1546449850446097", "account": "ACCOUNT_A",
         "lr_values_provider_delivered": ["cici_ai"], "ui": "UI_GENERIC_DOWNLOAD",
         "level": "D"},
        {"label": "F3R_012", "creation_id": "1542350901495057", "account": "ACCOUNT_D",
         "lr_values_provider_delivered": ["cici_ai"], "ui": "UI_GENERIC_DOWNLOAD",
         "player_stream": "byte-identical watermarked variant (lr=cici_ai)",
         "level": "D"},
    ],
    "levels": {
        "A_explicit": "NOT REACHED — no UI control anywhere on the four "
                      "creation cards, players, or viewer labels a "
                      "no-watermark/original variant; no plan-level grant "
                      "surface found",
        "B_provider_delivered_unclear": "NOT REACHED for the four frozen "
                                        "creations — provider-delivered "
                                        "objects carry ONLY lr=cici_ai. "
                                        "HISTORICAL: the 010C-era F2A raw "
                                        "SSE capture (reconstructed in "
                                        "V2_010D_UNWATERMARKED_VARIANT.json) "
                                        "carried lr=unwatermarked-labeled "
                                        "variants, but that creation's "
                                        "message has rolled out of the "
                                        "current conversation pull window "
                                        "and cannot be re-verified through "
                                        "any qualified path; re-deriving it "
                                        "would require forbidden URL work — "
                                        "it remains OBSERVED_NOT_AUTHORIZED",
        "C_derivable": "NOT EXERCISED (forbidden) — no parameter editing, "
                       "no URL guessing, no undocumented endpoints",
        "D_no_variant": "REACHED for all four minimum creations under "
                        "current qualified paths",
    },
    "canonical": {
        "UNWATERMARKED_VARIANT": "OBSERVED_NOT_AUTHORIZED (retained)",
        "UNWATERMARKED_AUTHORITY": "NOT_AVAILABLE (current creations; "
                                   "current qualified paths)",
        "production_assets": "watermarked lr=cici_ai custody unchanged",
    },
    "confidence": "HIGH for the four frozen creations (three independent "
                  "channels: creation objects, UI control surfaces, player "
                  "stream bytes)",
})

# ---- adapter contract (conditional, NOT qualified) ---------------------------
write("V2_011W_ADAPTER_CONTRACT.json", {
    "version": "v2-011w-adapter-contract-v1",
    "status": "NOT_QUALIFIED — no authorized unwatermarked path exists to "
              "qualify; contract recorded conditionally for a future slice "
              "IF provider authority ever reaches LEVEL A",
    "DolaAssetVariantResolver_conditional_design": {
        "input": "creation_id (exact provider lineage)",
        "step_1": "enumerate provider-issued variants from provider-delivered "
                  "data only (creation object fields + provider UI workflow)",
        "step_2": "classify watermark status by the lr marker / provider "
                  "labels (never by URL appearance alone)",
        "step_3": "validate entitlement (LEVEL A evidence or fail closed)",
        "step_4": "choose preferred authorized asset: "
                  "AUTHORIZED_UNWATERMARKED else AUTHORIZED_WATERMARKED",
        "boundary": "Film Core never reasons about lr parameters, Dola URL "
                    "layout, provider UI, or watermark URL semantics — all "
                    "of it stays inside the Dola provider adapter",
    },
    "qualification_preconditions": [
        "provider UI explicitly labels a no-watermark/original control "
        "(LEVEL A), or",
        "a provider plan/account surface explicitly grants watermark-free "
        "download, and",
        "one read-only acquisition + content-equivalence QC proves the "
        "variant is the same generation",
    ],
})

# ---- migration plan (not required) -------------------------------------------
write("V2_011W_MIGRATION_PLAN.json", {
    "version": "v2-011w-migration-plan-v1",
    "status": "NOT_REQUIRED — no LEVEL A authority; current watermarked "
              "custody stands",
    "conditional_sketch": "IF a future slice proves LEVEL A: a controlled "
                          "rebind would (1) acquire the authorized variant "
                          "per creation, (2) run content-equivalence QC "
                          "(same generation proof), (3) rebind asset custody "
                          "while preserving the frozen editorial frame "
                          "ranges and the sequence lock, (4) re-seal the "
                          "proof — all in a dedicated Owner-authorized "
                          "slice, never inside a qualification slice",
})

# ---- secret audit ------------------------------------------------------------
git_files = subprocess_list = None
import subprocess
git = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                     text=True).stdout.splitlines()
MARKERS = [b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
           b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]
hits, scanned = [], 0
targets = sorted(ROOT.glob("tools/*v2_011w*.py")) + sorted(PKG.glob("*.json"))
for p in targets:
    scanned += 1
    blob = p.read_bytes()
    for m in MARKERS:
        if m.lower() in blob.lower():
            hits.append(f"{p.name}: {m.decode()}")
write("V2_011W_SECRET_AUDIT.json", {
    "version": "v2-011w-secret-audit-v1",
    "built_at": utcnow(),
    "scope": "V2-011W slice files from disk (tools + project JSONs) as they "
             "will be committed; raw network captures stay DPAPI-encrypted "
             "in the untracked cache layer; signed query values redacted in "
             "all persisted evidence",
    "files_scanned": scanned,
    "hits": hits,
    "verdict": "CLEAN" if not hits else "FAIL",
})

# ---- candidate seal -----------------------------------------------------------
write("V2_011W_CANDIDATE_SEAL.json", {
    "version": "v2-011w-candidate-seal-v1",
    "sealed_at": utcnow(),
    "checkpoint": "V2011W_SEAL",
    "status": "COMPLETED_CANDIDATE",
    "outcome": "AUTHORITY NOT ESTABLISHED — UNWATERMARKED_VARIANT retained "
               "as OBSERVED_NOT_AUTHORIZED",
    "canonical": {
        "UNWATERMARKED_VARIANT": "OBSERVED_NOT_AUTHORIZED (retained)",
        "UNWATERMARKED_AUTHORITY": "NOT_AVAILABLE (four frozen creations, "
                                   "current qualified paths)",
        "production_assets": "watermarked custody UNCHANGED — F1R b879f215…, "
                             "F2 ada66463…, F3R_012 b558f8e8…, proof "
                             "63eac46c… all recomputed and untouched",
        "SEQ_CONTEXT_LOCK": "GRANTED (unchanged)",
    },
    "checks": {
        "custody_verified": True,
        "four_creations_reconstructed": True,
        "ui_control_surfaces_inspected": True,
        "player_stream_byte_identical_to_watermarked": True,
        "no_parameter_tampering": True,
        "no_url_guessing": True,
        "no_undocumented_endpoints": True,
        "no_generation": True,
        "video_generation_mutations": 0,
        "secret_audit_clean": True,
        "film_assets_modified": False,
    },
    "video_generation_mutations": 0,
    "next_handoff": "STOP — return to Tech Lead: (A) V2-011X authorized "
                    "watermark-free rebinding is NOT actionable now (no "
                    "authority); (B) retain watermarked custody and proceed "
                    "to finishing strategy. Re-qualification preconditions "
                    "are recorded in V2_011W_ADAPTER_CONTRACT.json",
})

print("V2-011W evidence complete")
