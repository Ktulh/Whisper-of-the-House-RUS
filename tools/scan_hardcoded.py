"""Find English text in TextMeshPro/Text components that is not covered by the I2 table."""
import UnityPy, glob, os, re, json, struct, collections
from common import *
G = game_data_dir()
en_set = set()
for p in glob.glob(os.path.join(TRANSLATION_DIR, "*.json")):
    for e in json.load(open(p, encoding="utf-8")): en_set.add(e["en"].strip())
files = [os.path.join(G, f) for f in os.listdir(G) if (f.endswith(".assets") or re.fullmatch(r"level\d+", f))]
files += glob.glob(G + r"\StreamingAssets\aa\BuildTarget\*.bundle")
STR = re.compile(rb"(?s)(.{4})")
found = collections.defaultdict(set)
for fp in files:
    try: env = UnityPy.load(fp)
    except Exception: continue
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour": continue
        try:
            mb = obj.read(check_read=False); cls = mb.m_Script.read().m_ClassName
        except Exception: continue
        if cls not in ("TextMeshProUGUI", "TextMeshPro", "Text"): continue
        raw = obj.get_raw_data()
        # m_text is the first string after the header (+ material refs); scan all length-prefixed strings
        p = 0
        while p + 4 < len(raw):
            n = struct.unpack_from("<I", raw, p)[0]
            if 2 <= n < 2000 and p + 4 + n <= len(raw):
                try: s = raw[p+4:p+4+n].decode("utf-8")
                except UnicodeDecodeError: p += 4; continue
                if re.search(r"[A-Za-z]{3,}", s) and s.isprintable() or "\n" in s:
                    if re.search(r"[A-Za-z]{3,}", s) and s.strip() not in en_set and not s.startswith("Assets/"):
                        found[s].add(os.path.basename(fp)[:40])
                p += 4 + ((n + 3) & ~3); continue
            p += 4
out = os.path.join(ROOT, "work", "hardcoded.json")
json.dump({k: sorted(v) for k, v in sorted(found.items())}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(found), "candidate strings ->", out)
