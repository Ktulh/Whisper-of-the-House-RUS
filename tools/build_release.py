"""Build dist/WhisperOfTheHouse_RUS_v<version>.zip for GitHub Releases."""
import os, sys, zipfile
from common import ROOT

FILES = ["Установить перевод.bat", "Удалить перевод.bat", "install.ps1", "Patcher.cs", "ru.tsv"]

README_TXT = """Русификатор Whisper of the House

1. Закройте игру.
2. Запустите "Установить перевод.bat" (двойной щелчок).
3. В игре выберите язык English - вместо английского будет русский.

Удаление: "Удалить перевод.bat".
После обновления игры запустите "Установить перевод.bat" ещё раз.
"""


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "0.1"
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"WhisperOfTheHouse_RUS_v{version}.zip")
    folder = f"WhisperOfTheHouse_RUS_v{version}"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:  # Python sets the UTF-8 name flag
        for f in FILES:
            z.write(os.path.join(ROOT, "installer", f), f"{folder}/{f}")
        z.writestr(f"{folder}/ПРОЧТИ МЕНЯ.txt", README_TXT.replace("\n", "\r\n").encode("utf-8-sig"))
    print(out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
