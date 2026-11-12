"""Create deliberately broken copies of resources.assets for tools/test_installer.ps1.

usage: python tools/make_test_variants.py <out_dir>
Needs extracted/original/resources.assets (made by tools/export.py).
"""
import os, sys
import UnityPy
import i2
from common import ORIGINAL_DIR, ASSET_NAME, find_i2

ENGLISH_ROW = b"English\x00\x02\x00\x00\x00en"


def save_variant(out, name, mutate):
    env = UnityPy.load(os.path.join(ORIGINAL_DIR, ASSET_NAME))
    obj = find_i2(env)
    doc = i2.parse(obj.get_raw_data())
    mutate(doc)
    obj.set_raw_data(i2.serialize(doc))
    with open(os.path.join(out, name), "wb") as f:
        f.write(env.file.save())
    print("wrote", name)


def lang_code_changed(doc):
    # column 1 is no longer "en" (e.g. the developers reordered the languages)
    assert ENGLISH_ROW in doc["tail"]
    doc["tail"] = doc["tail"].replace(ENGLISH_ROW, ENGLISH_ROW[:-2] + b"xx", 1)


def lang_count_changed(doc):
    # language list says 8 languages while every term has 9
    marker = b"\x09\x00\x00\x00\x0c\x00\x00\x00"  # count=9, first name length=12 (简体中文)
    assert marker in doc["tail"]
    doc["tail"] = doc["tail"].replace(marker, b"\x08" + marker[1:], 1)


def duplicate_object(data):
    """A second object-table entry that points at the same I2Languages bytes (two 'tables' to choose from)."""
    import struct
    b = bytearray(data)
    meta_size = struct.unpack_from(">I", b, 20)[0]
    data_off = struct.unpack_from(">Q", b, 32)[0]
    sig = b"\x0b\x00\x00\x00I2Languages"
    for p in range(48, 48 + meta_size - 24, 4):
        start, = struct.unpack_from("<q", b, p + 8)
        size, = struct.unpack_from("<I", b, p + 16)
        if size < 100000 or start < 0 or data_off + start + size > len(b):
            continue
        if bytes(b[data_off + start + 28: data_off + start + 28 + len(sig)]) == sig:
            struct.pack_into("<q", b, p - 24 + 8, start)      # previous table entry now aliases the I2 object
            struct.pack_into("<I", b, p - 24 + 16, size)
            return bytes(b)
    raise RuntimeError("I2 entry not found")


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    src = os.path.join(ORIGINAL_DIR, ASSET_NAME)
    with open(src, "rb") as f:
        data = f.read()
    with open(os.path.join(out, "dup_object.assets"), "wb") as f:
        f.write(duplicate_object(data))
    print("wrote dup_object.assets")
    with open(os.path.join(out, "truncated.assets"), "wb") as f:
        f.write(data[:30_000_000])
    print("wrote truncated.assets")
    with open(os.path.join(out, "garbage.assets"), "wb") as f:
        f.write(os.urandom(100_000))
    print("wrote garbage.assets")
    save_variant(out, "lang_code_changed.assets", lang_code_changed)
    save_variant(out, "lang_count_changed.assets", lang_count_changed)


if __name__ == "__main__":
    main()
