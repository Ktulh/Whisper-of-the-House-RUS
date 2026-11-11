import UnityPy, glob, os, struct
GAME = r"C:\Games\Steam\steamapps\common\Whisper of the House\Whisper of the House_Data"
files = [os.path.join(GAME, f) for f in os.listdir(GAME) if f.endswith(".assets") or f.startswith("level")] \
      + glob.glob(GAME + r"\StreamingAssets\aa\BuildTarget\*.bundle")
for fp in files:
    if fp.endswith(".resS"): continue
    try: env = UnityPy.load(fp)
    except Exception as e: print("ERR", fp, e); continue
    for obj in env.objects:
        t = obj.type.name
        if t == "Font":
            f = obj.read(check_read=False)
            print(os.path.basename(fp), obj.path_id, "Font", f.m_Name, len(getattr(f,"m_FontData",b"") or b""))
        elif t == "MonoBehaviour":
            try:
                mb = obj.read(check_read=False); sc = mb.m_Script.read()
            except Exception: continue
            if sc.m_ClassName in ("TMP_FontAsset",):
                print(os.path.basename(fp), obj.path_id, sc.m_ClassName, mb.m_Name, obj.byte_size)
