import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, "src")
from film_pipeline.drama import HandoffQC
spec = importlib.util.spec_from_file_location("v2", sys.argv[1])
v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
qc = HandoffQC.from_end_state("SC03_g1", "SC03_g2", v2.STATE["g1_end"],
                              looks=list(v2.LOOKS.values()),
                              sheet="docs/drama/film01_takes/qc/SC03_g1_end.png")
notes = {
 "position:NORA": "standing at the counter, frame-left",
 "position:DOYLE": "frame-right, across the counter",
 "prop:the letter:": "torn pieces lie flat on the counter in front of NORA",
 "look:NORA": "short straight grey-streaked hair, matches SC02_g2/SC04_g1 "
              "(cast sheet SC03_g1_cast.png); navy blazer; white top",
 "look:DOYLE": "heavy-set, sandy hair, clean-shaven, navy patrol uniform",
}
for c in qc.checks:
    qc.review(c.item, "PASS", notes[c.item])
qc.reviewer = "Claude (Worker), pending Owner review"
h = qc.to_handoff(previous_action=v2.ACTION[1],
                  previous_start=v2.STATE["g1_start"],
                  previous_end=v2.STATE["g1_end"])
Path("docs/drama/film01_takes/qc/SC03_handoff_qc.json").write_text(
    json.dumps(qc.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
print("verified", qc.verified, h.end_state_verified)
