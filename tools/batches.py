"""Split untranslated strings into batches for translators, and merge results back.

  python tools/batches.py make  --cats ItemName,UI --max-chars 9000 --prefix A
  python tools/batches.py merge            # work/out/*.json -> translation/*.json
  python tools/batches.py check            # placeholder/tag validation -> work/check.json

Batch input  work/in/<id>.json : [{"id": n, "keys": [...], "zh": "...", "en": "..."}]
Batch output work/out/<id>.json: {"<id>": "русский текст", ...}   (id as string)
Identical English strings inside one category are translated once (dedup).
Strings without Latin letters (numbers, "...", "???") are copied as-is.
"""
import argparse, glob, json, os, re
from common import ROOT, TRANSLATION_DIR

WORK = os.path.join(ROOT, "work")
TAG_RE = re.compile(r"<[^>]*>|\{[^}]*\}|#\d+|\\n|%[sd]")
LATIN = re.compile(r"[A-Za-z]")


def key_sort(k):
    tail = k.split("/", 1)[-1]
    return (0, int(tail), "") if tail.isdigit() else (1, 0, tail)


def load_cat(cat):
    return json.load(open(os.path.join(TRANSLATION_DIR, f"{cat}.json"), encoding="utf-8"))


def save_cat(cat, data):
    with open(os.path.join(TRANSLATION_DIR, f"{cat}.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def all_cats():
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(TRANSLATION_DIR, "*.json")))


def make(a):
    os.makedirs(os.path.join(WORK, "in"), exist_ok=True)
    cats = a.cats.split(",") if a.cats else all_cats()
    manifest = []
    for cat in cats:
        data = load_cat(cat)
        groups = {}
        changed = False
        for e in data:
            if e["ru"]:
                continue
            if not LATIN.search(e["en"]):
                e["ru"] = e["en"]
                changed = True
                continue
            groups.setdefault(e["en"], {"keys": [], "zh": e["zh"], "en": e["en"]})["keys"].append(e["key"])
        if changed:
            save_cat(cat, data)
        items = sorted(groups.values(), key=lambda g: key_sort(g["keys"][0]))
        batch, size, n = [], 0, 0
        def flush():
            nonlocal batch, size, n
            if not batch:
                return
            bid = f"{a.prefix}_{cat}_{n:03d}"
            for i, g in enumerate(batch):
                g["id"] = i
            with open(os.path.join(WORK, "in", f"{bid}.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump([{"id": g["id"], "keys": g["keys"], "zh": g["zh"], "en": g["en"]} for g in batch],
                          f, ensure_ascii=False, indent=1)
            manifest.append({"id": bid, "cat": cat, "count": len(batch), "chars": size})
            batch, size, n = [], 0, n + 1
        for g in items:
            cost = len(g["en"]) + 40  # per-entry overhead so name lists don't get huge
            if batch and size + cost > a.max_chars:
                flush()
            batch.append(g)
            size += cost
        flush()
    print(json.dumps(manifest, ensure_ascii=False))


def merge(a):
    updates = {}
    for p in glob.glob(os.path.join(WORK, "out", "*.json")):
        bid = os.path.splitext(os.path.basename(p))[0]
        src = os.path.join(WORK, "in", f"{bid}.json")
        if not os.path.exists(src):
            continue
        inp = {str(g["id"]): g for g in json.load(open(src, encoding="utf-8"))}
        out = json.load(open(p, encoding="utf-8"))
        for i, ru in out.items():
            if i in inp and isinstance(ru, str) and ru.strip():
                for k in inp[i]["keys"]:
                    updates[k] = ru
    n = 0
    for cat in all_cats():
        data = load_cat(cat)
        hit = False
        for e in data:
            if e["key"] in updates and e["ru"] != updates[e["key"]]:
                e["ru"] = updates[e["key"]]
                hit = True
                n += 1
        if hit:
            save_cat(cat, data)
    print(f"merged {n} strings")


def tags(s):
    return sorted(TAG_RE.findall(s))


def check(a):
    problems = []
    total = done = 0
    for cat in all_cats():
        for e in load_cat(cat):
            total += 1
            if not e["ru"]:
                continue
            done += 1
            if tags(e["en"]) != tags(e["ru"]):
                problems.append({"key": e["key"], "issue": "tags", "en": e["en"], "ru": e["ru"]})
            elif e["en"].count("\n") != e["ru"].count("\n"):
                problems.append({"key": e["key"], "issue": "newlines", "en": e["en"], "ru": e["ru"]})
            elif LATIN.search(re.sub(r"<[^>]*>|\{[^}]*\}", "", e["ru"])) and LATIN.search(e["en"]) and not a.allow_latin:
                problems.append({"key": e["key"], "issue": "latin", "en": e["en"], "ru": e["ru"]})
    os.makedirs(WORK, exist_ok=True)
    json.dump(problems, open(os.path.join(WORK, "check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(f"translated {done}/{total}; problems: {dict(Counter(p['issue'] for p in problems))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("make"); m.add_argument("--cats"); m.add_argument("--max-chars", type=int, default=9000); m.add_argument("--prefix", default="B")
    sp.add_parser("merge")
    c = sp.add_parser("check"); c.add_argument("--allow-latin", action="store_true")
    a = ap.parse_args()
    {"make": make, "merge": merge, "check": check}[a.cmd](a)
