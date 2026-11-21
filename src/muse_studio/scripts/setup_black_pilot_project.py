import sys
import shutil
from pathlib import Path

sys.path.insert(0, r"D:\Muse\muse_studio")
from core.project_manager import ProjectManager

pm = ProjectManager()
proj_name = "Attendant Rips Badge Off Black Pilot"

# Check if exists
existing = [p for p in pm.list_projects() if p["name"] == proj_name]
if existing:
    proj = existing[0]
    print(f"Existing project found: {proj['id']}")
else:
    proj = pm.create_project(name=proj_name, mode="batch_parallel")
    print(f"Created project: {proj['id']}")

proj_id = proj["id"]
proj_dir = pm.get_project_dir(proj_id)
ref_src = Path(r"D:\Youtube\Vận hành kênh\Black Drama\wanglin08ma\Đang sản xuất\[4-11-26] Attendant Rips Badge Off Black Pilot Before 142 Passengers — [AhrVCbAppHs]\thumbnail_maxres.jpg")
ref_dest = proj_dir / "refs" / "ref_thumbnail.jpg"

if ref_src.exists():
    shutil.copy2(ref_src, ref_dest)
    print(f"Copied reference thumbnail to: {ref_dest}")

shots_data = [
    {
        "order": 1,
        "prompt": "A high-definition cinematic shot of Captain Brianna Johnson, an African American female airline captain in her early 40s with sharp composed eyes and tied-back hair, wearing a dark navy pilot uniform with four gold stripes on epaulets, standing calm and upright in a commercial airliner entrance near the cockpit door. Passenger cabin visible in background under soft recessed lighting. She holds her pilot cap, looking straight into the camera with steady dignity. Locked-off static tripod shot, 16:9 widescreen, cinematic depth of field.",
        "dialogue": "I am the captain.",
        "reference_images": [str(ref_dest)]
    },
    {
        "order": 2,
        "prompt": "Cinematic shot of a hostile Caucasian flight attendant in airline crew uniform standing in the narrow airplane aisle, sneering with wrinkled nose and arrogant expression, scoffing and pointing a dismissive finger towards the front. Narrow aircraft aisle with rows of seated passengers watching in the background. Locked-off static camera, realistic cinematic interior lighting.",
        "dialogue": "It smells like garbage. Get out before I have someone drag you off this plane.",
        "reference_images": [str(ref_dest)]
    },
    {
        "order": 3,
        "prompt": "Cinematic close-up of Captain Brianna Johnson in sharp four-stripe pilot uniform, dignified and unyielding posture. She remains utterly motionless, chin slightly raised, eyes piercing and resolute with total professional authority. Aircraft cabin background with passengers turning heads. Locked-off static close-up shot, shallow depth of field, 16:9 widescreen.",
        "dialogue": "I am Captain Brianna Johnson, your pilot today.",
        "reference_images": [str(ref_dest)]
    },
    {
        "order": 4,
        "prompt": "Medium profile shot inside aircraft cabin entrance: The arrogant flight attendant reaches forward abruptly and yanks the gold-framed pilot ID badge off Captain Brianna's uniform pocket, clutching it smugly while shouting over her shoulder. Passengers looking on with wide eyes and gasps. Locked-off static camera, high detail cinematic 4k look, 16:9 aspect ratio.",
        "dialogue": "Security, get this woman off my plane!",
        "reference_images": [str(ref_dest)]
    },
    {
        "order": 5,
        "prompt": "Cinematic low-angle hero shot of Captain Brianna Johnson, composed and commanding African American female pilot. She calmly pulls out a sleek company smartphone from her pocket with deliberate grace, looking at the attendant with quiet authority in the forward galley. Locked-off static low-angle shot, soft cinematic lighting, 16:9 widescreen.",
        "dialogue": "",
        "reference_images": [str(ref_dest)]
    }
]

proj_obj = pm.get_project(proj_id)
if not proj_obj.get("shots"):
    for s in shots_data:
        pm.add_shot(
            project_id=proj_id,
            prompt=s["prompt"],
            dialogue=s.get("dialogue"),
            reference_images=s.get("reference_images", [])
        )
    print(f"Added {len(shots_data)} shots to project {proj_id}.")
else:
    print(f"Project already has {len(proj_obj['shots'])} shots.")
