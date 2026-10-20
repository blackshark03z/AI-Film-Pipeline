"""XIANXIA60 — Nhất Kiếm Phá Vân — Full-Film Pre-Production Compilation Builder.

Executes the existing Film Core pipeline:
NarrativeCompiler -> StoryGraph -> DirectorCompiler/ShotGraph ->
Canonical ShotSpec (X01-X12) -> Prompt Compiler (compile_prompt) ->
EditManifest (make_edit_manifest).

Deterministic; 0 provider network actions, $0 paid.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import (
    ActionIntent, Audio, Blocking, Camera, CharacterRef, Constraints,
    Continuity, Editorial, Environment, Lighting, Movement, Performance,
    PerformanceBeat, PerformanceSpec, PromptPlan, ProviderCapabilities,
    References, ShotSpec, canonical_json, sha256, validate_contract,
)
from film_pipeline.editorial import EditClip, make_edit_manifest
from film_pipeline.narrative import (
    CharacterBible, NarrativeCompiler, StoryGraph, WorldState, WorldStateGraph,
)
from film_pipeline.narrative.director import (
    DirectorCompiler, DirectorShotIntent, ShotGraph, ShotGraphEdge, ShotGraphNode,
)

PROJECT_DIR = ROOT / "projects" / "xianxia60_nhat_kiem_pha_van"
SHOTS_DIR = PROJECT_DIR / "shots"
PROMPTS_DIR = PROJECT_DIR / "prompts"
EDITORIAL_DIR = PROJECT_DIR / "editorial"
STORYBOARD_DIR = PROJECT_DIR / "storyboard"

# -----------------------------------------------------------------------------
# 1. Screenplay & Narrative Prose (12 distinct beat sentences)
# -----------------------------------------------------------------------------

PROSE = (
    "A wide view opens on the misty mountain platform where the white-robed cultivator and dark-robed cultivator face off across the terrace. "
    "The white cultivator decides to draw his slender sword, a narrow line of pale qi humming along the steel. "
    "The black cultivator crosses the stone terrace and approaches with a lunging strike, his dark robe billowing. "
    "Their blades collide in midair as each spots the unyielding force of the opposing strike amidst bursting sparks. "
    "The white cultivator takes a sharp breath as he absorbs the impact and steps smoothly aside to evade a second slash. "
    "The black cultivator pauses and thrusts his palm forward, opening a dark qi barrier while wary of counterattack. "
    "The white cultivator notices a hairline fracture in the dark shield and strikes the barrier with his sword tip. "
    "The white cultivator commits to an evasive aerial leap, arcing cleanly past his opponent through the backlit mist. "
    "Turning abruptly, the black cultivator dreads losing initiative and sweeps his blade into a dark crescent slash. "
    "The white cultivator continues forward with one decisive thrust, his bright sword-line shattering the dark energy. "
    "The mountain terrace falls into silence as the black cultivator lowers his sword and sinks onto one knee alone. "
    "The white cultivator lowers his blade and walks on toward the terrace edge at last as cloudlight breaks through."
)

CAST = [
    {
        "name": "White Cultivator",
        "desire": "maintain defensive discipline, neutralize the aggressive assault, and resolve the duel with a single decisive counter-thrust",
        "bible": {
            "character_id": "char_white_cultivator",
            "age_band": "early 20s",
            "face_geometry_family": "clean refined jawline, calm focused eyes, serene expression",
            "hair": "long straight black hair bound in a high silver crown hairpin with black ribbon tails",
            "body_build": "slender athletic martial build, agile and erect posture",
            "skin_tone": "fair porcelain complexion",
            "signature_wardrobe": "layered pure white Daoist martial robes with subtle silver cloud embroidery on collar and cuffs, dark silver leather bracers, white silk sash, light travel boots",
            "persistent_accessories": ["silver crown hairpin", "dark silver leather bracers", "silver-mounted sword scabbard"],
        },
    },
    {
        "name": "Black Cultivator",
        "desire": "dominate the platform through overwhelming kinetic pressure, dark qi barriers, and heavy cleaving strikes",
        "bible": {
            "character_id": "char_black_cultivator",
            "age_band": "late 20s",
            "face_geometry_family": "angular sharp cheekbones, intense piercing gaze, stern jaw",
            "hair": "shoulder-length dark hair partly tied, loose strands whipping across temples in wind",
            "body_build": "broad powerful athletic frame, forward-leaning combat posture",
            "skin_tone": "pale weathered olive complexion",
            "signature_wardrobe": "layered charcoal-black martial robes with obsidian leather shoulder guards and bracers, dark bronze-buckled waist sash, heavy dark combat boots",
            "persistent_accessories": ["obsidian shoulder guard", "leather bracers", "heavy iron-mounted sword scabbard"],
        },
    },
]

WORLD_INITIAL = WorldState(
    location="ancient circular granite platform of Van Dai terrace on a high mountain summit above an undulating sea of white clouds",
    time_of_day="cold morning",
    weather="mountain mist drifting low across stone pavers, cold gentle breeze",
    lighting="diffuse cold morning cloudlight, soft shadows, luminous sky horizon",
    terrain="weathered dark granite flagstones with faint Daoist geometric ring engravings and low stone balustrade",
    architecture="ancient open mountain terrace with four weathered stone marker pillars at cardinal edges",
    props_present=["four weathered stone marker pillars", "low stone balustrade", "intact granite flagstones"],
    character_position="White: West ledge (screen-left) | Black: East ledge (screen-right), 15 paces apart",
    character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
    wardrobe_state="clean white robes and clean charcoal-black robes moving in wind",
    damage_dirt="clean",
    held_objects=["White: sheathed straight sword", "Black: sheathed heavy broadsword"],
    camera_side_of_axis="south",
    screen_direction="static",
)

WORLD_STATES = [
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist drifting low across stone pavers, cold gentle breeze",
        lighting="diffuse cold morning cloudlight, soft shadows, luminous sky horizon",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "intact granite flagstones"],
        character_position="White: West ledge (screen-left) | Black: East ledge (screen-right), 15 paces apart",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="clean white robes and clean charcoal-black robes moving in wind",
        damage_dirt="clean",
        held_objects=["White: sheathed straight sword", "Black: sheathed heavy broadsword"],
        camera_side_of_axis="south",
        screen_direction="static",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist drifting low across stone pavers, cold gentle breeze",
        lighting="diffuse cold morning cloudlight, specular reflection on drawn steel",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "intact granite flagstones"],
        character_position="White: West ledge (screen-left), stationary draw | Black: East ledge (screen-right), stationary ready",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="clean white robes and clean charcoal-black robes moving in wind",
        damage_dirt="clean",
        held_objects=["White: drawn straight sword (pale azure qi active)", "Black: sheathed heavy broadsword"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist drifting low across stone pavers, cold gentle breeze",
        lighting="diffuse cold morning cloudlight, rim light on sprinting silhouette",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "intact granite flagstones"],
        character_position="White: West ledge (screen-left), anchored | Black: sprinting right-to-left across center-line",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="white robes braced; black robes billowing in forward sprint wake",
        damage_dirt="clean",
        held_objects=["White: drawn straight sword", "Black: drawn heavy broadsword (trailing dark qi)"],
        camera_side_of_axis="south",
        screen_direction="right-to-left",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist parting radially from kinetic shockwave",
        lighting="sharp specular spark flash illuminating faces and crossed blades",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "intact granite flagstones"],
        character_position="White: center-left in parry lock | Black: center-left pressing downward in blade lock",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="robe hems ruffled by spark and shockwave burst",
        damage_dirt="clean",
        held_objects=["White: straight sword in parry lock", "Black: heavy broadsword in cleave lock"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist drifting across stone pavement",
        lighting="diffuse cold morning cloudlight catching stone chips and dust",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone at center"],
        character_position="White: pivoted to foreground-left | Black: overextended at center with blade struck in stone",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="white robes clean in low evasion; stone dust on black boots and robe hem",
        damage_dirt="minor stone dust on Black boots and sword tip; White pristine",
        held_objects=["White: straight sword leveled in guard", "Black: heavy broadsword struck in stone pavement"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist swirling around projected qi barrier",
        lighting="violet luminescence emanating from dark crystalline qi barrier",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone", "manifested dark qi barrier disc"],
        character_position="White: poised at foreground-left | Black: stepped back to center-right behind qi barrier",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="white robes poised; black sleeve fabric rippling backward from palm shockwave",
        damage_dirt="minor stone dust on Black boots; White pristine",
        held_objects=["White: straight sword in ready guard", "Black: heavy broadsword at hip + manifested dark qi barrier disc"],
        camera_side_of_axis="south",
        screen_direction="right-to-left",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mountain mist crackling with static energy at barrier fracture",
        lighting="sharp azure and violet specular highlights tracing along barrier fractures",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone", "spiderweb-fractured dark qi barrier disc"],
        character_position="White: lunging rightward at center-left with tip in barrier | Black: center-right bracing barrier",
        character_orientation="White: facing East (screen-right) | Black: facing West (screen-left)",
        wardrobe_state="white sleeves forward in thrust; black robes tensed under impact force",
        damage_dirt="minor stone dust on Black boots; White pristine",
        held_objects=["White: straight sword tip wedged in barrier", "Black: heavy broadsword at hip + spiderweb-fractured dark qi barrier disc"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="rising mountain mist backlighting airborne silhouette",
        lighting="strong golden-white rim light outlining leaping silhouette against morning sky",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone"],
        character_position="White: aerial leap from West to East ledge (screen-right) | Black: turning at center-left",
        character_orientation="White: facing East in flight, landing facing West | Black: pivoting from West to East",
        wardrobe_state="white robes billowing wide like wings in flight; black robes settling after barrier collapse",
        damage_dirt="minor stone dust on Black boots; White pristine",
        held_objects=["White: straight sword tucked along forearm in flight", "Black: heavy broadsword in hand (barrier dissolved)"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mist parting along the horizontal trajectory of flying dark crescent",
        lighting="deep violet glow from flying crescent blade casting dynamic moving shadows",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone", "flying dark crescent blade"],
        character_position="White: grounded on East ledge (screen-right) | Black: West ledge (screen-left) sweeping crescent",
        character_orientation="White: facing West (screen-left) | Black: facing East (screen-right)",
        wardrobe_state="white robes grounded on East ledge; black cloak whipped around torso in follow-through",
        damage_dirt="minor stone dust on Black boots; White pristine",
        held_objects=["White: straight sword in ready guard", "Black: two-handed heavy broadsword + launched dark crescent energy"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="mist cleared in radial circle by title strike shockwave",
        lighting="brilliant white-azure puncture point light illuminating arena before clearing",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone", "dissipating grey vapor"],
        character_position="White: lunging leftward from East ledge | Black: staggered back on West ledge (screen-left)",
        character_orientation="White: facing West (screen-left) | Black: facing East (screen-right)",
        wardrobe_state="white robes flowing backward in lunging line; black robes disheveled by impact shock",
        damage_dirt="minor stone dust on Black boots; White pristine",
        held_objects=["White: straight sword in decisive linear thrust", "Black: heavy broadsword deflected low (crescent shattered)"],
        camera_side_of_axis="south",
        screen_direction="right-to-left",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning",
        weather="still mountain air, thinning quiet mist",
        lighting="soft diffuse cloudlight softening dark robes in quiet aftermath",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone"],
        character_position="White: standing heroically on East ledge | Black: kneeling in defeat on West ledge (screen-left)",
        character_orientation="White: facing West (screen-left) | Black: facing East (screen-right)",
        wardrobe_state="white robes erect and pristine; black robe hems draping onto wet granite pavement",
        damage_dirt="stone dust on Black boots and right knee; White pristine",
        held_objects=["White: straight sword held at rest", "Black: heavy broadsword tip resting on stone pavement"],
        camera_side_of_axis="south",
        screen_direction="static",
    ),
    WorldState(
        location=WORLD_INITIAL.location,
        time_of_day="cold morning sunrise",
        weather="parting clouds, gentle warm morning breeze",
        lighting="warm golden sunbeams breaking through opening clouds across terrace and sea of clouds",
        terrain=WORLD_INITIAL.terrain,
        architecture=WORLD_INITIAL.architecture,
        props_present=["four weathered stone marker pillars", "low stone balustrade", "chipped granite flagstone", "morning sunbeams breaking through clouds"],
        character_position="White: standing at East ledge sheathing blade | Black: kneeling in peace on West ledge",
        character_orientation="White: facing East toward morning horizon | Black: facing East in peace",
        wardrobe_state="white robes catching golden morning light; black robes resting peacefully in shade",
        damage_dirt="stone dust on Black boots and right knee; White pristine",
        held_objects=["White: straight sword fully sheathed in silver scabbard", "Black: heavy broadsword resting on stone pavement"],
        camera_side_of_axis="south",
        screen_direction="left-to-right",
    ),
]

NEGATIVES = [
    "no modern clothing, no modern buildings, no vehicles, no firearms,",
    "no text, no subtitles, no logos, no watermarks, no UI overlays,",
    "no third fighter, no audience, no spectators, no animals,",
    "no blood, no dismemberment, no gore, no chaotic fullscreen particle blinding,",
    "no camera crossing the 180-degree axis line, no random teleports.",
]

# -----------------------------------------------------------------------------
# 2. Xianxia Director Compiler (Specialized Film Core Director)
# -----------------------------------------------------------------------------

class XianxiaDirectorCompiler(DirectorCompiler):
    """Specialized DirectorCompiler modeling opposing two-cultivator combat grammar.

    Synchronizes ShotGraph nodes with the canonical ShotSpec combat plan,
    resolving screen direction, camera movements, and two-fighter states.
    """

    def _treat(self, beats):
        intents = []
        specs = [
            ("S01", "ESTABLISH", "WIDE", "LOCKED", "eye level", "static",
             "White on left, Black on right across misty terrace", "standing face-off tension", "CUT"),
            ("S02", "DECISION", "MEDIUM_CLOSE", "LOCKED", "eye level profile", "left-to-right",
             "White draws straight sword facing right", "smooth linear draw left-to-right", "CUT"),
            ("S03", "APPROACH", "MEDIUM", "TRACKING_LATERAL", "low angle", "right-to-left",
             "Black accelerates sprint lunge right-to-left", "rapid sprint right-to-left", "MATCH_CUT"),
            ("S04", "DISCOVER", "MEDIUM", "PUSH_IN", "eye level", "left-to-right",
             "swords collide in spark burst at center-left", "kinetic convergence into blade lock", "CUT"),
            ("S05", "REACTION", "MEDIUM", "LOCKED", "eye level", "left-to-right",
             "White sidesteps clockwise to foreground-left, Black strikes stone", "rotational sidestep evasion left-to-right", "CUT"),
            ("S06", "PRESSURE", "MEDIUM", "PUSH_IN", "eye level", "right-to-left",
             "Black thrusts left palm projecting dark qi barrier", "palm thrust projecting barrier right-to-left", "MATCH_CUT"),
            ("S07", "DISCOVER", "MEDIUM_CLOSE", "PUSH_IN", "eye level", "left-to-right",
             "White sword tip strikes and fractures qi barrier", "linear thrust left-to-right into barrier", "CUT"),
            ("S08", "DECISION", "WIDE", "LOCKED", "low angle backlit", "left-to-right",
             "White aerial leap from left to right over opponent", "aerial arc left-to-right swapping positions", "CUT"),
            ("S09", "PRESSURE", "MEDIUM", "LOCKED", "eye level", "left-to-right",
             "Black sweeps crescent blade left-to-right toward White", "rotational torque launching dark crescent left-to-right", "MATCH_CUT"),
            ("S10", "PAYOFF", "WIDE", "LOCKED", "eye level", "right-to-left",
             "White linear thrust pierces and shatters dark crescent", "immaculate linear lunge right-to-left", "CUT"),
            ("S11", "AFTERMATH", "MEDIUM", "LOCKED", "high angle", "static",
             "Black lowers sword and kneels on one knee in defeat", "slow controlled downward descent onto one knee", "CUT"),
            ("S12", "RESOLVE", "WIDE", "TRACKING_LATERAL", "eye level", "left-to-right",
             "White sheathes blade at sunrise, Black kneeling", "graceful sheathing and horizon contemplation left-to-right", "CUT"),
        ]
        for i, (sid, func, size, mov, ang, sdir, blk, mvec, tr) in enumerate(specs):
            intents.append(DirectorShotIntent(
                shot_id=sid,
                function=func,
                beat_ids=[beats[i].beat_id],
                story_purpose=beats[i].summary[:160],
                shot_size=size,
                camera_angle=ang,
                camera_movement=mov,
                blocking=blk,
                screen_direction=sdir,
                light_direction=self.light_direction,
                motion_vector=mvec,
                duration_target_s=5.0,
                transition_intent=tr,
                story_node_ids=list(beats[i].event_ids)
            ))
        return intents

    def _graph(self, intents, *, world_state, cast):
        graph = ShotGraph()
        char_states = [
            ("White: ready stance at West ledge", "Black: ready stance at East ledge"),
            ("White: drawing straight sword", "Black: observing from East ledge"),
            ("White: anchored defensive guard", "Black: sprinting lunge right-to-left"),
            ("White: upward parry in blade lock", "Black: downward cleave in blade lock"),
            ("White: evasive sidestep to foreground-left", "Black: overextended with blade in stone"),
            ("White: counter guard at foreground-left", "Black: left palm projecting dark qi barrier"),
            ("White: thrusting sword tip into barrier", "Black: bracing fractured dark qi barrier"),
            ("White: aerial leap over opponent to East ledge", "Black: barrier dissolved, beginning turn"),
            ("White: grounded at East ledge in ready guard", "Black: sweeping crescent blade from West ledge"),
            ("White: immaculate linear counter-thrust", "Black: staggered back, crescent shattered"),
            ("White: holding victorious stance on East ledge", "Black: kneeling on one knee in defeat"),
            ("White: sheathing blade at sunrise", "Black: kneeling peacefully in surrender")
        ]
        for index, intent in enumerate(intents):
            incoming = {
                "screen_direction": intent.screen_direction,
                "world": world_state.model_dump(),
                "characters": {
                    "White Cultivator": char_states[index][0],
                    "Black Cultivator": char_states[index][1]
                }
            }
            outgoing = dict(incoming)
            outgoing["last_function"] = intent.function
            continuity = [
                f"screen direction must remain {intent.screen_direction}",
                "camera must remain strictly on South side of combat axis",
                "wardrobe, weapons, and environmental damage persist unless combat changes them"
            ]
            node = ShotGraphNode(
                shot_id=intent.shot_id,
                story_purpose=intent.story_purpose,
                story_node_ids=intent.story_node_ids,
                function=intent.function,
                incoming_state=incoming,
                outgoing_state=outgoing,
                world_state=world_state.model_dump(),
                character_state={
                    "White Cultivator": char_states[index][0],
                    "Black Cultivator": char_states[index][1]
                },
                camera_intent={
                    "shot_size": intent.shot_size,
                    "angle": intent.camera_angle,
                    "movement": intent.camera_movement,
                    "screen_direction": intent.screen_direction,
                    "light_direction": intent.light_direction,
                    "duration_target_s": intent.duration_target_s
                },
                motion_intent=intent.motion_vector,
                continuity_constraints=continuity,
                duration_target_s=intent.duration_target_s,
                priority="P0" if intent.function in ("PAYOFF", "DECISION") else "P1",
                repairability="MEDIUM" if intent.shot_size in ("CLOSE", "MEDIUM_CLOSE") else "HIGH",
                provider_requirements={"duration_class": 5, "model": "free-route default", "references": "TEXT_ANCHOR_ONLY"}
            )
            graph.add_node(node)
            if index > 0:
                graph.add_edge(ShotGraphEdge(
                    src=intents[index - 1].shot_id,
                    dst=intent.shot_id,
                    kind=intent.transition_intent,
                    rationale=f"{intent.function} after {intents[index - 1].function}"
                ))
        return graph

# -----------------------------------------------------------------------------
# 3. Shot Data Definition with Strict End-to-Start Continuity
# -----------------------------------------------------------------------------

# Typed continuity state schemas (100% congruent across all 11 cuts)
C_STATES = [
    # X01 (00-05s)
    {
        "start": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "calm_standing_faceoff", "sword_state": "sheathed", "qi_state": "dormant"},
            "black_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "aggressive_standing_faceoff", "sword_state": "sheathed", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        },
        "end": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "hand_on_sword_hilt", "sword_state": "sheathed", "qi_state": "awakening"},
            "black_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "weight_shifted_forward", "sword_state": "sheathed", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        }
    },
    # X02 (05-10s)
    {
        "start": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "hand_on_sword_hilt", "sword_state": "sheathed", "qi_state": "awakening"},
            "black_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "weight_shifted_forward", "sword_state": "sheathed", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        },
        "end": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "straight_guard_at_45_degrees", "sword_state": "drawn_cleanly", "qi_state": "pale_azure_line_active"},
            "black_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "coiling_into_sprint_stance", "sword_state": "drawing_heavy_sword", "qi_state": "dark_purple_awakening"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        }
    },
    # X03 (10-15s)
    {
        "start": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "straight_guard_at_45_degrees", "sword_state": "drawn_cleanly", "qi_state": "pale_azure_line_active"},
            "black_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "coiling_into_sprint_stance", "sword_state": "drawing_heavy_sword", "qi_state": "dark_purple_awakening"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        },
        "end": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "rooted_defensive_stance", "sword_state": "sword_raised_in_parry_angle", "qi_state": "pale_azure_line_active"},
            "black_cultivator": {"position": "center_left_striking_range", "orientation": "facing_west", "pose": "sprint_lunge_reaching_apex", "sword_state": "heavy_sword_coiled_to_cleave", "qi_state": "trailing_dark_purple_smoke"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        }
    },
    # X04 (15-20s)
    {
        "start": {
            "white_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "rooted_defensive_stance", "sword_state": "sword_raised_in_parry_angle", "qi_state": "pale_azure_line_active"},
            "black_cultivator": {"position": "center_left_striking_range", "orientation": "facing_west", "pose": "sprint_lunge_reaching_apex", "sword_state": "heavy_sword_coiled_to_cleave", "qi_state": "trailing_dark_purple_smoke"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        },
        "end": {
            "white_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "bracing_rear_foot_in_blade_lock", "sword_state": "straight_sword_in_parry_lock", "qi_state": "pale_azure_sparking"},
            "black_cultivator": {"position": "center_left", "orientation": "facing_west", "pose": "two_handed_downward_power_press", "sword_state": "heavy_sword_in_cleave_lock", "qi_state": "dark_purple_sparking"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        }
    },
    # X05 (20-25s)
    {
        "start": {
            "white_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "bracing_rear_foot_in_blade_lock", "sword_state": "straight_sword_in_parry_lock", "qi_state": "pale_azure_sparking"},
            "black_cultivator": {"position": "center_left", "orientation": "facing_west", "pose": "two_handed_downward_power_press", "sword_state": "heavy_sword_in_cleave_lock", "qi_state": "dark_purple_sparking"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "intact"}
        },
        "end": {
            "white_cultivator": {"position": "foreground_left", "orientation": "facing_east", "pose": "low_evasion_stance", "sword_state": "straight_sword_leveled_at_flank", "qi_state": "pale_azure_ready"},
            "black_cultivator": {"position": "center_overextended", "orientation": "facing_west", "pose": "overextended_lurch", "sword_state": "heavy_sword_struck_in_flagstone", "qi_state": "dark_purple_flickering"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        }
    },
    # X06 (25-30s)
    {
        "start": {
            "white_cultivator": {"position": "foreground_left", "orientation": "facing_east", "pose": "low_evasion_stance", "sword_state": "straight_sword_leveled_at_flank", "qi_state": "pale_azure_ready"},
            "black_cultivator": {"position": "center_overextended", "orientation": "facing_west", "pose": "overextended_lurch", "sword_state": "heavy_sword_struck_in_flagstone", "qi_state": "dark_purple_flickering"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "foreground_left", "orientation": "facing_east", "pose": "stepping_into_linear_advance", "sword_state": "straight_sword_coiled_to_thrust", "qi_state": "pale_azure_concentrating"},
            "black_cultivator": {"position": "center_right", "orientation": "facing_west", "pose": "left_palm_extended_rear_guard", "sword_state": "heavy_sword_at_right_hip", "qi_state": "dark_purple_channeling_to_palm"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "solid_crystalline_disc", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        }
    },
    # X07 (30-35s)
    {
        "start": {
            "white_cultivator": {"position": "foreground_left", "orientation": "facing_east", "pose": "stepping_into_linear_advance", "sword_state": "straight_sword_coiled_to_thrust", "qi_state": "pale_azure_concentrating"},
            "black_cultivator": {"position": "center_right", "orientation": "facing_west", "pose": "left_palm_extended_rear_guard", "sword_state": "heavy_sword_at_right_hip", "qi_state": "dark_purple_channeling_to_palm"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "solid_crystalline_disc", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "lunging_thrust_held", "sword_state": "sword_tip_embedded_in_barrier", "qi_state": "pale_azure_concentrated_at_tip"},
            "black_cultivator": {"position": "center_right", "orientation": "facing_west", "pose": "bracing_rear_leg_under_impact", "sword_state": "heavy_sword_at_right_hip", "qi_state": "dark_purple_strained"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "spiderweb_fractured", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        }
    },
    # X08 (35-40s) — Clean Positional Inversion
    {
        "start": {
            "white_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "lunging_thrust_held", "sword_state": "sword_tip_embedded_in_barrier", "qi_state": "pale_azure_concentrated_at_tip"},
            "black_cultivator": {"position": "center_right", "orientation": "facing_west", "pose": "bracing_rear_leg_under_impact", "sword_state": "heavy_sword_at_right_hip", "qi_state": "dark_purple_strained"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "spiderweb_fractured", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "low_balanced_landing_crouch", "sword_state": "tucked_along_forearm", "qi_state": "pale_azure_dormant"},
            "black_cultivator": {"position": "center_left", "orientation": "pivoting_toward_east", "pose": "mid_turn_recovering", "sword_state": "heavy_sword_held_in_two_hands", "qi_state": "dark_purple_coiling_for_sweep"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "dissolved", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        }
    },
    # X09 (40-45s)
    {
        "start": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "low_balanced_landing_crouch", "sword_state": "tucked_along_forearm", "qi_state": "pale_azure_dormant"},
            "black_cultivator": {"position": "center_left", "orientation": "pivoting_toward_east", "pose": "mid_turn_recovering", "sword_state": "heavy_sword_held_in_two_hands", "qi_state": "dark_purple_coiling_for_sweep"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "dissolved", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "rooted_defensive_stance", "sword_state": "straight_sword_ready_guard", "qi_state": "pale_azure_concentrating_at_point"},
            "black_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "horizontal_sweep_follow_through", "sword_state": "heavy_sword_pointed_forward_right", "qi_state": "expended_into_projectile"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "flying_crescent_left_to_right", "pavement_state": "chipped_at_center"}
        }
    },
    # X10 (45-50s)
    {
        "start": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "rooted_defensive_stance", "sword_state": "straight_sword_ready_guard", "qi_state": "pale_azure_concentrating_at_point"},
            "black_cultivator": {"position": "center_left", "orientation": "facing_east", "pose": "horizontal_sweep_follow_through", "sword_state": "heavy_sword_pointed_forward_right", "qi_state": "expended_into_projectile"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "flying_crescent_left_to_right", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "full_orthodox_lunging_thrust", "sword_state": "straight_sword_extended_horizontal", "qi_state": "white_azure_beam_piercing"},
            "black_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "staggered_backward_reeling", "sword_state": "heavy_sword_knocked_aside_low", "qi_state": "empty"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "shattered_into_grey_vapor", "pavement_state": "chipped_at_center"}
        }
    },
    # X11 (50-55s)
    {
        "start": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "full_orthodox_lunging_thrust", "sword_state": "straight_sword_extended_horizontal", "qi_state": "white_azure_beam_piercing"},
            "black_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "staggered_backward_reeling", "sword_state": "heavy_sword_knocked_aside_low", "qi_state": "empty"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "shattered_into_grey_vapor", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "standing_erect_at_rest", "sword_state": "straight_sword_lowered", "qi_state": "calm_harmonic"},
            "black_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "kneeling_on_right_knee_bowed", "sword_state": "heavy_sword_tip_resting_on_stone", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        }
    },
    # X12 (55-60s)
    {
        "start": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_west", "pose": "standing_erect_at_rest", "sword_state": "straight_sword_lowered", "qi_state": "calm_harmonic"},
            "black_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "kneeling_on_right_knee_bowed", "sword_state": "heavy_sword_tip_resting_on_stone", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "chipped_at_center"}
        },
        "end": {
            "white_cultivator": {"position": "east_ledge_screen_right", "orientation": "facing_east", "pose": "standing_peaceful_contemplation", "sword_state": "fully_sheathed_in_silver_scabbard", "qi_state": "dormant"},
            "black_cultivator": {"position": "west_ledge_screen_left", "orientation": "facing_east", "pose": "kneeling_peaceful_surrender", "sword_state": "heavy_sword_resting_on_stone", "qi_state": "dormant"},
            "arena": {"camera_side_of_axis": "south", "barrier_state": "none", "energy_projectile": "none", "pavement_state": "chipped_at_center_illuminated_by_sunbeams"}
        }
    }
]

SHOTS_RAW = [
    {
        "shot_id": "X01",
        "dramatic_purpose": "Establish the high-mountain terrace arena, sea of clouds atmosphere, and initial face-off confrontation between the two sword cultivators.",
        "duration_target_s": 5.0,
        "shot_type": "establishing",
        "camera": {
            "framing": "WS", "height": "eye_level", "lens_intent": "wide", "focal_hint_mm": 24.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "White cultivator stands motionless at screen-left foreground; Black cultivator stands motionless at screen-right midground, 15 paces apart across the misty terrace.",
            "action_beats": [
                "Gentle mountain breeze ripples white and black robe hems",
                "Thin mist drifts low across ancient dark stone pavers between both figures",
                "Both duelists remain completely still, hands resting near weapon hilts, locked in intense pre-combat evaluation"
            ],
            "end": "Static face-off tension established; arena boundaries and sea of clouds clearly readable.",
            "prop_interactions": []
        },
        "performance": {
            "observable_beats": [
                "Controlled calm breathing visible in cold air",
                "Unwavering mutual eyeline across horizontal axis"
            ],
            "forbidden": ["fidgeting", "premature weapon drawing", "walking toward each other"]
        },
        "lighting": {
            "key_direction": "north_east_clouds", "contrast": "medium_soft",
            "notes": "Luminous cloudlight backlighting terrace edge, diffuse ambient fill on dark stone"
        },
        "continuity": {
            "screen_direction": "static",
            "eyeline": "across_axis_horizontal",
            "start_state": C_STATES[0]["start"],
            "end_state": C_STATES[0]["end"],
            "previous_shot_id": None,
            "critical_invariants": [
                "White cultivator strictly screen-left, Black cultivator strictly screen-right",
                "Camera strictly on South side of combat axis looking North",
                "Sea of clouds visible beyond low balustrade",
                "No third character in frame"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "high mountain wind, gentle steady breeze, distant atmospheric hum",
            "sfx_intent": "soft fabric fluttering, low ambient tension drone"
        },
        "editorial": {"cut_purpose": "establish duel geography", "handles_s": 0.25, "pickup_priority": "normal"},
        "performance_spec": {
            "primary_action": "static martial duel confrontation stance with rising internal tension",
            "anticipation": "Duelists settle weight firmly onto balls of feet; fingers curl gently over scabbards.",
            "locomotion": "stationary",
            "weight_transfer": "balanced 50-50 weight distribution on both legs",
            "foot_plant": "stable shoulder-width martial stance on dark granite flagstones",
            "hip_torso_rotation": "torso angled three-quarters toward opponent",
            "arm_countermotion": "minimal, left hand steadying scabbard at hip",
            "contact_event": "none",
            "reaction": "heightened sensory alertness",
            "recovery": "sustained readiness",
            "secondary_motion": "robe hems and headband ribbons fluttering in the steady breeze",
            "motion_energy": "low",
            "motion_risk_class": "LOW",
            "beats": [
                {"label": "settle_stance", "description": "both duelists lock stance on stone pavers", "approx_start_s": 0.0},
                {"label": "tension_hold", "description": "wind and mist drift between standing silhouettes", "approx_start_s": 2.5}
            ]
        },
        "action_intent": {
            "trigger": "arrival at the designated duel ground above the clouds",
            "perception": "each duelist assesses the other's posture, breath, and weapon balance",
            "character_goal": "establish spatial control and evaluate opponent's opening vector",
            "motivation": "Daoist martial honor and high-stakes duel resolution",
            "obstacle_or_pressure": "imminent threat of lethal engagement across open stone",
            "chosen_action": "hold motionless ready stance to force the first psychological tell",
            "intended_outcome": "force opponent to commit to an opening vector",
            "resulting_state": "tactical standoff locked across the 180-degree axis",
            "next_decision": "White cultivator decides to unsheathe straight blade",
            "visual_legibility_requirements": ["two distinct silhouettes separated by open space", "clear cloud backdrop", "no occlusion"],
            "stakes": "life, death, and martial path",
            "urgency": "controlled anticipation",
            "knowledge_state": "both know only one will walk away uncontested"
        }
    },
    {
        "shot_id": "X02",
        "dramatic_purpose": "White cultivator commits to the duel; smoothly unsheathes slender straight sword, revealing a razor-thin line of pale azure qi.",
        "duration_target_s": 5.0,
        "shot_type": "insert",
        "camera": {
            "framing": "MCU", "height": "eye_level", "lens_intent": "normal", "focal_hint_mm": 50.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "White cultivator framed from chest up in profile facing screen-right; right hand rests on silver sword hilt.",
            "action_beats": [
                "Right fingers tighten smoothly around silver-wrapped sword hilt",
                "Draws the straight double-edged blade from scabbard with a crisp linear draw facing screen-right",
                "A faint, razor-thin line of pale azure qi ignites along the blade cutting edge as it clears the scabbard mouth"
            ],
            "end": "Straight sword held stationary at 45-degree ready guard pointing toward screen-right; pale qi hums faintly.",
            "prop_interactions": ["straight steel sword", "silver-mounted scabbard"]
        },
        "performance": {
            "observable_beats": [
                "Single smooth unbroken weapon draw",
                "Calm unwavering gaze focused ahead toward screen-right",
                "Relaxed neck and dropped shoulders demonstrating disciplined poise"
            ],
            "forbidden": ["jerky movement", "flourishing or spinning blade", "angry facial grimace"]
        },
        "lighting": {
            "key_direction": "screen_right_ambient", "contrast": "medium",
            "notes": "Cold metallic reflection along blade ridge; pale azure rim light on white silk collar"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "screen_right",
            "start_state": C_STATES[1]["start"],
            "end_state": C_STATES[1]["end"],
            "previous_shot_id": "X01",
            "critical_invariants": [
                "White cultivator facing screen-right on South camera axis",
                "White robes with silver cloud embroidery",
                "Slender straight double-edged blade (orthodox Daoist jian)"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain breeze, subtle distant mist roar",
            "sfx_intent": "crisp metallic ring of steel sliding from scabbard, followed by a faint crystalline qi harmonic hum"
        },
        "editorial": {"cut_purpose": "weapon commitment insert", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "smooth linear unsheathing of orthodox straight sword",
            "anticipation": "Right thumb nudges sword guard 1 inch free with clean tactile release.",
            "locomotion": "stationary",
            "weight_transfer": "slight 5% shift to rear foot to anchor weapon extension",
            "foot_plant": "grounded lead left foot, rear right foot stabilizing",
            "hip_torso_rotation": "torso stays locked in strict side profile facing screen-right",
            "arm_countermotion": "left hand holds scabbard firmly at hip as right arm draws back and extends forward",
            "contact_event": "blade clears scabbard throat collar",
            "reaction": "blade tip stops precisely at eye level",
            "recovery": "grip locks into balanced four-finger sword hold",
            "secondary_motion": "sleeve cuffs settle smoothly after draw",
            "motion_energy": "moderate",
            "motion_risk_class": "LOW",
            "beats": [
                {"label": "grip_tighten", "description": "hand closes on hilt and thumb pops guard", "approx_start_s": 0.5},
                {"label": "blade_draw", "description": "blade slides out cleanly reflecting cold light", "approx_start_s": 1.5},
                {"label": "guard_lock", "description": "blade tip locks at 45 degrees, pale qi hums", "approx_start_s": 3.2}
            ]
        },
        "action_intent": {
            "trigger": "standoff reaches moment of commitment",
            "perception": "White cultivator senses Black cultivator gathering kinetic momentum",
            "character_goal": "ready weapon with minimal wasted energy and signal non-hostile readiness",
            "motivation": "disciplined Daoist swordsmanship: defense before offense",
            "obstacle_or_pressure": "high-speed impending assault from challenger",
            "chosen_action": "unhurried orthodox draw to establish center-line defense",
            "intended_outcome": "weapon in hand, qi channeled to blade edge, ready for first contact",
            "resulting_state": "active defensive readiness",
            "next_decision": "brace for incoming sprint charge",
            "visual_legibility_requirements": ["clean sword draw without hand warping", "readable straight blade geometry", "subtle pale qi line"],
            "stakes": "readiness before impact",
            "urgency": "calm immediate",
            "knowledge_state": "White cultivator knows Black cultivator favours aggressive lunges"
        }
    },
    {
        "shot_id": "X03",
        "dramatic_purpose": "Black cultivator launches the duel's first offensive, accelerating across the stone axis in an aggressive forward sprint.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "MS", "height": "low", "lens_intent": "wide", "focal_hint_mm": 35.0,
            "movement": {"type": "tracking", "purpose": "lateral tracking right to left matching sprint lunge", "timing": "entire 5s"}
        },
        "blocking": {
            "start": "Black cultivator framed in medium shot sprinting right-to-left across the dark granite flagstones.",
            "action_beats": [
                "Heavy combat boots drive powerfully into wet flagstones, kicking up faint mist droplets",
                "Right hand trails heavy dark sword low behind rear hip in a trailing strike guard",
                "Dark layered robes and loose hair whip violently in the aerodynamic slipstream as he accelerates across center"
            ],
            "end": "Black cultivator enters close striking distance near frame-center, tensing core to launch downward cleave.",
            "prop_interactions": ["heavy dark steel sword"]
        },
        "performance": {
            "observable_beats": [
                "Aggressive forward-canted torso posture (25 degrees)",
                "Fierce locked eyeline toward screen-left target",
                "Powerful athletic leg drive and grounded footing"
            ],
            "forbidden": ["floating or flying without leg drive", "stumbling", "aimless weapon waving"]
        },
        "lighting": {
            "key_direction": "north_clouds_rim", "contrast": "high",
            "notes": "Low-angle rim light catching flying droplets and edges of black leather shoulder guard"
        },
        "continuity": {
            "screen_direction": "right-to-left",
            "eyeline": "screen_left",
            "start_state": C_STATES[2]["start"],
            "end_state": C_STATES[2]["end"],
            "previous_shot_id": "X02",
            "critical_invariants": [
                "Travel direction strictly right-to-left on South camera axis",
                "Black robes with obsidian leather shoulder guards",
                "Dark straight-broad sword held in trailing right hand"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "rushing wind",
            "sfx_intent": "heavy resonant boot stomps on stone pavers, whooshing heavy wool fabric, low predatory growl of dark qi resonance"
        },
        "editorial": {"cut_purpose": "dynamic approach attack", "handles_s": 0.25, "pickup_priority": "normal"},
        "performance_spec": {
            "primary_action": "explosive sprint lunge right-to-left trailing broadsword",
            "anticipation": "Deep plantar push-off from rear foot; torso drops forward to drive momentum.",
            "locomotion": "rapid athletic sprint across stone",
            "weight_transfer": "aggressive forward weight transfer on each stride",
            "foot_plant": "heavy heel-to-ball strike of dark leather combat boots on granite",
            "hip_torso_rotation": "hips drive linear forward, right shoulder slightly back trailing weapon",
            "arm_countermotion": "left arm pumps forward for counter-balance as right arm holds trailing sword",
            "contact_event": "boots striking wet stone flags",
            "reaction": "surging forward velocity",
            "recovery": "transition into striking plant stance",
            "secondary_motion": "charcoal robe hems and tied hair whip backward in motion wake",
            "motion_energy": "high",
            "motion_risk_class": "MEDIUM",
            "beats": [
                {"label": "sprint_burst", "description": "explosive acceleration across flagstones", "approx_start_s": 0.5},
                {"label": "stride_momentum", "description": "three powerful strides trailing dark sword", "approx_start_s": 2.0},
                {"label": "strike_coil", "description": "coiling torso to unleash strike", "approx_start_s": 4.0}
            ]
        },
        "action_intent": {
            "trigger": "seeing White cultivator draw weapon",
            "perception": "Black cultivator spots opening distance to bridge before opponent establishes defensive ward",
            "character_goal": "close distance instantaneously and crush opponent's guard with heavy downward cleave",
            "motivation": "overwhelm the orthodox sword cultivator with raw speed and kinetic force",
            "obstacle_or_pressure": "distance across open terrace",
            "chosen_action": "high-speed sprint into heavy downward slash",
            "intended_outcome": "break White cultivator's stance on first contact",
            "resulting_state": "entering close quarters combat range",
            "next_decision": "execute overhead cleave at close range",
            "visual_legibility_requirements": ["readable running biomechanics", "clear right-to-left motion vector", "sword held securely in hand"],
            "stakes": "seizing the offensive initiative",
            "urgency": "maximum attack velocity",
            "knowledge_state": "confident in superior physical weight and blade mass"
        }
    },
    {
        "shot_id": "X04",
        "dramatic_purpose": "First violent sword clash; blades lock in midair at center-left with bursting sparks and localized kinetic shockwave.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "TWO_SHOT", "height": "eye_level", "lens_intent": "wide", "focal_hint_mm": 35.0,
            "movement": {"type": "dolly_in", "purpose": "push into sword collision point", "timing": "first 2s push then lock"}
        },
        "blocking": {
            "start": "Black cultivator's downward diagonal cleave meets White cultivator's upward angled straight sword parry at center-left.",
            "action_beats": [
                "Steel collides violently with steel at frame-center-left, producing a brilliant burst of gold-white sparks",
                "A tight, translucent radial shock ring blasts outward, parting low mist along the pavement",
                "White cultivator's left fingers brace the flat of his blade; his boots slide back two inches under the heavy impact",
                "Blades remain locked edge-to-edge as both fighters exert opposing physical and qi pressure"
            ],
            "end": "Tense sword lock sustained; intense eye contact through the shower of dying sparks.",
            "prop_interactions": ["colliding swords", "metal blade lock"]
        },
        "performance": {
            "observable_beats": [
                "Sudden deceleration from high sprint to dead stop",
                "Muscles in forearms and shoulders strained under heavy blade pressure",
                "White cultivator's jaw tenses in disciplined absorption; Black cultivator's teeth grit in aggressive push"
            ],
            "forbidden": ["rubber swords or bending blades", "teleporting positions", "swords passing through bodies"]
        },
        "lighting": {
            "key_direction": "contact_point_sparks", "contrast": "high",
            "notes": "Sharp specular flash from spark burst illuminating faces, surrounded by cold morning sky"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "mutual_lock",
            "start_state": C_STATES[3]["start"],
            "end_state": C_STATES[3]["end"],
            "previous_shot_id": "X03",
            "critical_invariants": [
                "White cultivator on screen-left, Black cultivator on screen-right",
                "Contact point localized at center-left of frame on South camera axis",
                "Both swords intact and physically legible"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain air",
            "sfx_intent": "thunderous metallic crack of high-carbon steel clashing, sharp sizzling of sparks, low bass kinetic thud of shockwave"
        },
        "editorial": {"cut_purpose": "first combat climax", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "violent blade-to-blade clash and sustained isometric lock",
            "anticipation": "White cultivator sets rear foot into granite seam; Black cultivator drops entire body weight into downward swing.",
            "locomotion": "abrupt kinetic deceleration into braced lock",
            "weight_transfer": "Black transfers 80% weight forward-down; White absorbs 70% into rear rooted leg",
            "foot_plant": "White boots skid 2 inches leaving faint wet friction tracks; Black boots plant firmly",
            "hip_torso_rotation": "White rotates shoulders 30 degrees to deflect vector; Black squares shoulders downward",
            "arm_countermotion": "White left hand supports blade spine with flat fingers; Black grips hilt two-handed",
            "contact_event": "hard steel-on-steel collision at center-left",
            "reaction": "vibrational tremor traveling through both weapon hilts into wrists",
            "recovery": "stiffening core into isometric resistance",
            "secondary_motion": "robe hems billow radially from the kinetic shockwave ring",
            "motion_energy": "high",
            "motion_risk_class": "HIGH",
            "beats": [
                {"label": "blade_impact", "description": "swords meet with explosive spark eruption", "approx_start_s": 0.8},
                {"label": "shockwave_burst", "description": "translucent ring blows mist outward", "approx_start_s": 1.2},
                {"label": "isometric_lock", "description": "sustained grinding blade lock", "approx_start_s": 2.5}
            ]
        },
        "action_intent": {
            "trigger": "Black cultivator completes sprint cleave",
            "perception": "White cultivator tracks blade path and calculates exact deflection angle",
            "character_goal": "White: deflect lethal cleave without breaking blade; Black: overwhelm guard with sheer weight",
            "motivation": "survival vs domination",
            "obstacle_or_pressure": "crushing downward kinetic energy",
            "chosen_action": "White: high angled parry supported by offhand; Black: two-handed power press",
            "intended_outcome": "White: arrest momentum and seek disengagement; Black: crush White to knees",
            "resulting_state": "temporary deadlock with high stored kinetic energy",
            "next_decision": "White must disengage and pivot before Black leverages weight advantage",
            "visual_legibility_requirements": ["sharp anatomically sound hand positions", "clear blade intersection point", "no limb merging"],
            "stakes": "integrity of weapon and defensive stance",
            "urgency": "extreme immediate",
            "knowledge_state": "White realizes Black possesses heavier blade; Black realizes White's defense is perfectly anchored"
        }
    },
    {
        "shot_id": "X05",
        "dramatic_purpose": "White cultivator executes an evasive rotational sidestep, causing Black's follow-up cleave to strike empty stone.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "MS", "height": "eye_level", "lens_intent": "wide", "focal_hint_mm": 35.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "Blade lock dissolves as White cultivator disengages his blade with a subtle wrist roll.",
            "action_beats": [
                "White cultivator pivots fluidly on his left heel, stepping smoothly toward foreground-left",
                "Black cultivator's heavy downward follow-through slash cleaves empty air where White stood a split-second earlier",
                "Black's sword strikes the granite flagstone, chipping stone dust and sending sparks flying across the pavement",
                "White cultivator settles into a low coiled evasion stance on foreground-left, sword leveled at Black's exposed flank"
            ],
            "end": "White cultivator poised in clean counter-ready stance; Black cultivator overextended facing left.",
            "prop_interactions": ["sword striking stone pavement"]
        },
        "performance": {
            "observable_beats": [
                "Fluid rotational body evasion by White cultivator",
                "Overextended torso lurch by Black cultivator as blade hits stone",
                "Immediate defensive recovery by White duelist"
            ],
            "forbidden": ["clumsy slipping", "flying away unrealistically", "instant teleportation"]
        },
        "lighting": {
            "key_direction": "north_clouds", "contrast": "medium",
            "notes": "Diffuse cold daylight catching stone chips and swirling mist around White's pivoting foot"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "screen_right",
            "start_state": C_STATES[4]["start"],
            "end_state": C_STATES[4]["end"],
            "previous_shot_id": "X04",
            "critical_invariants": [
                "White cultivator sidesteps toward foreground-left on South camera axis",
                "Black cultivator overextends toward left-down",
                "Stone pavement chipped at impact point"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain wind",
            "sfx_intent": "whistling blade cutting air, sharp jarring clack of heavy steel biting granite pavement, stone fragments scattering"
        },
        "editorial": {"cut_purpose": "evasion counter dynamic", "handles_s": 0.25, "pickup_priority": "normal"},
        "performance_spec": {
            "primary_action": "rotational sidestep evasion and grounded counter-orientation",
            "anticipation": "White cultivator yields 1 inch on the blade lock, rolling wrist to guide Black's blade outward.",
            "locomotion": "single rotational martial step (Bát Quái / Bagua footwork)",
            "weight_transfer": "weight transfers smoothly from center to left heel, pivoting 45 degrees",
            "foot_plant": "left heel pivots smoothly; right foot plants firmly in low foreground horse stance",
            "hip_torso_rotation": "torso rotates 45 degrees away from blade trajectory, drawing robes clear of strike",
            "arm_countermotion": "sword arm retracts in tight circular arc, keeping blade aligned to opponent",
            "contact_event": "Black cultivator's sword tip strikes granite flagstone",
            "reaction": "Black's arms jar from hitting solid stone; White maintains relaxed breathing",
            "recovery": "White immediately stabilizes ready to thrust",
            "secondary_motion": "white robe hems flare in a clean circle during the pivot",
            "motion_energy": "moderate",
            "motion_risk_class": "MEDIUM",
            "beats": [
                {"label": "disengage_pivot", "description": "wrist roll and rotational step", "approx_start_s": 0.4},
                {"label": "stone_impact", "description": "black blade cleaves empty air and strikes stone", "approx_start_s": 1.8},
                {"label": "counter_set", "description": "white settles into low counter stance", "approx_start_s": 3.2}
            ]
        },
        "action_intent": {
            "trigger": "Black cultivator commits excessive forward weight to break lock",
            "perception": "White cultivator feels the unbalanced vector through the crossed blades",
            "character_goal": "White: use opponent's momentum against him; Black: salvage balance before counter arrives",
            "motivation": "Daoist principle: deflect hardness with softness",
            "obstacle_or_pressure": "narrow margin of error to evade heavy blade",
            "chosen_action": "yield center line and step off-axis",
            "intended_outcome": "leave opponent overextended and open to counter-thrust",
            "resulting_state": "tactical advantage to White cultivator",
            "next_decision": "White prepares counter-thrust; Black must deploy defensive qi",
            "visual_legibility_requirements": ["clear separation between characters after pivot", "visible stone impact", "no tangled limbs"],
            "stakes": "turning defense into offense",
            "urgency": "split-second timing",
            "knowledge_state": "Black realizes his cleave was baited into the stone"
        }
    },
    {
        "shot_id": "X06",
        "dramatic_purpose": "Black cultivator checks White's counter-momentum by thrusting his left palm forward, generating a dark crystalline qi barrier.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "MS", "height": "eye_level", "lens_intent": "normal", "focal_hint_mm": 50.0,
            "movement": {"type": "dolly_in", "purpose": "dolly in on qi barrier", "timing": "first 2s"}
        },
        "blocking": {
            "start": "Black cultivator recoils from overextension, yanking his heavy sword free from the stone pavement.",
            "action_beats": [
                "Left hand thrusts forward facing screen-left with fingers tensed in a clawed palm strike",
                "A circular disc of translucent dark-purple crystalline qi (3 feet diameter) condenses 2 feet ahead of his palm",
                "Dark smoky energy ripples outward along the perimeter of the barrier, arresting White cultivator's advance"
            ],
            "end": "Dark qi barrier fully established between duelists; Black cultivator recovers balance behind it.",
            "prop_interactions": ["manifested dark qi barrier"]
        },
        "performance": {
            "observable_beats": [
                "Sharp explosive palm extension",
                "Tense facial concentration as internal qi is projected externally",
                "Right hand recovers heavy sword to ready flank position"
            ],
            "forbidden": ["comic energy blasts", "flame or explosion effects", "body turning into smoke"]
        },
        "lighting": {
            "key_direction": "barrier_dark_violet", "contrast": "high",
            "notes": "Dark purple internal luminescence emanating from qi barrier casting violet highlights on Black's face"
        },
        "continuity": {
            "screen_direction": "right-to-left",
            "eyeline": "screen_left",
            "start_state": C_STATES[5]["start"],
            "end_state": C_STATES[5]["end"],
            "previous_shot_id": "X05",
            "critical_invariants": [
                "Black cultivator facing screen-left on South camera axis",
                "Barrier disc positioned between fighters (approx 3 feet diameter)",
                "Translucent dark purple crystalline texture with smoky edges"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain wind",
            "sfx_intent": "deep resonant whoosh of projected qi, followed by a glass-like crystalline resonance as the barrier solidifies"
        },
        "editorial": {"cut_purpose": "defensive qi intervention", "handles_s": 0.25, "pickup_priority": "normal"},
        "performance_spec": {
            "primary_action": "explosive palm thrust projecting crystalline dark qi barrier",
            "anticipation": "Black pulls left hand to waist, gathering core breath before snapping palm forward.",
            "locomotion": "recoil step backward into rear guard stance",
            "weight_transfer": "shifts weight onto rear right leg to brace palm projection",
            "foot_plant": "rear foot wedges firmly against granite flagstone ridge",
            "hip_torso_rotation": "torso squares toward screen-left as left palm punches forward",
            "arm_countermotion": "right arm retracts heavy sword to hip; left arm locks out at elbow with tensed palm",
            "contact_event": "internal qi condensing into physical barrier plane",
            "reaction": "minor recoil through left shoulder as barrier anchors in air",
            "recovery": "holds steady qi channel from palm to barrier",
            "secondary_motion": "dark sleeve fabric ripples backward from palm shockwave",
            "motion_energy": "moderate",
            "motion_risk_class": "MEDIUM",
            "beats": [
                {"label": "palm_strike", "description": "explosive palm thrust toward screen-left", "approx_start_s": 0.5},
                {"label": "barrier_manifest", "description": "translucent purple crystalline disc forms", "approx_start_s": 1.8},
                {"label": "lock_shield", "description": "barrier stabilizes holding White cultivator at bay", "approx_start_s": 3.5}
            ]
        },
        "action_intent": {
            "trigger": "White cultivator poised for counter-thrust following evasion",
            "perception": "Black cultivator recognizes physical blade parry is too slow to intercept White's thrust",
            "character_goal": "manifest instant defensive barrier to block White's line of attack",
            "motivation": "prevent fatal puncture to exposed flank",
            "obstacle_or_pressure": "incoming sword counter",
            "chosen_action": "U Minh palm barrier (Hộ Thể Khí Điệp)",
            "intended_outcome": "arrest White's blade and buy time to reset footing",
            "resulting_state": "barrier deployed between fighters",
            "next_decision": "prepare counter-strike while White is halted by barrier",
            "visual_legibility_requirements": ["clearly localized qi disc geometry", "translucency showing Black behind it", "no screen clutter"],
            "stakes": "intercepting counter-attack",
            "urgency": "instantaneous defense",
            "knowledge_state": "confident the crystalline qi shield can absorb multiple sword impacts"
        }
    },
    {
        "shot_id": "X07",
        "dramatic_purpose": "White cultivator's thrust strikes the dark qi barrier; fracture lines flare, revealing structural stress.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "MCU", "height": "eye_level", "lens_intent": "normal", "focal_hint_mm": 50.0,
            "movement": {"type": "dolly_in", "purpose": "push in on barrier fracture point", "timing": "first 2s"}
        },
        "blocking": {
            "start": "White cultivator executes a precise straight thrust with his orthodox sword pointing toward screen-right.",
            "action_beats": [
                "Sharp sword tip impacts dead-center of the translucent dark purple crystalline barrier",
                "Kinetic shock ripples across the barrier surface; azure and violet sparks spray outward at the contact point",
                "Spiderweb fracture lines flare brightly within the dark crystalline matrix, spreading 6 inches from the tip",
                "Blade flexes slightly under resistance; White cultivator holds maximum linear thrust pressure"
            ],
            "end": "Sword tip lodged into the barrier surface; fracture lines crackling with unstable energy.",
            "prop_interactions": ["sword tip contacting qi barrier"]
        },
        "performance": {
            "observable_beats": [
                "Locked right wrist and perfectly straight thrusting arm alignment",
                "Left hand formed into traditional Daoist sword-finger behind ear for balance",
                "Calm focused gaze tracking the fracture propagation in the shield"
            ],
            "forbidden": ["sword shattering", "flame eruption", "comic sound effect visualizers"]
        },
        "lighting": {
            "key_direction": "contact_point_fractures", "contrast": "high",
            "notes": "Sharp azure and violet specular highlights tracing along fracture cracks across the barrier"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "screen_right",
            "start_state": C_STATES[6]["start"],
            "end_state": C_STATES[6]["end"],
            "previous_shot_id": "X06",
            "critical_invariants": [
                "Thrust vector strictly left-to-right on South camera axis",
                "Barrier disc positioned center-right",
                "Sword blade straight and unbroken"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain wind",
            "sfx_intent": "sharp high-frequency glass-like pierce, crackling static electrical sparks, strained metallic resonance of flexing steel"
        },
        "editorial": {"cut_purpose": "barrier stress reveal", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "linear sword thrust impacting qi barrier and causing structural fracture",
            "anticipation": "Linear drive from rear foot through hip, shoulder, and elbow into straight sword tip.",
            "locomotion": "single forward lunging step",
            "weight_transfer": "70% weight driven forward into lead right foot",
            "foot_plant": "lead foot plants firmly facing forward; rear heel rooted",
            "hip_torso_rotation": "torso narrowed to minimize profile, shoulders locked in thrust vector",
            "arm_countermotion": "left arm sweeps back in traditional sword-finger counterbalance",
            "contact_event": "steel sword tip impacts dark crystalline qi matrix",
            "reaction": "minor backward shockwave traveling along blade into wrist",
            "recovery": "wrist locks solid, maintaining point pressure",
            "secondary_motion": "white sleeve cuffs ripple forward with momentum",
            "motion_energy": "moderate",
            "motion_risk_class": "MEDIUM",
            "beats": [
                {"label": "sword_strike", "description": "blade tip impacts barrier surface", "approx_start_s": 0.6},
                {"label": "fracture_spread", "description": "spiderweb cracks glow and radiate outward", "approx_start_s": 1.8},
                {"label": "pressure_sustain", "description": "sustained point force testing shield integrity", "approx_start_s": 3.2}
            ]
        },
        "action_intent": {
            "trigger": "Black cultivator projects defensive palm barrier",
            "perception": "White cultivator recognizes barrier has single focal density at center",
            "character_goal": "test structural strength of the dark barrier with concentrated point penetration",
            "motivation": "find weakness in opponent's defensive technique",
            "obstacle_or_pressure": "dense crystalline energy resistance",
            "chosen_action": "Thanh Vân point-thrust (Thanh Vân Nhất Điểm)",
            "intended_outcome": "create structural fractures and destabilize barrier",
            "resulting_state": "barrier compromised, ready to shatter on next maneuver",
            "next_decision": "disengage and use aerial mobility rather than grinding into shield",
            "visual_legibility_requirements": ["clear point of contact", "physically localized fractures", "sharp blade definition"],
            "stakes": "penetrating opponent's magical defense",
            "urgency": "sustained high pressure",
            "knowledge_state": "White perceives barrier will collapse under another focused attack"
        }
    },
    # X08 (35-40s) — The Clean Aerial Positional Inversion
    {
        "shot_id": "X08",
        "dramatic_purpose": "White cultivator disengages from barrier resistance and performs a high aerial leap, arcing cleanly past opponent through backlit mist to invert screen positions.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "WS", "height": "low", "lens_intent": "wide", "focal_hint_mm": 28.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "White cultivator retracts sword tip from the fractured barrier, coiling legs for upward leap.",
            "action_beats": [
                "Kicks off the granite pavers, launching body into an elegant horizontal aerial arc through the air",
                "Travels smoothly from screen-left toward screen-right above Black cultivator's head height",
                "Silhouette beautifully backlit against opening morning clouds, white robes billowing like crane wings",
                "Lands softly on the balls of both feet at screen-right midground, pivoting instantly to face back toward left"
            ],
            "end": "White cultivator grounded on screen-right; duel positions inverted across the arena.",
            "prop_interactions": []
        },
        "performance": {
            "observable_beats": [
                "Graceful aerodynamic leap with sword tucked along forearm",
                "Effortless silent landing with knees flexing into balanced crouch",
                "Instant pivot maintaining combat awareness"
            ],
            "forbidden": ["acrobatic tumbling or wire-work spinning", "loss of silhouette clarity", "distorted anatomy in air"]
        },
        "lighting": {
            "key_direction": "backlit_clouds_morning", "contrast": "high",
            "notes": "Strong rim light outlining white cultivator silhouette against bright morning mist"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "screen_left",
            "start_state": C_STATES[7]["start"],
            "end_state": C_STATES[7]["end"],
            "previous_shot_id": "X07",
            "critical_invariants": [
                "Flight arc strictly left-to-right on South camera axis",
                "Tactical positions smoothly inverted (White now on East ledge screen-right, Black on West ledge screen-left)",
                "Camera maintains South vantage looking North at mountain clouds without crossing axis"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "high altitude wind",
            "sfx_intent": "light spring off stone paver, rushing aerial wind through layered silk robes, soft cushioned landing on stone"
        },
        "editorial": {"cut_purpose": "spatial inversion transition", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "aerial leap past opponent and balanced landing inversion",
            "anticipation": "Deep knee flexion and ankle compression loading vertical spring force.",
            "locomotion": "lightweight martial leap (Thân Pháp / Qinggong trajectory)",
            "weight_transfer": "ground force into airborne ballistic arc, settling into bilateral shock absorption",
            "foot_plant": "soft landing on metatarsals, heels settling quietly onto granite",
            "hip_torso_rotation": "torso remains horizontal in air, rotating 180 degrees at landing touchdown",
            "arm_countermotion": "arms spread wide like wings for balance, sword held parallel to forearm",
            "contact_event": "soft foot landing on flagstones",
            "reaction": "fluid deceleration into balanced crouch",
            "recovery": "immediate rising into ready stance",
            "secondary_motion": "white robes billow wide in flight, settling gracefully around boots on landing",
            "motion_energy": "moderate",
            "motion_risk_class": "MEDIUM",
            "beats": [
                {"label": "takeoff_launch", "description": "explosive silent spring into air", "approx_start_s": 0.5},
                {"label": "airborne_apex", "description": "backlit silhouette soaring past opponent", "approx_start_s": 2.0},
                {"label": "landing_touchdown", "description": "cushioned landing and rotational ready pivot", "approx_start_s": 3.8}
            ]
        },
        "action_intent": {
            "trigger": "barrier fractures and Black cultivator's balance is committed to holding it",
            "perception": "White cultivator recognizes frontal path is blocked but vertical aerial lane is open",
            "character_goal": "bypass barrier completely and invert combat geography",
            "motivation": "exploit superior lightness skill (Khinh Công) and reposition behind opponent",
            "obstacle_or_pressure": "Black cultivator's physical mass and barrier obstruction",
            "chosen_action": "Đạp Vân Thân Pháp (Cloud-Treading leap)",
            "intended_outcome": "take position behind Black cultivator and force him to turn",
            "resulting_state": "positions inverted: White at East ledge facing West, Black at West facing East",
            "next_decision": "prepare final decisive counter-strike as Black turns",
            "visual_legibility_requirements": ["readable airborne human silhouette", "consistent screen direction", "clean landing"],
            "stakes": "tactical repositioning",
            "urgency": "fluid and decisive",
            "knowledge_state": "White knows Black will be disoriented by the rapid positional inversion"
        }
    },
    {
        "shot_id": "X09",
        "dramatic_purpose": "Black cultivator pivots sharply and unleashes a wide sweeping crescent of dark sword energy across the terrace.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "MS", "height": "eye_level", "lens_intent": "normal", "focal_hint_mm": 40.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "Black cultivator dissolves his barrier, pivoting 180 degrees on his heel to face screen-right.",
            "action_beats": [
                "Grips heavy sword hilt with both hands and sweeps blade through a wide horizontal crescent arc",
                "A 6-foot wide crescent blade of concentrated dark-purple sword energy detaches from the steel",
                "The dark crescent projectile flies horizontally across the terrace floor toward screen-right",
                "Low-lying mist on the flagstones is sucked into the crescent's wake like a dark vortex"
            ],
            "end": "Black cultivator holds aggressive follow-through pose; dark crescent flying toward screen-right.",
            "prop_interactions": ["heavy sword", "projected crescent energy"]
        },
        "performance": {
            "observable_beats": [
                "Full-body rotational torque driving the two-handed swing",
                "Intense aggressive grimace of determination",
                "Firm rooted follow-through stance"
            ],
            "forbidden": ["aimless particle spam", "sword disappearing during swing", "distorted torso anatomy"]
        },
        "lighting": {
            "key_direction": "crescent_dark_purple", "contrast": "high",
            "notes": "Deep violet glow from crescent blade casting dynamic moving shadows across dark flagstones"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "screen_right",
            "start_state": C_STATES[8]["start"],
            "end_state": C_STATES[8]["end"],
            "previous_shot_id": "X08",
            "critical_invariants": [
                "Black cultivator now positioned at screen-left facing right on South camera axis",
                "Dark crescent blade travels strictly left-to-right along flagstone plane",
                "Mist wake trailing behind energy projectile"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain wind",
            "sfx_intent": "low guttural kiai yell, heavy tearing whoosh of crescent blade cleaving air, deep sub-bass rumble of dark qi"
        },
        "editorial": {"cut_purpose": "ranged energy escalation", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "rotational two-handed swing releasing crescent blade of dark sword energy",
            "anticipation": "180-degree pivot loading rotational torque through hips, core, and shoulders.",
            "locomotion": "stationary pivot on heel",
            "weight_transfer": "weight shifts from left foot to right foot in wide rooted horse stance",
            "foot_plant": "wide aggressive stance, boots dug into stone grooves",
            "hip_torso_rotation": "explosive 90-degree torso rotation driving the blade release",
            "arm_countermotion": "both arms sweep horizontally across chest in powerful coordinated extension",
            "contact_event": "release of dark sword energy from steel blade tip",
            "reaction": "recoil through shoulders as energy detaches",
            "recovery": "holds solid follow-through posture with blade pointed forward-right",
            "secondary_motion": "dark cloak whips radially in direction of sword sweep",
            "motion_energy": "high",
            "motion_risk_class": "HIGH",
            "beats": [
                {"label": "pivot_load", "description": "sharp pivot gathering dark energy into blade", "approx_start_s": 0.4},
                {"label": "crescent_release", "description": "two-handed sweep launching dark energy crescent", "approx_start_s": 1.6},
                {"label": "follow_through", "description": "holding follow-through pose as crescent flies", "approx_start_s": 3.5}
            ]
        },
        "action_intent": {
            "trigger": "White cultivator lands behind him at opposite edge",
            "perception": "Black cultivator senses White preparing a counter and unleashes his ultimate ranged strike",
            "character_goal": "annihilate White cultivator with full-power crescent strike before White can close distance",
            "motivation": "desperation to regain combat dominance",
            "obstacle_or_pressure": "White's superior evasion and positional advantage",
            "chosen_action": "U Minh Trảm (Dark Nether Slash)",
            "intended_outcome": "cleave White cultivator in half or blast him off the terrace cliff",
            "resulting_state": "all offensive power committed to the flying crescent projectile",
            "next_decision": "watch for impact outcome",
            "visual_legibility_requirements": ["clear crescent blade silhouette", "visible travel trajectory", "no frame flicker"],
            "stakes": "ultimate offensive gamble",
            "urgency": "all-in aggressive release",
            "knowledge_state": "believes no ordinary straight sword can deflect this full-power crescent"
        }
    },
    {
        "shot_id": "X10",
        "dramatic_purpose": "The decisive strike (Nhất Kiếm) — White cultivator's focused linear thrust pierces and shatters the dark crescent energy into vapor.",
        "duration_target_s": 5.0,
        "shot_type": "action",
        "camera": {
            "framing": "TWO_SHOT", "height": "eye_level", "lens_intent": "wide", "focal_hint_mm": 35.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "White cultivator stands firm on screen-right; the 6-foot dark crescent speeds toward him from screen-left.",
            "action_beats": [
                "White cultivator steps forward into an immaculate linear lunge, extending sword straight forward",
                "A concentrated, needle-thin beam of pure white-azure light projects from the sword point",
                "The white sword-line pierces dead-center through the dark crescent, shattering it into harmless grey vapor",
                "A clean radial shockwave clears mist across the entire terrace; Black cultivator is staggered back on screen-left"
            ],
            "end": "White cultivator holds extended lunging pose; dark energy completely neutralized; silence falls.",
            "prop_interactions": ["sword piercing energy crescent"]
        },
        "performance": {
            "observable_beats": [
                "Flawless orthodox lunge posture (front knee 90 degrees, rear leg straight)",
                "Complete stillness and mental focus during and after the strike",
                "Black cultivator staggering backward three paces, breathless"
            ],
            "forbidden": ["blood or decapitation", "screaming faces", "chaotic flashing lights"]
        },
        "lighting": {
            "key_direction": "piercing_sword_white_azure", "contrast": "high",
            "notes": "Brilliant point light at puncture center illuminating duelists before settling into soft morning light"
        },
        "continuity": {
            "screen_direction": "right-to-left",
            "eyeline": "mutual_sightline",
            "start_state": C_STATES[9]["start"],
            "end_state": C_STATES[9]["end"],
            "previous_shot_id": "X09",
            "critical_invariants": [
                "White cultivator on screen-right thrusting leftward on South camera axis",
                "Black cultivator on screen-left staggered back",
                "Dark crescent completely shattered and gone, no lingering fire"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain air",
            "sfx_intent": "high-pitched crystalline chime of sword-point puncture, followed by a soft airy whoosh as dark energy dissolves into vapor"
        },
        "editorial": {"cut_purpose": "decisive duel payoff", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "flawless orthodox linear thrust piercing and dissolving dark energy",
            "anticipation": "White cultivator drops center of gravity, aligning shoulder, elbow, wrist, and blade into a laser-straight axis.",
            "locomotion": "single decisive lunging step (Chính Đạo Trực Thứ)",
            "weight_transfer": "70% weight locked into front right leg, rear leg anchored straight",
            "foot_plant": "lead foot plants flat and immovable; rear foot digs into granite",
            "hip_torso_rotation": "hips square to target vector, spine perfectly erect",
            "arm_countermotion": "right arm extends to full extension; left hand locks in sword-finger at temple",
            "contact_event": "sword-line pierces and shatters the flying energy crescent",
            "reaction": "radial kinetic air blast expanding outward",
            "recovery": "holds rigid heroic lunging pose without trembling",
            "secondary_motion": "white robe hems flow smoothly backward in line with lunge",
            "motion_energy": "high",
            "motion_risk_class": "HIGH",
            "beats": [
                {"label": "linear_lunge", "description": "laser-focused lunging extension", "approx_start_s": 0.5},
                {"label": "energy_shatter", "description": "piercing point shatters crescent into vapor", "approx_start_s": 1.5},
                {"label": "resonance_hold", "description": "mist clears radially, holding triumphant lock", "approx_start_s": 3.0}
            ]
        },
        "action_intent": {
            "trigger": "incoming lethal crescent projectile",
            "perception": "White cultivator identifies the singular geometric center of the energy arc",
            "character_goal": "neutralize the crescent with one focused stroke ('Nhất Kiếm Phá Vân') and end the duel",
            "motivation": "Daoist philosophy: one pure truth dispels a thousand dark illusions",
            "obstacle_or_pressure": "massive flying energy projectile",
            "chosen_action": "Nhất Kiếm Phá Vân (One Sword Pierces the Clouds)",
            "intended_outcome": "shatter the crescent and decisively disarm opponent's will to fight",
            "resulting_state": "duel decisively decided; dark energy dissolved",
            "next_decision": "hold pose to confirm opponent acknowledges defeat",
            "visual_legibility_requirements": ["crisp straight beam line", "instant clean dissipation of dark energy", "readable two-fighter staging"],
            "stakes": "the decisive title shot of the film",
            "urgency": "perfect razor-sharp timing",
            "knowledge_state": "White knows the duel is won; Black realizes his ultimate technique was countered with simplicity"
        }
    },
    {
        "shot_id": "X11",
        "dramatic_purpose": "Aftermath of the clash; Black cultivator lowers his sword tip to the flagstones and sinks to one knee in exhausted defeat.",
        "duration_target_s": 5.0,
        "shot_type": "reaction",
        "camera": {
            "framing": "MS", "height": "high", "lens_intent": "normal", "focal_hint_mm": 50.0,
            "movement": {"type": "locked"}
        },
        "blocking": {
            "start": "Black cultivator stands trembling on screen-left amid fading wisps of grey vapor.",
            "action_beats": [
                "Heavy chest heaves with rapid exhausted breathing; fingers slowly loosen on sword hilt",
                "The heavy sword tip drops slowly until it rests gently against dark granite flagstones",
                "Black cultivator lowers his right knee onto the stone in posture of dignified surrender",
                "Bows head slightly, accepting the unambiguous martial outcome without bitterness"
            ],
            "end": "Kneeling silhouette motionless on screen-left; breath fogging in the cold mountain air.",
            "prop_interactions": ["sword resting point-down on flagstone"]
        },
        "performance": {
            "observable_beats": [
                "Visible heavy breathing and chest deflation",
                "Gradual muscular surrender of tension in shoulders and arms",
                "Dignified downward tilt of head indicating acknowledgment of defeat"
            ],
            "forbidden": ["wailing or dramatic weeping", "blood vomiting", "spastic collapsing"]
        },
        "lighting": {
            "key_direction": "north_sky_diffuse", "contrast": "medium_soft",
            "notes": "Gentle diffuse cloudlight softening dark robes, highlighting quiet stillness of defeat"
        },
        "continuity": {
            "screen_direction": "static",
            "eyeline": "ground_level",
            "start_state": C_STATES[10]["start"],
            "end_state": C_STATES[10]["end"],
            "previous_shot_id": "X10",
            "critical_invariants": [
                "Black cultivator kneeling on screen-left on South camera axis",
                "Sword point resting peacefully on stone, intact",
                "No blood, no wounds, clean dignified martial defeat"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "mountain silence, soft gentle wind",
            "sfx_intent": "heavy ragged exhale of breath, soft metallic tap of sword tip touching granite, rustle of black robe fabric touching stone"
        },
        "editorial": {"cut_purpose": "duel aftermath & defeat acknowledgment", "handles_s": 0.25, "pickup_priority": "normal"},
        "performance_spec": {
            "primary_action": "slow controlled descent to one knee in dignified martial surrender",
            "anticipation": "Heavy deep breath; fingers unclench from white-knuckle hilt grip.",
            "locomotion": "stationary vertical descent",
            "weight_transfer": "weight lowers from standing legs onto right knee and left foot",
            "foot_plant": "right knee rests gently on granite paver; left foot anchors forward",
            "hip_torso_rotation": "spine curves slightly forward in fatigue, head dips 15 degrees",
            "arm_countermotion": "right arm extends downward letting sword tip contact stone; left arm rests on knee",
            "contact_event": "sword tip and right knee touching granite pavers",
            "reaction": "deep full-body release of combat adrenaline",
            "recovery": "motionless kneeling posture of quiet resignation",
            "secondary_motion": "robe hems drape softly onto the wet stone pavement",
            "motion_energy": "low",
            "motion_risk_class": "LOW",
            "beats": [
                {"label": "sword_lower", "description": "heavy sword tip drops to touch flagstone", "approx_start_s": 0.8},
                {"label": "knee_drop", "description": "slow dignified descent onto one knee", "approx_start_s": 2.2},
                {"label": "breath_settle", "description": "head lowers, breath fogs in quiet silence", "approx_start_s": 3.8}
            ]
        },
        "action_intent": {
            "trigger": "witnessing ultimate technique effortlessly pierced and dissolved",
            "perception": "Black cultivator recognizes the insurmountable gap in sword dao understanding",
            "character_goal": "acknowledge defeat with dignity and yield the platform",
            "motivation": "Daoist martial code: submit to true mastery without resentment",
            "obstacle_or_pressure": "pride and physical exhaustion",
            "chosen_action": "lower weapon and take one knee",
            "intended_outcome": "signal cessation of hostilities and peaceful resolution",
            "resulting_state": "defeat unambiguously declared and accepted",
            "next_decision": "remain kneeling in respectful silence",
            "visual_legibility_requirements": ["clear kneeling silhouette", "sword touching ground", "peaceful composition"],
            "stakes": "martial character and dignity",
            "urgency": "slow, unhurried, conclusive",
            "knowledge_state": "peace in accepting total defeat by a superior swordsman"
        }
    },
    {
        "shot_id": "X12",
        "dramatic_purpose": "Resolution; White cultivator smoothly sheathes his blade as warm morning sunbeams break through the mountain clouds over both figures.",
        "duration_target_s": 5.0,
        "shot_type": "hero",
        "camera": {
            "framing": "WS", "height": "eye_level", "lens_intent": "wide", "focal_hint_mm": 28.0,
            "movement": {"type": "tracking", "purpose": "slow lateral tracking revealing parting clouds and morning horizon", "timing": "entire 5s"}
        },
        "blocking": {
            "start": "White cultivator stands upright on screen-right; Black cultivator kneels quietly in midground-left.",
            "action_beats": [
                "White cultivator performs a graceful circular wrist flick to clear residual sword qi from steel",
                "Slides straight blade smoothly back into silver-mounted scabbard until it locks with a soft metallic click",
                "Turns gaze toward the distant mountain horizon as golden morning sunbeams break through the parting cloud sea",
                "Both silhouettes remain peaceful and grounded on the ancient terrace in wide cinematic balance"
            ],
            "end": "Full-film visual resolution; sunlight flooding the sea of clouds; runtime reaches exactly 60.0s.",
            "prop_interactions": ["sword and scabbard"]
        },
        "performance": {
            "observable_beats": [
                "Graceful ritualistic sheathing of sword",
                "Serene, composed facial expression with soft upward eyeline toward light",
                "Relaxed upright Daoist martial posture"
            ],
            "forbidden": ["celebrating or gloating", "turning back aggressively", "artificial fade to black filler"]
        },
        "lighting": {
            "key_direction": "morning_sunbeams_breakthrough", "contrast": "medium_warm",
            "notes": "Warm golden morning rays piercing through parted clouds, illuminating white robes and misty terrace"
        },
        "continuity": {
            "screen_direction": "left-to-right",
            "eyeline": "horizon_morning_sky",
            "start_state": C_STATES[11]["start"],
            "end_state": C_STATES[11]["end"],
            "previous_shot_id": "X11",
            "critical_invariants": [
                "White standing upright on screen-right, Black kneeling on screen-left on South camera axis",
                "Sword fully sheathed at shot completion",
                "Golden morning sunbeams illuminating mountain clouds",
                "Total film runtime exactly 60.0s"
            ]
        },
        "audio": {
            "dialogue": None, "dialogue_character_id": None,
            "room_tone": "warm mountain breeze, opening expansive sky acoustics",
            "sfx_intent": "soft metallic click of sword hilt locking into scabbard collar, followed by soaring gentle traditional wooden flute and string melody"
        },
        "editorial": {"cut_purpose": "film resolution & picture lock", "handles_s": 0.25, "pickup_priority": "high"},
        "performance_spec": {
            "primary_action": "ritual sheathing of straight sword and peaceful contemplation of sunrise",
            "anticipation": "Right wrist rolls sword in tight vertical circle clearing residual energy.",
            "locomotion": "stationary with subtle slow lateral camera track",
            "weight_transfer": "settles evenly onto both legs in relaxed natural posture",
            "foot_plant": "parallel feet, grounded and relaxed on granite flagstones",
            "hip_torso_rotation": "torso turns 20 degrees toward morning sun on horizon",
            "arm_countermotion": "left hand raises scabbard throat; right hand guides blade smoothly home",
            "contact_event": "scabbard collar lock click",
            "reaction": "shoulders drop in complete tranquility",
            "recovery": "arms settle naturally at sides",
            "secondary_motion": "white robe hems catch golden light as wind softens",
            "motion_energy": "low",
            "motion_risk_class": "LOW",
            "beats": [
                {"label": "blade_flick", "description": "wrist flick clearing qi from steel", "approx_start_s": 0.5},
                {"label": "sword_sheathe", "description": "blade slides smoothly into scabbard with tactile click", "approx_start_s": 2.0},
                {"label": "sunrise_resolve", "description": "gaze toward sunrise horizon as clouds open", "approx_start_s": 3.8}
            ]
        },
        "action_intent": {
            "trigger": "duel conclusion acknowledged by opponent",
            "perception": "White cultivator senses danger has passed and world harmony is restored",
            "character_goal": "sheathe weapon and achieve spiritual and martial closure",
            "motivation": "highest Daoist ideal: the purpose of the sword is to bring peace, not endless slaughter",
            "obstacle_or_pressure": "none; combat tension dissolved",
            "chosen_action": "ritual sheathing and horizon contemplation",
            "intended_outcome": "complete visual, dramatic, and emotional resolution of the film",
            "resulting_state": "peace on the mountain summit; master film complete",
            "next_decision": "picture lock and sound finishing handoff",
            "visual_legibility_requirements": ["unobstructed view of sea of clouds and sunbeams", "clean sword sheathing action", "poetic final composition"],
            "stakes": "dramatic resolution of the entire 60-second film",
            "urgency": "serene, unhurried, majestic",
            "knowledge_state": "harmony restored on Van Dai peak"
        }
    }
]

# -----------------------------------------------------------------------------
# 4. Main Compilation Logic
# -----------------------------------------------------------------------------

def build_compilation() -> int:
    print("=" * 70)
    print("XIANXIA60 — Film Core Pre-Production Compilation Builder (v2 Correction)")
    print("Film: Nhất Kiếm Phá Vân (60.0s, 12 shots, Van Dai Mountain Terrace)")
    print("=" * 70)

    # A. Narrative Compiler
    print("\n[Phase A] Running NarrativeCompiler...")
    narrative_compiler = NarrativeCompiler()
    compiled_narrative = narrative_compiler.compile(
        source_text=PROSE,
        source_kind="prose",
        cast=CAST,
        world_facts={"location": WORLD_INITIAL.location}
    )
    n_events = len(compiled_narrative["events"])
    n_beats = len(compiled_narrative["beats"])
    print(f"  Compiled events: {n_events}")
    print(f"  Compiled beats: {n_beats}")
    if n_beats != 12:
        raise SystemExit(f"Narrative compilation drift: expected 12 beats, got {n_beats}")

    # B. StoryGraph
    print("\n[Phase B] Building StoryGraph...")
    story_graph = StoryGraph().build_from_compiled(
        compiled_narrative,
        cast=CAST,
        locations=["Van Dai mountain terrace"],
        objects=["straight steel sword", "heavy broad sword", "scabbard", "qi barrier", "energy crescent"]
    )
    print(f"  StoryGraph nodes: {len(story_graph.nodes)}")
    print(f"  StoryGraph edges: {len(story_graph.edges)}")

    # Character Bibles
    white_bible = CharacterBible(
        name="White Cultivator",
        **CAST[0]["bible"]
    )
    black_bible = CharacterBible(
        name="Black Cultivator",
        **CAST[1]["bible"]
    )
    print(f"  White Cultivator fingerprint: {white_bible.identity_fingerprint()}")
    print(f"  Black Cultivator fingerprint: {black_bible.identity_fingerprint()}")

    # C. WorldStateGraph (Using explicit physical states for both fighters and terrace)
    print("\n[Phase C] Building WorldStateGraph with explicit entity states...")
    world_graph = WorldStateGraph(WORLD_STATES[0])
    for i, event in enumerate(compiled_narrative["events"]):
        sid = f"X{i+1:02d}"
        world_graph.push_shot_state(sid, WORLD_STATES[i], justified_by_event=event.event_id)
    print(f"  WorldStateGraph states: {len(world_graph.states)}")
    print(f"  WorldStateGraph transitions: {len(world_graph.transitions)}")

    # D. XianxiaDirectorCompiler (Synchronized ShotGraph)
    print("\n[Phase D] Running XianxiaDirectorCompiler (synchronized ShotGraph)...")
    director = XianxiaDirectorCompiler(
        screen_direction="left-to-right",
        light_direction=WORLD_INITIAL.lighting
    )
    shot_graph, intents = director.design(
        compiled_narrative["beats"],
        world_state=WORLD_INITIAL,
        cast=CAST
    )
    print(f"  Director intents: {len(intents)}")
    print(f"  ShotGraph nodes: {len(shot_graph.nodes)}")
    print(f"  ShotGraph edges: {len(shot_graph.edges)}")
    if len(shot_graph.nodes) != 12:
        raise SystemExit(f"Director compiler drift: expected 12 shot nodes, got {len(shot_graph.nodes)}")

    # E. Construct Canonical ShotSpecs (X01 to X12)
    print("\n[Phase E] Constructing & Validating 12 Canonical ShotSpecs (Draft2020-12)...")
    shot_specs: list[ShotSpec] = []
    shot_spec_hashes: dict[str, str] = {}

    for i, raw in enumerate(SHOTS_RAW):
        sid = raw["shot_id"]
        char_refs = [
            CharacterRef(
                character_id="WHITE_CULTIVATOR",
                identity_version="ID_V1",
                look_state_id="LOOK_WHITE_ROBE_V1",
                behavior_state="disciplined_ready" if i < 10 else "peaceful_triumphant",
                role_in_shot="protagonist"
            ),
            CharacterRef(
                character_id="BLACK_CULTIVATOR",
                identity_version="ID_V1",
                look_state_id="LOOK_BLACK_ROBE_V1",
                behavior_state="aggressive_assault" if i < 10 else "defeated_dignified",
                role_in_shot="antagonist"
            )
        ]
        env = Environment(
            location_id="LOC_VAN_DAI_TERRACE",
            location_version="LOC_V1",
            time_of_day="cold morning",
            weather="mountain mist",
            atmosphere=WORLD_INITIAL.location
        )
        cam = Camera(
            framing=raw["camera"]["framing"],
            height=raw["camera"]["height"],
            lens_intent=raw["camera"]["lens_intent"],
            focal_hint_mm=raw["camera"]["focal_hint_mm"],
            movement=Movement(**raw["camera"]["movement"])
        )
        blocking = Blocking(**raw["blocking"])
        perf = Performance(**raw["performance"])
        lighting = Lighting(**raw["lighting"])
        cont = Continuity(**raw["continuity"])
        audio = Audio(**raw["audio"])
        refs = References(
            character_asset_ids=["CHAR_WHITE_CULTIVATOR_REF_V1", "CHAR_BLACK_CULTIVATOR_REF_V1"],
            location_asset_ids=["LOC_VAN_DAI_TERRACE_REF_V1"],
            wardrobe_asset_ids=["WARDROBE_WHITE_ROBE_V1", "WARDROBE_BLACK_ROBE_V1"],
            other_asset_ids=[]
        )
        constraints = Constraints(
            must_preserve=[
                "White cultivator screen-left / Black cultivator screen-right axis (prior to X08)",
                "Orthodox straight sword vs heavy broadsword distinction",
                "High mountain cloud sea environment"
            ],
            must_avoid=NEGATIVES
        )
        editorial = Editorial(**raw["editorial"])
        perf_spec = PerformanceSpec(schema_version="performance-spec-v1", **raw["performance_spec"])
        action_intent = ActionIntent(schema_version="action-intent-v1", **raw["action_intent"])

        spec = ShotSpec(
            schema_version="1.0.0",
            spec_version=1,
            shot_id=sid,
            scene_id="SC_XIANXIA60_DUEL",
            dramatic_purpose=raw["dramatic_purpose"],
            duration_target_s=raw["duration_target_s"],
            shot_type=raw["shot_type"],
            characters=char_refs,
            environment=env,
            camera=cam,
            blocking=blocking,
            performance=perf,
            lighting=lighting,
            continuity=cont,
            audio=audio,
            references=refs,
            constraints=constraints,
            editorial=editorial,
            performance_spec=perf_spec,
            action_intent=action_intent
        )

        # Validate against JSON schema
        validate_contract("shot_spec", spec.payload())
        h = sha256(spec)
        shot_specs.append(spec)
        shot_spec_hashes[sid] = h
        print(f"  {sid}: schema PASS | hash: {h[:16]}... | type: {spec.shot_type:12s} | {spec.camera.framing:8s} | {spec.dramatic_purpose[:40]}...")

    # F. Canonical Prompt Compilation (PromptPlan)
    print("\n[Phase F] Compiling Structured PromptPlans via film_pipeline.compiler...")
    planning_capabilities = ProviderCapabilities(
        profile_version="planning-xianxia60-v1",
        provider_id="seedance_v2_planning",
        transport_type="other",
        supports_text_to_video=True,
        supports_image_input=False,
        supports_duration_control=False,
        supports_native_audio=False,
        supports_negative_prompt=False,
        notes=[
            "PLANNING ONLY: Seedance 2.0 text-to-video profile for Xianxia60.",
            "No active network release authorized in this pre-production package.",
            "Unsupported structured controls degrade safely to textual canonical blocks."
        ]
    )

    prompt_plans: dict[str, PromptPlan] = {}
    prompt_hashes: dict[str, str] = {}
    for spec in shot_specs:
        plan = compile_prompt(spec, planning_capabilities)
        validate_contract("prompt_plan", plan.payload())
        prompt_plans[spec.shot_id] = plan
        prompt_hashes[spec.shot_id] = plan.input_hash
        print(f"  {spec.shot_id}: plan_id: {plan.prompt_plan_id[:24]}... | input_hash: {plan.input_hash[:16]}... | unsupported: {len(plan.unsupported_controls)} degraded: {len(plan.degraded_controls)}")

    # G. Pre-production EditManifest
    print("\n[Phase G] Building Pre-production EditManifest via make_edit_manifest...")
    clips = [
        EditClip(
            order=i + 1,
            shot_id=spec.shot_id,
            selected_take_id=f"take_placeholder_{spec.shot_id}",
            asset_id=f"asset_placeholder_{spec.shot_id}",
            source_in_s=0.0,
            source_out_s=spec.duration_target_s,
            target_duration_s=spec.duration_target_s,
            notes=f"PRE-PRODUCTION PLANNING PLACEHOLDER / NO GENERATED FOOTAGE - {spec.dramatic_purpose}"
        )
        for i, spec in enumerate(shot_specs)
    ]
    edit_manifest = make_edit_manifest("xianxia60_nhat_kiem_pha_van", clips)
    total_duration = sum(c.target_duration_s for c in edit_manifest.clips)
    print(f"  EditManifest ID: {edit_manifest.edit_manifest_id}")
    print(f"  Total clips: {len(edit_manifest.clips)}")
    print(f"  Total planned duration: {total_duration:.1f} seconds (Target: 55-65s, intended 60s)")

    # H. Storyboard & Animatic Plan Cards
    print("\n[Phase H] Assembling Storyboard & Animatic Planning Cards...")
    storyboard_cards = []
    for spec, raw in zip(shot_specs, SHOTS_RAW):
        storyboard_cards.append({
            "shot_id": spec.shot_id,
            "beat_id": f"beat_{int(spec.shot_id[1:]):02d}",
            "timing_s": f"{(int(spec.shot_id[1:]) - 1) * 5:02d}-{(int(spec.shot_id[1:])) * 5:02d}",
            "duration_s": spec.duration_target_s,
            "framing": spec.camera.framing,
            "camera_movement": spec.camera.movement.type,
            "camera_axis": "South (looking North at mountains and clouds)",
            "screen_direction": spec.continuity.screen_direction,
            "dramatic_purpose": spec.dramatic_purpose,
            "action_beats": spec.blocking.action_beats,
            "staging_in": spec.continuity.start_state,
            "staging_out": spec.continuity.end_state,
            "critical_invariants": spec.continuity.critical_invariants,
            "sound_intent": spec.audio.sfx_intent if spec.audio else "",
            "card_status": "PRE-PRODUCTION PLANNING ONLY / NO GENERATED FOOTAGE"
        })

    # I. Combat & VFX Risk Matrix
    risk_matrix = [
        {
            "shot_id": "X01", "risk_level": "LOW",
            "combat_element": "Standoff tension, wide cloud environment",
            "provider_failure_mode": "Extra unwanted characters or deformed mountain pillars",
            "mitigation_fallback": "Strict negative prompt 'no third person, no audience', wide locked camera reduces temporal morphing."
        },
        {
            "shot_id": "X02", "risk_level": "LOW",
            "combat_element": "Weapon unsheathing insert, pale blade qi",
            "provider_failure_mode": "Fingers fusing with sword guard or bent blade geometry",
            "mitigation_fallback": "Locked profile MCU, clear hilt grip biomechanics in performance spec; pickup fallback: cut directly from hand-on-hilt to drawn ready guard."
        },
        {
            "shot_id": "X03", "risk_level": "MEDIUM",
            "combat_element": "High-speed sprinting lunge right-to-left",
            "provider_failure_mode": "Floating feet, unrealistic gait, sword rubberizing behind body",
            "mitigation_fallback": "Low-angle lateral tracking camera moves with runner; fallback: tighter framing (waist-up) or 3-step stride insert."
        },
        {
            "shot_id": "X04", "risk_level": "HIGH",
            "combat_element": "Two-character sword clash and spark burst",
            "provider_failure_mode": "Multiperson blending, limbs fusing, swords passing through each other instead of locking",
            "mitigation_fallback": "Ranked #1 for Wave-1 generation test. Fallback: tight insert of crossing blades only, or fast cut to recoil reaction in X05."
        },
        {
            "shot_id": "X05", "risk_level": "MEDIUM",
            "combat_element": "Rotational evasion sidestep, blade striking stone",
            "provider_failure_mode": "Teleporting sidestep, feet sliding without traction",
            "mitigation_fallback": "Explicit Bagua pivot biomechanics in PerformanceSpec; fallback: split into White evasion reaction and insert of blade biting stone."
        },
        {
            "shot_id": "X06", "risk_level": "MEDIUM",
            "combat_element": "Palm thrust projecting crystalline qi barrier",
            "provider_failure_mode": "Chaotic fire explosion instead of geometric barrier disc",
            "mitigation_fallback": "Textual prompt specifies 'translucent dark purple crystalline disc, no fire, no explosion'; fallback: tighter palm insert."
        },
        {
            "shot_id": "X07", "risk_level": "HIGH",
            "combat_element": "Sword point impacting qi barrier, radiating cracks",
            "provider_failure_mode": "Sword tip bending, barrier vanishing instantaneously",
            "mitigation_fallback": "Ranked #2 for Wave-1 test. Fallback: macro insert of blade tip with animated composite fracture overlay in editorial/VFX."
        },
        {
            "shot_id": "X08", "risk_level": "HIGH",
            "combat_element": "Aerial leap past opponent, positional inversion",
            "provider_failure_mode": "Multiperson warping as bodies cross in 2D perspective, mangled legs in flight",
            "mitigation_fallback": "Backlit wide silhouette framing ensures clean contours; fallback: cut to low-angle takeoff, high-angle flight against clouds, grounded touchdown."
        },
        {
            "shot_id": "X09", "risk_level": "MEDIUM",
            "combat_element": "Two-handed sweep launching dark energy crescent",
            "provider_failure_mode": "Crescent detaching irregularly or character arms tangling on pivot",
            "mitigation_fallback": "Clear rotational torque in PerformanceSpec; fallback: locked medium shot focusing on torso release, crescent composited downstream."
        },
        {
            "shot_id": "X10", "risk_level": "HIGH",
            "combat_element": "Decisive linear thrust piercing and dissolving dark energy ('Nhất Kiếm')",
            "provider_failure_mode": "Fullscreen particle whiteout obscuring fighters, blade disappearing",
            "mitigation_fallback": "Ranked #3 for Wave-1 test. Core dramatic climax. Fallback: tight shot on White's focused face and thrusting arm, cutaway to dissipating cloud."
        },
        {
            "shot_id": "X11", "risk_level": "LOW",
            "combat_element": "Defeat acknowledgment, descent onto one knee",
            "provider_failure_mode": "Dramatic collapse or blood vomiting contrary to Daoist tone",
            "mitigation_fallback": "Negative constraints forbid blood/gore; slow controlled downward deceleration; highly repairable."
        },
        {
            "shot_id": "X12", "risk_level": "LOW",
            "combat_element": "Sword sheathing and sunrise resolution",
            "provider_failure_mode": "Blade missing scabbard mouth or warping during slide",
            "mitigation_fallback": "Wide framing softens macro alignment; fallback: cut to medium profile sheathing insert or wide silhouette against sunbeams."
        }
    ]

    # J. Audio, Sound FX & Finishing Plan
    audio_finishing_plan = {
        "title": "Nhất Kiếm Phá Vân — Audio, Sound FX & Fairlight Finishing Plan",
        "total_duration_s": 60.0,
        "sample_rate_hz": 48000,
        "channels": "Stereo / 5.1 Surround ready",
        "acoustic_layers": [
            {
                "layer_name": "A1_Dialogue_Voice",
                "role": "Muted martial vocalizations only (kiai on X03/X09, sharp breath on X05/X11), 0 spoken lines.",
                "processing": "Close dynamic mic presence, high-pass 80Hz, gentle optical compression."
            },
            {
                "layer_name": "A2_Foley_Footsteps_Movement",
                "role": "Leather boots on damp granite pavers, weight transfers, leaps, landings, cloth swooshes.",
                "processing": "Room reverb matched to open mountain plateau, slight pre-delay."
            },
            {
                "layer_name": "A3_SFX_Weapons_Combat",
                "role": "Steel unsheathing (X02), blade clash crack & sparks (X04), stone chip strike (X05), sheathing click (X12).",
                "processing": "Crisp transient enhancement, exciter on high-frequency ring (4kHz-8kHz)."
            },
            {
                "layer_name": "A4_VFX_Qi_Energy_Resonance",
                "role": "Crystalline pale azure qi hum (X02/X07/X10), deep sub-bass dark purple qi vortex (X06/X09/X10).",
                "processing": "Pitch-shifted acoustic harmonics, sub-bass 40Hz-60Hz punch, spatial stereo widening."
            },
            {
                "layer_name": "A5_Atmosphere_Ambience",
                "role": "Continuous high-altitude mountain wind, sea of clouds distant atmospheric rumble, breeze in robes.",
                "processing": "Constant room tone baseline, subtle dynamic dips during sword clash transients."
            },
            {
                "layer_name": "A6_Music_Score",
                "role": "Daoist martial score: solitary Guqin & Dizi flute opening -> rising Taiko & orchestral percussion during combat -> soaring melodic resolution at sunrise.",
                "processing": "Dynamic ducking (-3dB) under major sword clashes (X04, X10), full crescendo at X12."
            }
        ],
        "color_finishing_pipeline": {
            "target_color_space": "Rec.709 / Gamma 2.4 (Resolve Studio compatible)",
            "creative_lut_intent": "Cold misty mountain palette (cool cyan-grey shadows, neutral skin tones, luminous pale azure and deep violet qi accents, warm golden highlight breakout on X12)",
            "delivery_specs": "H.264/HEVC 1080p24 master, AAC 320kbps 48kHz audio."
        }
    }

    # K. Provider Route & Wave-1 Bounded Budget Proposal
    provider_budget_proposal = {
        "proposal_title": "S3 XIANXIA60 Wave-1 Bounded Production Authorization Proposal",
        "status": "PRE-PRODUCTION PROPOSAL / REQUIRES OWNER WRITTEN AUTHORIZATION",
        "financial_state_at_WP": "0 NEW PROVIDER ACTIONS / $0 PAID",
        "verified_route_facts": {
            "account_status": "ACCOUNT_A previously observed in prior gardener milestones; current live quota is UNKNOWN.",
            "free_route_policy": "Zero paid charges permitted without separate explicit authorization. No blind retries.",
            "live_session_rule": "No browser session scraping or credential capture without Owner permission."
        },
        "proposed_wave_1_scope": {
            "concept": "Action Style & Character Coherence Calibration Wave (3 critical shots)",
            "candidate_shots": ["X04", "X08", "X10"],
            "rationale": "X04 tests two-character physical sword clash; X08 tests aerial body inversion; X10 tests title decisive strike. If these 3 pass, the remaining 9 shots have lower combat risk.",
            "max_generation_attempts": 3,
            "max_repair_reserve": 1,
            "total_max_releases": 4,
            "cost_ceiling_usd": 0.0,
            "target_provider": "Dola / Seedance 2.0 (free route tier)",
            "fail_closed_latches": "Each attempt is latched in an isolated scope. Any UNKNOWN provider failure stops immediately without retry."
        },
        "proposed_wave_2_scope": {
            "concept": "Full Film Coverage & Completion Wave (Remaining 9 shots: X01-X03, X05-X07, X09, X11-X12)",
            "condition": "Dispatched ONLY after Owner reviews and accepts Wave-1 test results."
        }
    }

    # L. Write Output Files
    print("\n[Phase L] Writing All Artifacts to disk...")
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    EDITORIAL_DIR.mkdir(parents=True, exist_ok=True)
    STORYBOARD_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Individual ShotSpecs
    for spec in shot_specs:
        p = SHOTS_DIR / f"{spec.shot_id}.json"
        p.write_text(json.dumps(spec.payload(), indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Individual PromptPlans
    for plan in prompt_plans.values():
        p = PROMPTS_DIR / f"{plan.shot_id}_plan.json"
        p.write_text(json.dumps(plan.payload(), indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. EditManifest
    manifest_path = EDITORIAL_DIR / "edit_manifest.json"
    manifest_path.write_text(json.dumps(edit_manifest.payload(), indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Storyboard Cards
    storyboard_path = STORYBOARD_DIR / "storyboard_cards.json"
    storyboard_path.write_text(json.dumps(storyboard_cards, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5. Master Compilation Document
    master_compilation = {
        "version": "xianxia60-compilation-v1",
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "film_title": "Nhất Kiếm Phá Vân",
            "working_title": "XIANXIA60",
            "target_runtime_s": total_duration,
            "shot_count": len(shot_specs),
            "arena": "Van Dai high-mountain stone terrace above a sea of clouds",
            "characters": ["White Cultivator (Bạch Y Kiếm Tu)", "Black Cultivator (Hắc Y Kiếm Tu)"]
        },
        "narrative": {
            "source_prose": PROSE,
            "events": [e.model_dump() for e in compiled_narrative["events"]],
            "beats": [b.model_dump() for b in compiled_narrative["beats"]],
            "causality": [c.model_dump() for c in compiled_narrative["causality"]],
            "reveals": [r.model_dump() for r in compiled_narrative["reveals"]],
            "objectives": [o.model_dump() for o in compiled_narrative["objectives"]],
            "transitions": [t.model_dump() for t in compiled_narrative["transitions"]]
        },
        "story_graph": story_graph.to_manifest(),
        "character_bibles": {
            "white_cultivator": white_bible.model_dump(),
            "black_cultivator": black_bible.model_dump()
        },
        "world_state_graph": world_graph.to_manifest(),
        "shot_graph": shot_graph.to_manifest(),
        "lineage_traceability": {
            spec.shot_id: {
                "beat_id": f"beat_{int(spec.shot_id[1:]):02d}",
                "shot_graph_node": f"S{int(spec.shot_id[1:]):02d}",
                "shot_spec_hash": shot_spec_hashes[spec.shot_id],
                "prompt_plan_id": prompt_plans[spec.shot_id].prompt_plan_id,
                "prompt_input_hash": prompt_hashes[spec.shot_id],
                "edit_clip_order": int(spec.shot_id[1:]),
                "duration_s": spec.duration_target_s
            }
            for spec in shot_specs
        },
        "shot_specs": {spec.shot_id: spec.payload() for spec in shot_specs},
        "prompt_plans": {plan.shot_id: plan.payload() for plan in prompt_plans.values()},
        "edit_manifest": edit_manifest.payload(),
        "storyboard_cards": storyboard_cards,
        "risk_matrix": risk_matrix,
        "audio_finishing_plan": audio_finishing_plan,
        "provider_budget_proposal": provider_budget_proposal,
        "system_status": {
            "film_core_technical_pass": True,
            "provider_generate_authorized": False,
            "owner_creative_lock": "PENDING_INDEPENDENT_PROVE_AND_OWNER_REVIEW"
        }
    }

    compilation_path = PROJECT_DIR / "XIANXIA60_COMPILATION.json"
    compilation_path.write_text(json.dumps(master_compilation, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Master compilation saved to: {compilation_path}")
    print(f"  Total file size: {compilation_path.stat().st_size} bytes")

    print("\n" + "=" * 70)
    print("XIANXIA60 Compilation Complete: 12 shots, 60.0s, Schema Valid Draft2020-12.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(build_compilation())
