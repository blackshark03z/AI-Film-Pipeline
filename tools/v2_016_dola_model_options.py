"""V2-016 — Dola composer model options (deep unescape, targeted)."""
import json
import re

text = open("projects/quality_v2_010c_dola_fullstack/runtime/capture/"
            "raw_f3r_012_20261006T145913.jsonl", encoding="utf-8",
            errors="replace").read()
i = text.find("Dreamina Seedance 2.5")
window = text[max(0, i - 3000):i + 9000]
u = window
for _ in range(8):
    try:
        u2 = u.encode().decode("unicode_escape")
    except Exception:
        break
    if u2 == u:
        break
    u = u2
options = []
for m in list(re.finditer(r"Dreamina ([A-Za-z0-9 .]{2,50})", u))[:14]:
    tail = u[m.start():m.start() + 600]
    model = re.search(r'"model":\s*"([a-z0-9_.]+)"', tail)
    sub = re.search(r'"sub_display":\s*"([^"]{2,80})"', tail)
    subs = re.search(r'"subs_only_tag":\s*"([a-z_]+)"', tail)
    options.append({
        "display": m.group(1).strip(),
        "model": model.group(1) if model else None,
        "sub_display": sub.group(1) if sub else None,
        "subs_only_tag": subs.group(1) if subs else None,
    })
for o in options:
    print(json.dumps(o, ensure_ascii=False))
json.dump(options, open("projects/quality_v2_016_seedance25_capability/"
                        "dola_composer_model_options.json", "w",
                        encoding="utf-8"), indent=1, ensure_ascii=False)
print("saved dola_composer_model_options.json")
