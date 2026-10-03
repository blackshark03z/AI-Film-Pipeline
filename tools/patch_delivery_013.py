"""One-shot patcher: derive tools/build_delivery_013.py from the 012
builder with the 013 additions (family matrix, packet V3, requirement
013 docs). Idempotent.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "tools/build_delivery_012.py").read_text(
    encoding="utf-8").replace("\r\n", "\n")

src = src.replace(
    '"""FLOW-OWNER-REVIEW-SEMANTIC-RELEASE-012 (R11-R15): deterministic final delivery candidate.',
    '"""FLOW-GEMINI25-FINAL-QUAL-013 (G11-G15): deterministic delivery 013\nwith the final Gemini-family semantic matrix.')
src = src.replace('D12 = ROOT / "projects/flow_owner_review_release_012"\nBUNDLE = D12 / "delivery_012"',
                  'D12 = ROOT / "projects/flow_owner_review_release_012"\nD13 = ROOT / "projects/flow_gemini25_final_qual_013"\nBUNDLE = D13 / "delivery_013"')
src = src.replace('zip_path = D12 / "DELIVERY_012.zip"', 'zip_path = D13 / "DELIVERY_013.zip"')
src = src.replace('comparison = json.loads((D12 / "semantic_model_comparison_012.json")\n                            .read_text(encoding="utf-8"))',
                  'comparison = json.loads((D12 / "semantic_model_comparison_012.json")\n                            .read_text(encoding="utf-8"))\n    family = json.loads((D13 / "semantic_gemini_family_matrix_013.json")\n                        .read_text(encoding="utf-8"))\n    packet13 = json.loads((D13 / "owner_review_packet_013.json")\n                          .read_text(encoding="utf-8"))')
src = src.replace('"gemini_3_1_flash_lite":\n                        comparison["gemini_3_1_flash_lite"]["verdict"],\n                    "classification": comparison["classification"],',
                  '"gemini_3_1_flash_lite":\n                        comparison["gemini_3_1_flash_lite"]["verdict"],\n                    "classification": comparison["classification"],\n                    "gemini_family_decision":\n                        family["decision"]["GEMINI_LINE_EXHAUSTED_FOR_"\n                                           "CURRENT_FROZEN_CORPUS"],')
src = src.replace('''    packet12 = json.loads((D12 / "owner_review_packet_012.json")
                          .read_text(encoding="utf-8"))
    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(packet12, indent=2, ensure_ascii=False), encoding="utf-8")
    (BUNDLE / "manifests/narration_production_requirement_012.json").write_text(
        (D12 / "narration_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "manifests/caption_production_requirement_012.json").write_text(
        (D12 / "caption_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")''',
'''    (BUNDLE / "review" / "owner_review_packet.json").write_text(
        json.dumps(packet13, indent=2, ensure_ascii=False), encoding="utf-8")
    (BUNDLE / "manifests/narration_production_requirement_013.json").write_text(
        (D13 / "narration_production_requirement_013.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "manifests/caption_production_requirement_013.json").write_text(
        (D13 / "caption_production_requirement_013.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "qc/semantic_gemini_family_matrix_013.json").write_text(
        (D13 / "semantic_gemini_family_matrix_013.json").read_text(
            encoding="utf-8"), encoding="utf-8")''')
src = src.replace('''        DeliveryEntry(role="semantic_receipt",
                      path="qc/semantic_model_comparison_012.json",''',
'''        DeliveryEntry(role="semantic_receipt",
                      path="qc/semantic_gemini_family_matrix_013.json",
                      sha256=file_hash(
                          BUNDLE /
                          "qc/semantic_gemini_family_matrix_013.json"),
                      bytes=(BUNDLE /
                             "qc/semantic_gemini_family_matrix_013.json")
                      .stat().st_size,
                      media_type="application/json",
                      source_lineage="013 final Gemini-family matrix: "
                                     "GEMINI_LINE_EXHAUSTED_FOR_CURRENT_"
                                     "FROZEN_CORPUS"),
        DeliveryEntry(role="semantic_receipt",
                      path="qc/semantic_model_comparison_012.json",''')
src = src.replace('"manifests/"\n                           "narration_production_requirement_012.json"',
                  '"manifests/"\n                           "narration_production_requirement_013.json"')
src = src.replace('"manifests/"\n                           "caption_production_requirement_012.json"',
                  '"manifests/"\n                           "caption_production_requirement_012.json"')
src = src.replace('''    (BUNDLE / "manifests/narration_production_requirement_012.json").write_text(
        (D12 / "narration_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "manifests/caption_production_requirement_012.json").write_text(
        (D12 / "caption_production_requirement_012.json").read_text(
            encoding="utf-8"), encoding="utf-8")''',
'''    (BUNDLE / "manifests/narration_production_requirement_013.json").write_text(
        (D13 / "narration_production_requirement_013.json").read_text(
            encoding="utf-8"), encoding="utf-8")
    (BUNDLE / "manifests/caption_production_requirement_013.json").write_text(
        (D13 / "caption_production_requirement_013.json").read_text(
            encoding="utf-8"), encoding="utf-8")''')
# readiness: SEMANTIC_BACKEND_DECISION_REQUIRED
src = src.replace('''        "SEMANTIC_QC_READY": False,   # BOTH_NOT_QUALIFIED (capability)''',
'''        "SEMANTIC_QC_READY": False,   # GEMINI_LINE_EXHAUSTED (3 candidates)
        "SEMANTIC_BACKEND_DECISION_REQUIRED": True,''')
# conformance self-describing names
src = src.replace('"qc/delivery_conformance_011.json"', '"qc/delivery_conformance_013.json"')
src = src.replace('(BUNDLE / "qc/delivery_conformance_011.json").write_text',
                  '(BUNDLE / "qc/delivery_conformance_013.json").write_text')
out = ROOT / "tools/build_delivery_013.py"
out.write_text(src, encoding="utf-8", newline="\n")
print("013 builder written")
