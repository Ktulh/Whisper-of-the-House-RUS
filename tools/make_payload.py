"""Write installer/ru.tsv (term key -> Russian) from translation/*.json."""
import glob, json, os
from common import ROOT, TRANSLATION_DIR


def esc(s):
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(TRANSLATION_DIR, "*.json"))):
        for e in json.load(open(p, encoding="utf-8")):
            if e.get("ru") and e["ru"] != e["en"]:
                rows.append(f"{esc(e['key'])}\t{esc(e['ru'])}")
    out = os.path.join(ROOT, "installer", "ru.tsv")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Whisper of the House - русский перевод. key<TAB>text, escapes: \\n \\t \\\\\n")
        f.write("\n".join(rows) + "\n")
    print(f"{len(rows)} lines -> {out}")


if __name__ == "__main__":
    main()
