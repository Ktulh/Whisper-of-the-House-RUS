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
