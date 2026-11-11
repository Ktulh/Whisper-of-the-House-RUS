"""Extract DialogueOne ScriptableObjects -> work/speakers.json {dialogueID: {speaker, name, next, passage}}"""
import UnityPy, glob, os, json, struct, collections
from common import *
G = game_data_dir()
files = [os.path.join(G, f) for f in os.listdir(G) if f.endswith(".assets") or f.startswith("level") and not f.endswith(".resS")]
files += glob.glob(G + r"\StreamingAssets\aa\BuildTarget\*.bundle")
class R:
    def __init__(s, d, p): s.d, s.p = d, p
    def i(s): v = struct.unpack_from("<i", s.d, s.p)[0]; s.p += 4; return v
    def s(s):
        n = s.i(); v = s.d[s.p:s.p+n].decode("utf-8", "replace"); s.p += n; s.p = (s.p+3)&~3; return v
out = {}; classes = collections.Counter()
for fp in files:
    try: env = UnityPy.load(fp)
    except Exception: continue
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour": continue
        try:
            mb = obj.read(check_read=False); cls = mb.m_Script.read().m_ClassName
        except Exception: continue
        if cls != "DialogueOne": continue
        raw = obj.get_raw_data(); r = R(raw, 28); r.s()  # m_Name
        try:
            e = {"id": r.i(), "passage": r.i(), "speaker": r.s(), "name": r.s(), "start": r.s(), "content": r.s(), "end": r.s(), "next": r.i()}
        except Exception as ex:
            continue
        out[e["id"]] = e
        classes[os.path.basename(fp)[:30]] += 1
json.dump(out, open(os.path.join(ROOT, "work", "speakers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(out), classes)
for k in list(out)[:8]: print(out[k])
