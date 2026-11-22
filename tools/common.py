import os
import UnityPy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GAME = r"C:\Games\Steam\steamapps\common\Whisper of the House"
DATA_SUBDIR = "Whisper of the House_Data"
ASSET_NAME = "resources.assets"
I2_OBJECT_NAME = "I2Languages"
TRANSLATION_DIR = os.path.join(ROOT, "translation")
ORIGINAL_DIR = os.path.join(ROOT, "extracted", "original")  # pristine copy of resources.assets (gitignored)

# column indices in the I2 table
LANG_ZH, LANG_EN = 0, 1
TARGET_COLUMN = LANG_EN  # Russian replaces English (Steam "russian" UI language falls back to "en")


# ---------------------------------------------------------------------------------------------
# Translation storage.
#   translation/<Cat>.json  (published)  [{"key", "ru", "h"[, "ru_old"]}]   h = short hash of the original English
#   extracted/source/<Cat>.json (local)  [{"key", "zh", "en"}]               rebuilt from the game by export.py
# The game's original texts are never committed; `h` lets export.py notice when a game update changed a string.
SOURCE_DIR = os.path.join(ROOT, "extracted", "source")


def src_hash(en):
    import hashlib
    return hashlib.sha1(en.encode("utf-8")).hexdigest()[:8]


def _read_json(path):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def all_cats():
    return sorted(os.path.splitext(f)[0] for f in os.listdir(TRANSLATION_DIR) if f.endswith(".json"))


def load_cat(cat, need_source=True):
    """Merged view of one category: key, ru, h, (ru_old) + zh/en when the local source is available."""
    pub = _read_json(os.path.join(TRANSLATION_DIR, f"{cat}.json"))
    spath = os.path.join(SOURCE_DIR, f"{cat}.json")
    src = {e["key"]: e for e in _read_json(spath)} if os.path.exists(spath) else {}
    if need_source and not src and any("en" not in e for e in pub):
        raise SystemExit(f"Original texts for '{cat}' are not in the repository: run tools/export.py "
                         f"(needs your copy of the game) to rebuild extracted/source/")
    out = []
    for p in pub:
        e = dict(p)
        s = src.get(p["key"])
        if s:
            e["zh"], e["en"] = s["zh"], s["en"]
        out.append(e)
    return out


def save_cat(cat, entries):
    """Write the published file (key/ru/h only) and, when originals are present, the local source file."""
    pub, src = [], []
    for e in entries:
        p = {"key": e["key"], "ru": e.get("ru", "")}
        h = src_hash(e["en"]) if "en" in e else e.get("h")
        if h:
            p["h"] = h
        if e.get("ru_old"):
            p["ru_old"] = e["ru_old"]
        pub.append(p)
        if "en" in e:
            src.append({"key": e["key"], "zh": e.get("zh", ""), "en": e["en"]})
    _write_json(os.path.join(TRANSLATION_DIR, f"{cat}.json"), pub)
    if src:
        _write_json(os.path.join(SOURCE_DIR, f"{cat}.json"), src)


def game_data_dir(game=DEFAULT_GAME):
    return os.path.join(game, DATA_SUBDIR)


def find_i2(env):
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            mb = obj.read(check_read=False)
        except Exception:
            continue
        # the script PPtr points into globalgamemanagers.assets, so match by name + size
        if mb.m_Name == I2_OBJECT_NAME and obj.byte_size > 1_000_000:
            return obj
    raise RuntimeError("I2Languages not found")
