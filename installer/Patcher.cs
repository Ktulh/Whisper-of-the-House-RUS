// Russian translation patcher for "Whisper of the House".
// Compiled at install time by PowerShell (Add-Type), so no .exe is shipped.
//
// What it does: opens resources.assets (Unity SerializedFile v22+), finds the I2 Localization
// "I2Languages" object, replaces the English column with Russian strings (matched by term key),
// appends the rebuilt object to the end of the file and repoints the object table entry at it.
// Nothing else in the file is touched, so the patch survives unrelated game updates.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public static class WotHPatcher
{
    const int EnglishColumn = 1;

    static uint BE32(byte[] d, int p) { return (uint)(d[p] << 24 | d[p + 1] << 16 | d[p + 2] << 8 | d[p + 3]); }
    static long BE64(byte[] d, int p) { return ((long)BE32(d, p) << 32) | BE32(d, p + 4); }
    static void PutBE64(byte[] d, int p, long v) { for (int i = 7; i >= 0; i--) { d[p + i] = (byte)(v & 0xFF); v >>= 8; } }

    public static Dictionary<string, string> LoadTranslation(string path)
    {
        var map = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var line in File.ReadAllLines(path, new UTF8Encoding(false)))
        {
            if (line.Length == 0 || line[0] == '#') continue;
            int tab = line.IndexOf('\t');
            if (tab <= 0) continue;
            map[Unescape(line.Substring(0, tab))] = Unescape(line.Substring(tab + 1));
        }
        return map;
    }

    static string Unescape(string s)
    {
        if (s.IndexOf('\\') < 0) return s;
        var sb = new StringBuilder(s.Length);
        for (int i = 0; i < s.Length; i++)
        {
            char c = s[i];
            if (c == '\\' && i + 1 < s.Length)
            {
                char n = s[++i];
                if (n == 'n') sb.Append('\n');
                else if (n == 'r') sb.Append('\r');
                else if (n == 't') sb.Append('\t');
                else sb.Append(n);
            }
            else sb.Append(c);
        }
        return sb.ToString();
    }

    // ---- I2 LanguageSourceAsset payload ----
    const int TermsOffset = 56; // header(PPtr, enabled, PPtr script, name "I2Languages") + 3 bools + 1 int

    class R
    {
        public byte[] D; public int P;
        public int I32() { int v = BitConverter.ToInt32(D, P); P += 4; return v; }
        public void Align() { P = (P + 3) & ~3; }
        public string S() { int n = I32(); string v = Encoding.UTF8.GetString(D, P, n); P += n; Align(); return v; }
        public void SkipS() { int n = I32(); P += n; Align(); }
    }

    class W
    {
        public MemoryStream M = new MemoryStream();
        public void I32(int v) { M.Write(BitConverter.GetBytes(v), 0, 4); }
        public void Align() { while (M.Length % 4 != 0) M.WriteByte(0); }
        public void Raw(byte[] d, int off, int len) { M.Write(d, off, len); }
        public void S(string v) { var b = Encoding.UTF8.GetBytes(v); I32(b.Length); M.Write(b, 0, b.Length); Align(); }
    }

    public static byte[] RebuildI2(byte[] obj, Dictionary<string, string> tr, out int applied, out int total)
    {
        var r = new R { D = obj, P = TermsOffset };
        var w = new W();
        w.Raw(obj, 0, TermsOffset);
        int count = r.I32();
        w.I32(count);
        applied = 0; total = count;
        for (int t = 0; t < count; t++)
        {
            string term = r.S(); w.S(term);
            int type = r.I32(); w.I32(type);
            int nl = r.I32(); w.I32(nl);
            string ru;
            bool has = tr.TryGetValue(term, out ru) && type == 0;
            for (int i = 0; i < nl; i++)
            {
                int start = r.P;
                r.SkipS();
                if (has && i == EnglishColumn) { w.S(ru); applied++; }
                else w.Raw(obj, start, r.P - start);
            }
            int fstart = r.P; int fl = r.I32(); r.P += fl; r.Align(); w.Raw(obj, fstart, r.P - fstart);
            int tstart = r.P; int nt = r.I32(); for (int i = 0; i < nt; i++) r.SkipS(); w.Raw(obj, tstart, r.P - tstart);
        }
        w.Raw(obj, r.P, obj.Length - r.P);
        return w.M.ToArray();
    }

    // ---- SerializedFile handling ----
    static readonly byte[] NameSig = Encoding.ASCII.GetBytes("\x0b\0\0\0I2Languages");

    public static string Patch(string assetsPath, string translationPath, string outPath)
    {
        byte[] d = File.ReadAllBytes(assetsPath);
        uint version = BE32(d, 8);
        if (version < 22) throw new Exception("Unsupported SerializedFile version " + version);
        int metaSize = (int)BE32(d, 20);
        long fileSize = BE64(d, 24);
        long dataOffset = BE64(d, 32);
        if (fileSize != d.Length) throw new Exception("File size mismatch: file is damaged or not a Unity asset file");
        bool little = d[16] == 0;
        if (!little) throw new Exception("Big-endian asset files are not supported");
        int metaStart = 48;

        // Find the object-table entry {int64 pathId, int64 byteStart, uint32 byteSize, int32 typeId} of I2Languages
        int entryPos = -1; long objStart = 0; int objSize = 0;
        for (int p = metaStart; p + 24 <= metaStart + metaSize; p += 4)
        {
            long start = BitConverter.ToInt64(d, p + 8);
            uint size = BitConverter.ToUInt32(d, p + 16);
            if (size < 100000 || start < 0 || dataOffset + start + size > d.Length) continue;
            long at = dataOffset + start + 28; // after PPtr gameObject(12) + enabled(4) + PPtr script(12)
            bool match = true;
            for (int k = 0; k < NameSig.Length && match; k++) if (d[at + k] != NameSig[k]) match = false;
            if (match) { entryPos = p; objStart = start; objSize = (int)size; break; }
        }
        if (entryPos < 0) throw new Exception("I2Languages table not found (unknown game version?)");

        var obj = new byte[objSize];
        Buffer.BlockCopy(d, (int)(dataOffset + objStart), obj, 0, objSize);
        int applied, total;
        var tr = LoadTranslation(translationPath);
        byte[] nobj = RebuildI2(obj, tr, out applied, out total);

        // Append new object at the end (8-byte aligned relative to data start), repoint entry, fix header size
        long newStart = d.Length - dataOffset;
        int pad = (int)((8 - (newStart % 8)) % 8);
        newStart += pad;
        long newFileSize = dataOffset + newStart + nobj.Length;
        PutBE64(d, 24, newFileSize);
        Buffer.BlockCopy(BitConverter.GetBytes(newStart), 0, d, entryPos + 8, 8);
        Buffer.BlockCopy(BitConverter.GetBytes((uint)nobj.Length), 0, d, entryPos + 16, 4);

        using (var fs = new FileStream(outPath, FileMode.Create, FileAccess.Write))
        {
            fs.Write(d, 0, d.Length);
            fs.Write(new byte[pad], 0, pad);
            fs.Write(nobj, 0, nobj.Length);
        }
        return string.Format("{0} of {1} lines translated", applied, total);
    }
}
