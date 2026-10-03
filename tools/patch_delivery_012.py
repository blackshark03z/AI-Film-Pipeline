"""One-shot patcher for tools/build_delivery_012.py (R11-R14 extensions).
Run once; it idempotently injects the 012 additions into the 011-derived
builder, then deletes nothing else.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "tools/build_delivery_012.py"
src = p.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. comparison load before use (after semantic load)
anchor = '''    review = json.loads(
        (D11 / "review/owner_review_packet_011.json").read_text(
            encoding="utf-8"))'''
if "semantic_model_comparison_012.json\").read_text(" not in src:
    src = src.replace(anchor, '''    comparison = json.loads((D12 / "semantic_model_comparison_012.json")
                            .read_text(encoding="utf-8"))
''' + anchor)

# 2. bundle copies: comparison + packet V2 + requirement docs
anchor2 = '''    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")'''
if "narration_production_requirement_012.json" not in src:
    src = src.replace(anchor2, anchor2 + '''
    packet12 = json.loads((D12 / "owner_review_packet_012.json")
                          .read_text(encoding="utf-8"))
    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(packet12, indent=2, ensure_ascii=False), encoding="utf-8")
    (BUNDLE / "manifests/narration_production_requirement_012.json").write_text(
        (D12 / "narration_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "manifests/caption_production_requirement_012.json").write_text(
        (D12 / "caption_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "qc/semantic_model_comparison_012.json").write_text(
        (D12 / "semantic_model_comparison_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")''')

# 3. semantic verdict additions (3.1 + classification + warning)
old_verdict = '''        json.dumps({"verdict": semantic["verdict"],
                    "model": semantic["model_frozen"],
                    "corpus_hash": semantic["corpus_hash"],
                    "run1_matrix": semantic["run1"]["matrix"]}, indent=1),
        encoding="utf-8")'''
if "unsupported_conclusion_warning" not in src:
    src = src.replace(old_verdict, '''        json.dumps({"verdict": semantic["verdict"],
                    "model": semantic["model_frozen"],
                    "corpus_hash": semantic["corpus_hash"],
                    "run1_matrix": semantic["run1"]["matrix"],
                    "gemini_3_1_flash_lite":
                        comparison["gemini_3_1_flash_lite"]["verdict"],
                    "classification": comparison["classification"],
                    "unsupported_conclusion_warning":
                        comparison["unsupported_conclusion_warning"]},
                   indent=1), encoding="utf-8")''')

# 4. extra entries after the semantic_qc entry
old_entry = '''        DeliveryEntry(role="semantic_qc", path="qc/semantic_verdict.json",
                      sha256=file_hash(BUNDLE / "qc/semantic_verdict.json"),
                      bytes=(BUNDLE / "qc/semantic_verdict.json").stat().st_size,
                      media_type="application/json",
                      source_lineage="frozen 006 corpus, model " +
                                     semantic["model_frozen"]),'''
if "semantic_model_comparison_012.json" not in src.split("entries = [")[1].split("]")[0]:
    extra = '''        DeliveryEntry(role="semantic_receipt",
                      path="qc/semantic_model_comparison_012.json",
                      sha256=file_hash(
                          BUNDLE / "qc/semantic_model_comparison_012.json"),
                      bytes=(BUNDLE /
                             "qc/semantic_model_comparison_012.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="012 diagnostic comparison: both "
                                     "models NOT_QUALIFIED"),
        DeliveryEntry(role="narration_requirement",
                      path="manifests/"
                           "narration_production_requirement_012.json",
                      sha256=file_hash(BUNDLE /
                          "manifests/narration_production_requirement_012"
                          ".json"),
                      bytes=(BUNDLE / "manifests/"
                             "narration_production_requirement_012.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="R9 narration gate"),
        DeliveryEntry(role="caption_requirement",
                      path="manifests/"
                           "caption_production_requirement_012.json",
                      sha256=file_hash(BUNDLE /
                          "manifests/caption_production_requirement_012"
                          ".json"),
                      bytes=(BUNDLE / "manifests/"
                             "caption_production_requirement_012.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="R10 caption gate"),'''
    src = src.replace(old_entry, old_entry + "\n" + extra)

# 5. readiness model with profiles
old_ready = '''    readiness = {
        "VISUAL_TECHNICAL_READY": True,
        "SEMANTIC_QC_READY": False,   # NOT_QUALIFIED (model capability)
        "CONTENT_AUDIO_READY": False,  # UNQUALIFIED (no authoritative narration)
        "CAPTIONS_READY": False,       # TIMED_CAPTION_AUTHORITY_UNAVAILABLE
        "OWNER_TAKE_REVIEW_READY": True,  # packet built; review pending Owner
        "DELIVERY_BUNDLE_READY": conformance["result"] == "PASS",
        "final_status": ("OWNER_REVIEW_REQUIRED + SEMANTIC_EXTERNAL_GATE + "
                         "AUDIO_CONTENT_GATE — TECHNICAL_DELIVERY_PROVEN "
                         "does NOT imply RELEASE_READY"),
        "release_status": "OWNER_REVIEW_REQUIRED"}'''
if "release_profile" not in src:
    src = src.replace(old_ready, '''    readiness = {
        "VISUAL_TECHNICAL_READY": True,
        "UPLOAD_CONTRACT_READY": True,
        "EDITORIAL_READY": True,
        "DELIVERY_BUNDLE_READY": conformance["result"] == "PASS",
        "SEMANTIC_QC_READY": False,   # BOTH_NOT_QUALIFIED (capability)
        "OWNER_TAKE_REVIEW_COMPLETE": False,  # packet ready, Owner pending
        "CONTENT_AUDIO_READY": False,  # UNQUALIFIED (no authoritative narration)
        "TIMED_CAPTIONS_READY": False,  # TIMED_CAPTION_AUTHORITY_UNAVAILABLE
        "release_profile": {
            "TECHNICAL_FILM_ASSET_RELEASE": "READY",
            "FINAL_CONTENT_RELEASE": "GATED (semantic + narration + "
                                     "captions + Owner review)"},
        "final_status": ("OWNER_REVIEW_REQUIRED + SEMANTIC_MODEL_GATE + "
                         "CONTENT_AUDIO_GATE + CAPTION_GATE — "
                         "TECHNICAL_DELIVERY_PROVEN does NOT imply "
                         "RELEASE_READY"),
        "release_status": "OWNER_REVIEW_REQUIRED"}''')

p.write_text(src, encoding="utf-8", newline="\n")
print("012 builder patched")
