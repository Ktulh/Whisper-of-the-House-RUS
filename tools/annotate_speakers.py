"""Add "speaker" (Russian name + zh key) to Dialogues batch inputs from work/speakers.json."""
import json, glob, os, collections
from common import ROOT, TRANSLATION_DIR
sp = json.load(open(os.path.join(ROOT, "work", "speakers.json"), encoding="utf-8"))
names = {e["key"].split("/", 1)[1]: e["ru"] for e in json.load(open(os.path.join(TRANSLATION_DIR, "CharacterName.json"), encoding="utf-8"))}
cnt = collections.Counter(); miss = 0
for p in glob.glob(os.path.join(ROOT, "work", "in", "B_Dialogues_*.json")):
    data = json.load(open(p, encoding="utf-8"))
    for g in data:
        ids = [k.split("/", 1)[1] for k in g["keys"]]
        e = next((sp[i] for i in ids if i in sp), None)
        if not e: g["speaker"] = "unknown"; miss += 1; continue
        n = e["name"]; ru = names.get(n, n)
        g["speaker"] = f"{ru} ({n})" if ru != n else n
        cnt[g["speaker"]] += 1
    json.dump(data, open(p, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print("missing", miss); print(cnt.most_common(60))
