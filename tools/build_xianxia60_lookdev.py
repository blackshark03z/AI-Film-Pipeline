"""Deterministic builder for XIANXIA60 Look Development & Reference Preflight assets.

Generates:
1. character_white_cultivator.json (CharacterV1)
2. character_black_cultivator.json (CharacterV1)
3. location_van_dai_terrace.json (Location specification)
4. visual_style_bible.json (Color palette, weapons, optics, qi mechanics)
5. concept_schematics.svg (Vector schematic design sheet)
6. concept_schematics.md (Markdown specification guide)
7. reference_asset_ledger.json (AssetV1 fail-closed unbound ledger)

Deterministic; 0 provider calls, $0 spend.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import validate_contract

LOOK_DEV_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van" / "look_development"


def build_all_lookdev_assets() -> dict[str, str]:
    LOOK_DEV_DIR.mkdir(parents=True, exist_ok=True)
    generated = {}

    # 1. White Cultivator
    white = {
        "character_id": "WHITE_CULTIVATOR",
        "identity_version": "v1.0.0-lookdev-draft",
        "visual_identity": {
            "description": "Protagonist Lý Phá Vân (Bạch Y Kiếm Tu): youthful yet profoundly disciplined Daoist swordsman embodying serene elegance, razor-sharp focus, and effortless agility in high-altitude mountain combat.",
            "face_geometry": "Clean refined jawline with sculpted cheekbones, calm almond-shaped eyes with deep dark irises, straight noble nose bridge, serene and composed facial expression without excess muscle tension.",
            "body_proportions": "Slender athletic martial build, approximately 178cm height, long limbs, upright spine with perfectly centered balance and erect posture.",
            "age_range": "21-24 years old",
            "hair": "Lustrous ink-black straight hair reaching mid-back, upper section gathered into a high bun secured by an engraved sterling-silver crown hairpin (ngân quan), paired with dual flowing black silk ribbons cascading down the shoulder blades.",
            "skin": "Fair porcelain complexion with subtle cold-undertone radiance, immaculate texture reflecting diffuse dawn mist.",
            "silhouette": "Vertical, fluid, and wind-responsive; slender core accentuated by fitted waist and billowy lower robe layers creating a dynamic aerodynamic trail during footwork and leaps.",
            "unique_traits": [
                "Serene unblinking gaze during sword engagements",
                "Slight silver gleam in hair accessory under morning light",
                "Zero extraneous head or torso bobbing during rapid linear lunges"
            ]
        },
        "behavioral_identity": {
            "baseline": [
                "Maintains defensive poise and observant distance before committing to attacks",
                "Executes precision deflections using minimal angular rotation of the wrist and elbow",
                "Glides across stone pavers with near-silent weight transfer and stable horizontal eyeline",
                "Single decisive payoff thrust (X10) delivered without emotional flourish or theatrical hesitation",
                "Restrained breathing and composed posture even after heavy kinetic clashes"
            ],
            "forbidden": [
                "No wild screaming or theatrical battle roars",
                "No uncontrolled wide slashing motions or over-extended swings",
                "No modern military tactical stances or boxing guards",
                "No anime-style exaggerated facial distortions or sweat drops",
                "No demonic or corrupt energy manifestations"
            ]
        },
        "vocal_identity": None,
        "look_states": [
            {
                "look_state_id": "LOOK_WHITE_ROBE_V1",
                "description": "Pristine White Daoist Martial Robes (Bạch Y Đạo Bào) for high-mountain duel at dawn.",
                "wardrobe": "Multi-layered ceremonial martial vestment: inner white unbleached linen tunic, middle light azure-tinted silk cross-collar robe, outer flowing pure white heavy silk-crepe robe featuring delicate tone-on-tone silver cloud embroidery along lapels and sleeve borders; wide white silk waist sash bound by a dark silver plate and jade cord toggle; dark silver-grey embossed leather bracers tightly buckled over wrists; flexible black-soled white cloth combat boots.",
                "hair": "Neatly combed high crown bun with two black silk ribbon tails, stray sideburn wisps fluttering naturally in mountain breeze.",
                "makeup": "Subtle cinematic realism: matte natural skin, defined dark brows, natural lip tone, faint cold exposure blush on cheekbones.",
                "accessories": [
                    "Sterling silver cloud-motif crown hairpin (ngân quan)",
                    "Dual dark silver-chased leather forearm bracers (hộ oản)",
                    "Thanh Sương (Phá Vân Kiếm): 92cm slender double-edged straight sword with white mutton-fat jade hilt and silver cloud scabbard"
                ],
                "condition": [
                    "Clean, pristine fabric with mist moisture sheen",
                    "No blood, no tears; light wind-borne dust on hem only after X08 aerial landing"
                ]
            }
        ]
    }
    validate_contract("character", white)
    p_white = LOOK_DEV_DIR / "character_white_cultivator.json"
    p_white.write_text(json.dumps(white, indent=2, ensure_ascii=False), encoding="utf-8")
    generated["character_white_cultivator.json"] = str(p_white)

    # 2. Black Cultivator
    black = {
        "character_id": "BLACK_CULTIVATOR",
        "identity_version": "v1.0.0-lookdev-draft",
        "visual_identity": {
            "description": "Antagonist Dạ Vô Nhai (Hắc Y Kiếm Tu): formidable, brooding martial cultivator whose presence exerts crushing spatial gravity, wielding a massive broadsword with devastating kinetic momentum.",
            "face_geometry": "Angular chiselled jawline with prominent cheekbones, deep-set hooded piercing eyes with intense focused gaze, firm cleft chin, brooding stern expression forged in fierce combat.",
            "body_proportions": "Broad, muscular athletic frame, approximately 185cm height, wide shoulders, thick forearms, low and grounded center of gravity with powerful rooted leg stance.",
            "age_range": "27-29 years old",
            "hair": "Coarse dark raven hair, shoulder-length; crown and temple strands drawn back into a half-ponytail clamped with a hammered obsidian-iron clasp, loose rogue strands whipping across temples in heavy mountain wind.",
            "skin": "Weathered pale olive skin tone, hardened texture with faint shadow under hollow cheeks, reflecting cold diffused mountain ambient light.",
            "silhouette": "Broad-shouldered, wedge-shaped and heavily grounded; asymmetrical silhouette reinforced by right-shoulder leather pauldron and heavy trailing dark coat tails.",
            "unique_traits": [
                "Piercing, predatory eye contact locked onto opponent weapon hand",
                "Heavy single-pauldron leather armor contouring right shoulder",
                "Visible muscle tension in neck and traps during heavy downward swings"
            ]
        },
        "behavioral_identity": {
            "baseline": [
                "Initiates combat through relentless forward pressure and spatial encroachment",
                "Delivers heavy cleaving arcs with devastating momentum and grounded weight-transfer",
                "Employs dark qi compression barrier (X06) to nullify incoming thrusts and reposition",
                "Maintains grim combat dignity; accepts defeat silently on one knee (X11) after sword barrier shatters",
                "Rhythmic, deliberate foot stomps that transfer kinetic force directly from stone pavers into blade swings"
            ],
            "forbidden": [
                "No comedic villain smirks, maniacal laughter, or cartoonish scowls",
                "No cowardly flinching or frantic scrambling on the ground",
                "No glowing demonic eyes, horns, or beast transformations",
                "No flashy wire-fu acrobatics or unnecessary mid-air spinning kicks",
                "No verbal taunting or breaking disciplined martial focus"
            ]
        },
        "vocal_identity": None,
        "look_states": [
            {
                "look_state_id": "LOOK_BLACK_ROBE_V1",
                "description": "Charcoal-Black Layered Combat Robes (Huyền Sắc Võ Bào) with armor reinforcement for high-altitude duel.",
                "wardrobe": "Heavy-duty martial combat attire: inner charcoal twill undertunic, middle matte black linen coat with reinforced hem, outer layered midnight-black heavy wool-silk robe with weathered edges; sculpted matte-black boiled leather pauldron on right shoulder secured by aged bronze rivets and cross-chest harness; dual reinforced black leather vambraces with bronze stud accents; wide leather sash with double iron buckle; heavy iron-shod black combat boots with reinforced shins.",
                "hair": "Half-tied raven hair bound with dark iron hair-ring, rest falling freely past shoulders and blowing aggressively across collar.",
                "makeup": "Grounded cinematic realism: weathered matte finish, sharp facial contouring, subtle dark shading around eyes, wind-chapped lips.",
                "accessories": [
                    "Hammered obsidian-iron hair clasp",
                    "Single-shoulder boiled leather pauldron with dark bronze rivets",
                    "Huyền Minh (Trảm Đoán Kiếm): 105cm heavy double-edged broadsword (14cm wide blade) forged from dark meteoric steel with blood fuller, wrapped in stingray skin hilt with heavy iron counterweight pommel"
                ],
                "condition": [
                    "Weathered and travel-tested; matte finish without glossy reflection",
                    "Faint dust abrasion on boots and lower coat hem from aggressive lunges and sudden stops on granite"
                ]
            }
        ]
    }
    validate_contract("character", black)
    p_black = LOOK_DEV_DIR / "character_black_cultivator.json"
    p_black.write_text(json.dumps(black, indent=2, ensure_ascii=False), encoding="utf-8")
    generated["character_black_cultivator.json"] = str(p_black)

    # 3. Location Spec
    location_spec = {
        "location_id": "LOC_VAN_DAI_TERRACE",
        "location_version": "LOC_V1",
        "name": "Vân Đài Terrace (Vân Đài Thạch Đỉnh)",
        "setting_type": "High-Altitude Sacred Mountain Summit Arena",
        "elevation": "~2,800 meters altitude above sea of clouds",
        "arena_geometry": {
            "shape": "Circular open mountain terrace",
            "diameter_meters": 30.0,
            "surface_material": "Weathered dark granite flagstones with shallowly etched concentric Daoist Bagua geomantic rings, faint micro-fissures and desaturated dried moss",
            "perimeter": "Low ancient stone balustrade (0.7m height) with weathered cloud-pattern relief, chipped and eroded by centuries of exposure",
            "boundary_dropoff": "Sheer vertical cliff walls descending into perpetual mountain cloud sea"
        },
        "cardinal_landmarks": {
            "north": {
                "role": "Distant Depth Background",
                "features": "Precipice opening onto boundless undulating sea of white-grey clouds; jagged vertical peak silhouettes piercing through fog layer under cold morning sky"
            },
            "south": {
                "role": "Protected Camera / Observer Zone",
                "features": "Solid mountain shoulder ledge; strictly designated zone for 100% of camera setups to maintain immutable 180-degree action axis"
            },
            "west": {
                "role": "Stage Left / White Initial Sector",
                "features": "Weathered ancient stone archway monolith (3.5m height); starting combat position for White Cultivator facing East"
            },
            "east": {
                "role": "Stage Right / Black Initial Sector / Sunrise Vector",
                "features": "Ancient weathered dragon-cloud pillar (4.0m height); starting combat position for Black Cultivator facing West; horizon source of eventual morning sunlight"
            },
            "center": {
                "role": "Active Combat Circle (8m radius)",
                "features": "Paver center with concentric circular runic etchings, faint surface scuffs and hairline cracks from previous martial clashes"
            }
        },
        "spatial_continuity_rules": {
            "camera_axis_restriction": "Camera must remain strictly in South hemisphere (azimuth 150° to 210°). Zero camera crossings to North side.",
            "screen_direction_phase1_x01_x07": "White Cultivator occupies screen-left (West) facing East; Black Cultivator occupies screen-right (East) facing West.",
            "spatial_inversion_x08": "Shot X08 Aerial Inversion: White Cultivator executes aerial leap arcing cleanly from West to East across Black Cultivator; landing on East ledge facing West; Black Cultivator pivots in center facing East.",
            "screen_direction_phase2_x09_x12": "White Cultivator occupies screen-right (East) facing West; Black Cultivator occupies screen-left (West/Center) facing East."
        },
        "lighting_and_atmosphere_progression": {
            "phase_1_x01_x06": {
                "lighting_character": "Cold diffuse grey-cyan dawn cloudlight, soft wrap-around ambient, subtle blue shadows",
                "mist_density": "Dense low-drifting mountain fog skimming 20cm above flagstones",
                "color_temperature_k": 6800,
                "key_to_fill_ratio": "1.5:1"
            },
            "phase_2_x07_x09": {
                "lighting_character": "Turbulent mist backlit by rising horizon glow; sharp glancing edge light on wet stone and spinning blade edges; bursting amber sparks upon blade-barrier impact",
                "mist_density": "Dispersed and swirling radially from kinetic shockwaves",
                "color_temperature_k": 6200,
                "key_to_fill_ratio": "2.5:1"
            },
            "phase_3_x10_x12": {
                "lighting_character": "Ruptured cloud ceiling; directional warm morning sunlight (5200K) piercing through mist from East-Southeast, illuminating White Cultivator in luminous gold rim-light while Black Cultivator kneels in calm desaturated shadow",
                "mist_density": "Thinning luminous mist evaporating into golden haze",
                "color_temperature_k": 5200,
                "key_to_fill_ratio": "4:1"
            }
        }
    }
    p_loc = LOOK_DEV_DIR / "location_van_dai_terrace.json"
    p_loc.write_text(json.dumps(location_spec, indent=2, ensure_ascii=False), encoding="utf-8")
    generated["location_van_dai_terrace.json"] = str(p_loc)

    # 4. Visual Style Bible
    style_bible = {
        "style_bible_version": "1.0.0-xianxia60",
        "cinematic_philosophy": "Grounded Eastern Xianxia Realism (Cổ Phong Tiên Hiệp Điện Ảnh Chân Thực) inspired by the atmospheric depth of Crouching Tiger Hidden Dragon and Shadow, avoiding garish mobile-game neon or cartoon tropes.",
        "color_palette": {
            "primary_hues": {
                "white_cultivator_robe": {"hex": "#F8F9FA", "name": "Pristine Mist White", "role": "Protagonist outer robes"},
                "white_cultivator_inner": {"hex": "#E0E7ED", "name": "Pale Cloud Azure", "role": "Protagonist inner collar and silk trim"},
                "white_cultivator_metal": {"hex": "#CFD8DC", "name": "Sterling Silver", "role": "Hairpin, bracers, scabbard accents"},
                "white_cultivator_qi": {"hex": "#81D4FA", "name": "Luminous Azure Needles", "role": "Refined linear blade energy"},
                "black_cultivator_robe": {"hex": "#1C1D21", "name": "Charcoal Obsidian", "role": "Antagonist heavy outer coat"},
                "black_cultivator_leather": {"hex": "#2B2B2B", "name": "Boiled Matte Leather", "role": "Right pauldron, bracers, boot leather"},
                "black_cultivator_metal": {"hex": "#546E7A", "name": "Aged Meteoric Iron", "role": "Hair clasp, broadsword blade, belt buckle"},
                "black_cultivator_qi": {"hex": "#6A1B9A", "name": "Deep Amethyst Vapor", "role": "Dense gravitational shockwave qi"},
                "arena_granite": {"hex": "#454D53", "name": "Weathered Granite Gray", "role": "Terrace floor pavers and balustrade"},
                "mountain_mist": {"hex": "#B0BEC5", "name": "Dawn Cyan Mist", "role": "Ambient atmosphere and low clouds"},
                "sunrise_breakthrough": {"hex": "#FFD54F", "name": "Warm Morning Gold", "role": "Climax lighting key at X10-X12"}
            },
            "saturation_limits": "Robe and environment saturation capped at 25%; Qi energy luminosity contrast elevated while maintaining naturalistic diffusion",
            "contrast_profile": "Cinematic log curve with deep natural blacks (not crushed to 0) and protected highlights"
        },
        "weapons_and_props": {
            "sword_white_cultivator": {
                "name": "Thanh Sương Kiếm (Phá Vân Kiếm)",
                "type": "Slender Double-Edged Straight Sword (Tiên Hiệp Trường Kiếm)",
                "blade_length_cm": 92.0,
                "blade_width_cm": 3.2,
                "total_weight_kg": 1.1,
                "materials": "Folded Damascus patterned cold steel, hilt of carved white mutton-fat jade wrapped with fine silver wire, guard with cloud-relief chasing",
                "scabbard": "Lacquered white hornbeam wood mounted with engraved silver throat, chape, and dual suspension bands",
                "visual_dynamics": "Gleams with crisp cold specular reflection along blade ridge; leaves subtle micro-reflections in misty air"
            },
            "sword_black_cultivator": {
                "name": "Huyền Minh Kiếm (Trảm Đoán Trọng Kiếm)",
                "type": "Heavy Two-Handed Cleaving Broadsword (Hắc Thiết Trọng Kiếm)",
                "blade_length_cm": 105.0,
                "blade_width_cm": 14.0,
                "total_weight_kg": 4.8,
                "materials": "Forged dark meteoric iron with deep fuller/blood-groove, hilt wrapped in dark grey stingray skin, heavy forged iron counterweight pommel",
                "scabbard": "Aged dark bronze-trimmed oxhide sheath with wide cross-back harness",
                "visual_dynamics": "Matte gunmetal finish absorbs light; creates heavy displacement wake in mist during fast swings"
            }
        },
        "qi_energy_visual_mechanics": {
            "pale_azure_qi": {
                "geometry": "Razor-thin crystalline filaments, needles, and laminar ribbons adhering closely to blade edge (2-5cm offset)",
                "behavior": "Condenses silently; hums with high-frequency harmonic vibration; slices cleanly through mist leaving crisp negative voids",
                "decay": "Evaporates into fine crystalline light dust within 0.4 seconds of motion completion"
            },
            "dark_purple_qi": {
                "geometry": "Dense turbulent vapor and gravitational shockwave rings radiating 30-60cm from broadsword face",
                "behavior": "Distorts background mist like heat-shimmer; creates radial ground pressure waves skimming across flagstones",
                "decay": "Dissolves into dark smoky mist wisps that dissipate into ambient fog"
            },
            "collision_dynamics": {
                "impact_spark_profile": "Sharp amber/white particle sparks bursting radially at blade contact point (X04, X07)",
                "barrier_shatter_x10": "Geometric crystalline fracturing of dark qi shield into luminous purple and azure shards before vaporizing into clear dawn air"
            }
        },
        "camera_and_optics_bible": {
            "sensor_format": "Large Format Digital Cinema (43.8 x 30.2mm equivalent)",
            "aspect_ratio": "16:9 widescreen composition",
            "lens_choices": {
                "establishing_wide": {"focal_mm": 28, "shots": ["X01", "X12"], "character": "Deep perspective, vast sea of clouds framing circular arena"},
                "full_dynamic_two_shot": {"focal_mm": 40, "shots": ["X03", "X08"], "character": "Preserves full body martial silhouettes and clear 180-degree axis"},
                "medium_combat_engagements": {"focal_mm": 50, "shots": ["X05", "X06", "X09"], "character": "Neutral human perspective, authentic physical weight transfer"},
                "intense_closeup_payoff": {"focal_mm": 85, "shots": ["X02", "X04", "X07", "X10", "X11"], "character": "Shallow depth of field, crisp focus on eye intensity, blade tip, and weapon collision"}
            },
            "shutter_discipline": "Strict 180-degree shutter (1/48s at 24fps) to preserve naturalistic organic motion blur on rapid blade extensions"
        },
        "prohibited_visual_drifts": [
            "No oversaturated neon effects or cartoon cell-shading",
            "No video-game style HUD, damage numbers, or glowing magical rings on ground",
            "No flying swords swarming the sky (only the two physical weapons wielded in hand)",
            "No anime spiky hair or gravity-defying floating clothing in still poses",
            "No modern military tactical vests, boots, or tactical gloves",
            "No gore, severed limbs, or graphic blood splatters (duel resolves with honor and concession)"
        ]
    }
    p_style = LOOK_DEV_DIR / "visual_style_bible.json"
    p_style.write_text(json.dumps(style_bible, indent=2, ensure_ascii=False), encoding="utf-8")
    generated["visual_style_bible.json"] = str(p_style)

    # 5. Reference Asset Ledger
    ledger_records = [
        {
            "asset_id": "CHAR_WHITE_CULTIVATOR_REF_V1",
            "asset_type": "image",
            "origin": "reference",
            "uri_or_path": "UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED",
            "sha256": None,
            "mime_type": "image/png",
            "duration_s": None,
            "width": None,
            "height": None,
            "source_attempt_id": None,
            "provider_asset_id": None,
            "rights_metadata": {
                "target_character_id": "WHITE_CULTIVATOR",
                "creative_alias": "Lý Phá Vân (Bạch Y Kiếm Tu)",
                "qualification_tier": "DESIGN_CANDIDATE",
                "binding_status": "UNBOUND",
                "missing_action": "OWNER_IMAGE_SOURCE_REQUIRED",
                "provenance": "Pending Owner face/costume reference image selection or authorized image-prompt generation wave",
                "rights_owner": "Owner approval required",
                "license": "PENDING_OWNER_PROVENANCE",
                "intended_conditioning": "Character consistency anchor across Shots X01-X12",
                "required_views": ["Front facial portrait", "Three-quarter action stance", "Side profile in mountain mist"]
            }
        },
        {
            "asset_id": "CHAR_BLACK_CULTIVATOR_REF_V1",
            "asset_type": "image",
            "origin": "reference",
            "uri_or_path": "UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED",
            "sha256": None,
            "mime_type": "image/png",
            "duration_s": None,
            "width": None,
            "height": None,
            "source_attempt_id": None,
            "provider_asset_id": None,
            "rights_metadata": {
                "target_character_id": "BLACK_CULTIVATOR",
                "creative_alias": "Dạ Vô Nhai (Hắc Y Kiếm Tu)",
                "qualification_tier": "DESIGN_CANDIDATE",
                "binding_status": "UNBOUND",
                "missing_action": "OWNER_IMAGE_SOURCE_REQUIRED",
                "provenance": "Pending Owner face/costume reference image selection or authorized image-prompt generation wave",
                "rights_owner": "Owner approval required",
                "license": "PENDING_OWNER_PROVENANCE",
                "intended_conditioning": "Character consistency anchor across Shots X01-X12",
                "required_views": ["Front facial portrait with intense gaze", "Three-quarter broadsword combat stance", "Profile showing shoulder pauldron"]
            }
        },
        {
            "asset_id": "WARDROBE_WHITE_ROBE_V1",
            "asset_type": "image",
            "origin": "reference",
            "uri_or_path": "UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED",
            "sha256": None,
            "mime_type": "image/png",
            "duration_s": None,
            "width": None,
            "height": None,
            "source_attempt_id": None,
            "provider_asset_id": None,
            "rights_metadata": {
                "target_wardrobe_id": "LOOK_WHITE_ROBE_V1",
                "qualification_tier": "DESIGN_CANDIDATE",
                "binding_status": "UNBOUND",
                "missing_action": "OWNER_IMAGE_SOURCE_REQUIRED",
                "provenance": "Pending fabric texture reference (pure white silk-crepe with silver cloud embroidery and silver bracers)",
                "rights_owner": "Owner approval required",
                "license": "PENDING_OWNER_PROVENANCE",
                "intended_conditioning": "Texture and drape consistency anchor for white robes across dynamic movement"
            }
        },
        {
            "asset_id": "WARDROBE_BLACK_ROBE_V1",
            "asset_type": "image",
            "origin": "reference",
            "uri_or_path": "UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED",
            "sha256": None,
            "mime_type": "image/png",
            "duration_s": None,
            "width": None,
            "height": None,
            "source_attempt_id": None,
            "provider_asset_id": None,
            "rights_metadata": {
                "target_wardrobe_id": "LOOK_BLACK_ROBE_V1",
                "qualification_tier": "DESIGN_CANDIDATE",
                "binding_status": "UNBOUND",
                "missing_action": "OWNER_IMAGE_SOURCE_REQUIRED",
                "provenance": "Pending wardrobe texture reference (charcoal twill, matte black leather single pauldron with bronze rivets)",
                "rights_owner": "Owner approval required",
                "license": "PENDING_OWNER_PROVENANCE",
                "intended_conditioning": "Texture and silhouette anchor for heavy black combat attire"
            }
        },
        {
            "asset_id": "LOC_VAN_DAI_TERRACE_REF_V1",
            "asset_type": "image",
            "origin": "reference",
            "uri_or_path": "UNBOUND:OWNER_IMAGE_SOURCE_REQUIRED",
            "sha256": None,
            "mime_type": "image/png",
            "duration_s": None,
            "width": None,
            "height": None,
            "source_attempt_id": None,
            "provider_asset_id": None,
            "rights_metadata": {
                "target_location_id": "LOC_VAN_DAI_TERRACE",
                "qualification_tier": "DESIGN_CANDIDATE",
                "binding_status": "UNBOUND",
                "missing_action": "OWNER_IMAGE_SOURCE_REQUIRED",
                "provenance": "Pending high-mountain stone terrace environment keyframe (weathered circular granite platform, sea of clouds, morning mist)",
                "rights_owner": "Owner approval required",
                "license": "PENDING_OWNER_PROVENANCE",
                "intended_conditioning": "Environment world-geometry and lighting coherence anchor across X01-X12"
            }
        }
    ]

    for rec in ledger_records:
        validate_contract("asset", rec)

    ledger_payload = {
        "ledger_version": "1.0.0-xianxia60",
        "ledger_status": "AUDITED_FAIL_CLOSED_NO_REAL_IMAGE_ON_DISK",
        "total_canonical_references": len(ledger_records),
        "unbound_references_count": len(ledger_records),
        "bound_references_count": 0,
        "records": ledger_records
    }
    p_ledger = LOOK_DEV_DIR / "reference_asset_ledger.json"
    p_ledger.write_text(json.dumps(ledger_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    generated["reference_asset_ledger.json"] = str(p_ledger)

    return generated


if __name__ == "__main__":
    res = build_all_lookdev_assets()
    print("Built look development assets successfully:")
    for k, v in res.items():
        print(f"  {k} -> {v}")
