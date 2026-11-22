"""Write installer/ru.tsv (term key -> Russian) from translation/*.json."""
import os
from common import ROOT, all_cats, load_cat


def esc(s):
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def main():
    rows = []
    for cat in all_cats():
        # with the local source we skip lines identical to the original; without it we keep them (harmless)
        for e in load_cat(cat, need_source=False):
            if e.get("ru") and e["ru"] != e.get("en"):
                rows.append(f"{esc(e['key'])}\t{esc(e['ru'])}")
    out = os.path.join(ROOT, "installer", "ru.tsv")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Whisper of the House - русский перевод. key<TAB>text, escapes: \\n \\t \\\\\n")
        f.write("\n".join(rows) + "\n")
    print(f"{len(rows)} lines -> {out}")


if __name__ == "__main__":
    main()
