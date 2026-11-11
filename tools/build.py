"""Build patched resources.assets: Russian text goes into the English column of I2Languages.

usage: python tools/build.py [--out build/resources.assets] [--test-prefix]
Empty "ru" values fall back to the original English text.
"""
import argparse, glob, json, os
import UnityPy
import i2
from common import *


def load_translations():
    tr = {}
    for path in glob.glob(os.path.join(TRANSLATION_DIR, "*.json")):
        for e in json.load(open(path, encoding="utf-8")):
            if e.get("ru"):
                tr[e["key"]] = e["ru"]
    return tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", ASSET_NAME))
    ap.add_argument("--test-prefix", action="store_true", help="prefix every EN string with Cyrillic (font smoke test)")
    a = ap.parse_args()

    env = UnityPy.load(os.path.join(ORIGINAL_DIR, ASSET_NAME))
    obj = find_i2(env)
    doc = i2.parse(obj.get_raw_data())
    tr = load_translations()
    applied = 0
    for t in doc["terms"]:
        if t["type"] != 0:
            continue
        ru = tr.get(t["term"])
        if a.test_prefix and t["langs"][TARGET_COLUMN]:
            ru = "Ёжик съел щи: " + (ru or t["langs"][TARGET_COLUMN])
        if ru:
            t["langs"][TARGET_COLUMN] = ru
            applied += 1
    obj.set_raw_data(i2.serialize(doc))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(env.file.save())
    print(f"applied {applied} strings -> {a.out}")


if __name__ == "__main__":
    main()
