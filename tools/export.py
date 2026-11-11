"""Export text terms from the original resources.assets into translation/<Category>.json.

Existing "ru" values are preserved, so re-export after a game update keeps finished work
and flags changed source strings (en changed -> ru moved to "ru_old", ru emptied).
"""
import json, os, shutil, sys
import UnityPy
import i2
from common import *


def main():
    os.makedirs(ORIGINAL_DIR, exist_ok=True)
    orig = os.path.join(ORIGINAL_DIR, ASSET_NAME)
    if not os.path.exists(orig):
        shutil.copy2(os.path.join(game_data_dir(), ASSET_NAME), orig)
        print("saved pristine copy:", orig)
    env = UnityPy.load(orig)
    doc = i2.parse(find_i2(env).get_raw_data())
    by_cat = {}
    for t in doc["terms"]:
        if t["type"] != 0:
            continue
        cat = t["term"].split("/")[0] if "/" in t["term"] else "_root"
        by_cat.setdefault(cat, []).append(t)
    os.makedirs(TRANSLATION_DIR, exist_ok=True)
    for cat, terms in by_cat.items():
        path = os.path.join(TRANSLATION_DIR, f"{cat}.json")
        old = {}
        if os.path.exists(path):
            old = {e["key"]: e for e in json.load(open(path, encoding="utf-8"))}
        out = []
        for t in terms:
            e = {"key": t["term"], "zh": t["langs"][LANG_ZH], "en": t["langs"][LANG_EN], "ru": ""}
            prev = old.get(t["term"])
            if prev:
                if prev["en"] == e["en"]:
                    e["ru"] = prev.get("ru", "")
                elif prev.get("ru"):
                    e["ru_old"] = prev["ru"]
            out.append(e)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"{cat:22} {len(out)}")


if __name__ == "__main__":
    main()
