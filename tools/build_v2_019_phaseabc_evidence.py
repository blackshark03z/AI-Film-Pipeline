"""V2-019 — Phase A/B/C evidence builder (read-only conclusions).

Consolidates:
  A: current Dola capability authority (wire, model registry, catalog,
     entitlement, transports, clean-variant machinery)
  B: BytePlus draft->final semantic oracle applied to Dola surfaces
  C: feature-gate classification per capability
  F: true-draft verdict (implicit in B/C)

Sources: raw captures (010C era + fresh V2-019 live probe), chat/xe bundles
+ 122 async chunks, /samantha/skill/pack, /alice/slot/action_bar_v3/
get_item_conf, /alice/commerce/sale/subscription/entry/config/,
/alice/profile/self, /samantha/user/ab/get. Zero mutations.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                            encoding="utf-8")
    print("wrote", name)


def main() -> int:
    phase_a = {
        "version": "v2-019-phaseA-capability-authority-v1",
        "built_at": utcnow(),
        "method": "read-only: raw capture forensics + CDN bundle deep-grep "
                  "(chat.js byte-identical to V2-016 build) + 122 async "
                  "chunks + live passive CDP probe of ACCOUNT_D "
                  "(SESSION_VALID, no requests sent)",
        "wire_contract": {
            "submit": "POST https://www.dola.com/chat/completion (SSE reply)",
            "ability_carrier": "chat_ability: {ability_type: 17, "
                               "ability_param: <JSON string>}",
            "ability_param_schema": ["model", "duration", "ratio",
                                     "resolution", "camera_movement",
                                     "input_box_content.user_input_content"],
            "observed_dispatch": {
                "model": "seedance_v2.0", "duration": 10,
                "note": "f2a release body: duration chip-gated (V2-010D "
                        "PROVEN); ratio/resolution absent when left default",
            },
            "poll": "POST /im/chain/single (limit 10/20 same shape; "
                    "deep JSON-string recursion REQUIRED)",
            "push": "wss://wss-normal-i18n.dola.com/ws/v2 (IM channel)",
            "config_endpoints": [
                "POST /samantha/skill/pack (skill meta + model_capability)",
                "POST /alice/slot/action_bar_v3/get_item_conf (composer "
                "selector templates)",
                "GET  /alice/commerce/sale/subscription/entry/config/",
                "GET  /alice/profile/self",
                "GET  /samantha/user/ab/get (feature flags)",
            ],
        },
        "model_registry": [
            {"option_key": "seedance_v2.5",
             "display": "Dreamina Seedance 2.5",
             "sub_display": "最高品質 • 5倍のクレジットを使用",
             "subs_only_tag": "enhanced",
             "credit_multiplier": 5,
             "is_default": False},
            {"option_key": "seedance_v2.0",
             "display": "Dreamina Seedance 2.0高速 (Fast)",
             "sub_display": "すぐに結果が出る優れたクオリティ",
             "subscription_tag": "none",
             "is_default": True},
            {"option_key": "ic_mini",
             "display": "Dreamina Seedance 1.0",
             "sub_display": "シンプルな動画向け",
             "subscription_tag": "none",
             "is_default": False},
        ],
        "model_capability_delivered": {
            "seedance_v2.0": {"supported_durations": ["5", "10"],
                              "supported_resolutions": ["720p"],
                              "support_video_ref": False},
            "ic_mini": {"supported_durations": ["5", "10"],
                        "supported_resolutions": ["720p"],
                        "support_video_ref": False},
            "seedance_v2.5": "NOT_LISTED_IN_DELIVERED_CATALOG "
                             "(capability hidden behind subscription gate)",
        },
        "composer_controls_delivered": {
            "video-model": ["seedance_v2.5", "seedance_v2.0", "ic_mini"],
            "video-duration": ["5", "10"],
            "video-ratio": ["1:1", "3:4", "4:3", "9:16", "16:9", "21:9"],
            "video-resolution": "ABSENT (no resolution control delivered; "
                                "frontend supports one but provider never "
                                "sent the group)",
        },
        "resolution_truth": {
            "declared": "720p (model_capability)",
            "observed_rendition": {"definition_label": "1080p",
                                   "actual": "1280x720 @ 24fps bytevc1",
                                   "bitrate": 888152,
                                   "note": "label overstates; matches "
                                           "declared 720p"},
        },
        "entitlement_probe_ACCOUNT_D": {
            "session_state": "SESSION_VALID (Khởi Đặng219)",
            "has_active_subscription": False,
            "sources": ["commerce/sale/subscription/entry/config/ x2",
                        "alice/profile/self"],
            "implication": "2.5 option DELIVERED to a non-subscriber "
                           "(template is global; entitlement enforced "
                           "elsewhere)",
        },
        "gating_mechanisms": {
            "subscription_tag/subs_only_tag": "none | enhanced (2.5)",
            "actionbar_commerce_gate_id": "per-model commerce unlock "
                                          "(observed on image model "
                                          "Seedream 4.5)",
            "ab_flags_video_post_processing": [
                "video_post_processing_is_show_remove_subtitles",
                "video_post_processing_is_show_super_resulution",
                "video_post_processing_is_show_video_edit",
                "video_post_processing_video_edit_model",
            ],
            "ab_flag_values_ACCOUNT_D": "ALL EMPTY (not exposed)",
        },
        "clean_variant_machinery": {
            "surface": "creation.video.video_model<json>.video_list.*."
                       "main_url|backup_url_1 (base64-encoded CDN URLs)",
            "variant_param": "lr=cici_ai (watermarked) vs lr=unwatermarked",
            "authority": "PROVIDER_ISSUED (V2-011W-R2 PROVEN; AVP parser "
                         "convergent; fallback_api itself carries "
                         "logo_type=unwatermarked)",
        },
        "historical_capture_truth": {
            "full_generation_lifecycle": "raw_f2b_20261006T015220 (245 "
                                         "entries, full F2A SSE)",
            "dispatch_bodies": "010C generation_attempt_*.json "
                               "(release_body_structure)",
        },
        "current_film_untouched": True,
    }
    write("V2_019_PHASEA_CAPABILITY_AUTHORITY.json", phase_a)

    phase_b = {
        "version": "v2-019-phaseB-draft-oracle-v1",
        "built_at": utcnow(),
        "oracle": {
            "true_draft_contract_byteplus": [
                "draft=true request field", "480p draft resolution",
                "provider task id = draft_task_id (persistent, 7-day)",
                "finalization = content.type=draft_task {task:{id}} + "
                "1080p on the SAME task id",
                "same-take guarantee by construction",
            ],
            "required_dola_equivalents": [
                "a persistent provider-side draft identity", "AND",
                "a provider finalization operation referencing that exact "
                "identity",
            ],
        },
        "searched_dola_surfaces": [
            "composer template selector groups (live + historical)",
            "/samantha/skill/pack model_capability",
            "chat.js + xe.js + 122 async chunks (deep-grep with contexts)",
            "AB feature flags (live /samantha/user/ab/get)",
            "video_model creation echo (generation parameter surface)",
            "historical full-lifecycle SSE capture (010C)",
        ],
        "semantic_terms_searched": [
            "draft", "preview", "rough", "quick", "low_quality", "source_task",
            "parent_task", "derive", "enhance", "render_final", "upgrade",
            "quality_upgrade", "task_reference", "generation_reference",
            "upscale", "super_resolution", "refine", "finalize",
        ],
        "findings": {
            "composer": "no draft/preview/upgrade control group delivered; "
                        "only model/duration/ratio (no resolution either)",
            "model_capability": "no draft tier; durations [5,10] + "
                                "resolutions [720p] only",
            "bundles": "ability_param/subs_only/seedance tokens appear ONLY "
                       "in registry + telemetry contexts; draft tokens = "
                       "Immer internals / chat-input drafts; finalize tokens "
                       "= telemetry flush; NO video draft/finalize op",
            "ab_flags": "video_post_processing.super_resulution flag EXISTS "
                        "in flag registry but: value EMPTY (not exposed), "
                        "no consumer in captured bundles, and the "
                        "super_resolution enum is IMAGE-edit only "
                        "(EDIT_IMAGE_FUNCTION_SUPER_RESOLUTION)",
            "creation_echo": "single-stage generation object; no draft id, "
                             "no parent/source task reference, no finalize "
                             "op on video_id",
        },
        "closest_semantic_analog": {
            "candidate": "video_post_processing super_resolution/video_edit "
                         "(AB-gated UI feature)",
            "rejected_because": [
                "not exposed on any probed account (flag empty)",
                "no frontend consumer in the captured build",
                "even if exposed, it is a post-process UI action, not a "
                "draft->final generation lineage with draft identity",
            ],
        },
        "verdict": "DOLA_TRUE_DRAFT_FINAL = NOT_OBSERVED; "
                   "DOLA_DRAFT_FINAL_FREE_ROUTE = NOT_AVAILABLE",
        "normal_route_continues": True,
    }
    write("V2_019_PHASEB_DRAFT_ORACLE.json", phase_b)

    phase_c = {
        "version": "v2-019-phaseC-gate-classification-v1",
        "built_at": utcnow(),
        "rows": [
            {"capability": "seedance_v2.0 generation",
             "ui_exposure": "UI_EXPOSED (default model)",
             "frontend": "PRESENT",
             "backend": "PRESENT (live-dispatched 6x in project history)",
             "entitlement_ACCOUNT_D": "ENTITLED (subscription_tag none)",
             "classification": "PRODUCTION_AVAILABLE"},
            {"capability": "ic_mini (Seedance 1.0) generation",
             "ui_exposure": "UI_EXPOSED",
             "frontend": "PRESENT",
             "backend": "PRESUMED (same ability_type 17 path; never "
                        "dispatched by this project)",
             "entitlement_ACCOUNT_D": "ENTITLED (subscription_tag none)",
             "classification": "AVAILABLE_UNPROVEN"},
            {"capability": "seedance_v2.5 generation",
             "ui_exposure": "UI_EXPOSED (option delivered to all)",
             "frontend": "PRESENT",
             "backend": "ASSUMED_PRESENT (no rejection observed; submit "
                        "never attempted on non-subscriber)",
             "entitlement_ACCOUNT_D": "CURRENT_ACCOUNT_NOT_ENTITLED "
                                      "(has_active_subscription=false; "
                                      "subs_only_tag=enhanced; 5x credits)",
             "classification": "FRONTEND_PRESENT_SUBSCRIPTION_GATED"},
            {"capability": "video resolution selection",
             "ui_exposure": "NOT_EXPOSED (no video-resolution group)",
             "frontend": "PRESENT (submit node reads video-resolution)",
             "backend": "CAPABILITY DECLARED per model (720p)",
             "classification": "BACKEND_PRESENT_FRONTEND_WITHHELD "
                               "(provider controls it; declared 720p)"},
            {"capability": "TRUE draft->final (same-take lineage)",
             "ui_exposure": "NOT_EXPOSED",
             "frontend": "NOT_PRESENT",
             "backend": "NOT_OBSERVED",
             "classification": "NOT_OBSERVED"},
            {"capability": "video post-processing (super-resolution/edit/"
                           "subtitle removal)",
             "ui_exposure": "NOT_EXPOSED (AB flags empty)",
             "frontend": "NO CONSUMER in captured build",
             "backend": "UNKNOWN",
             "classification": "FLAG_REGISTRY_ONLY_NOT_SHIPPED"},
        ],
        "policy": "no feature-flag overrides, no request modification to "
                  "fake entitlement, no paywall circumvention",
        "film_untouched": True,
    }
    write("V2_019_PHASEC_GATE_CLASSIFICATION.json", phase_c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
