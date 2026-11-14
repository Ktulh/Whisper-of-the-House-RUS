// Russian translation patcher for "Whisper of the House".
// Compiled at install time by PowerShell (Add-Type), so no .exe is shipped.
// NOTE: Windows PowerShell 5.1 compiles with C# 5 - keep the syntax old-school (no $"", ?., out var, "when").
//
// What it does: opens resources.assets (Unity SerializedFile v22+), finds the I2 Localization
// "I2Languages" object, replaces the English column with Russian strings (matched by term key),
// appends the rebuilt object to the end of the file and repoints the object table entry at it.
// Nothing else in the file is touched, so the patch survives unrelated game updates.
//
// Safety checks (the patcher refuses to write anything it is not sure about):
//   1. file header is sane and the declared size matches the real size;
//   2. every term has the same number of languages as the language list;
//   3. column 1 really is English ("en") - otherwise Russian would land in the wrong language;
//   4. at least 90% of translation keys exist in the game's table;
//   5. after writing, the new file is re-read: only the I2 object changed, every translated
//      string reads back exactly, and the term count is unchanged.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public class PatchException : Exception
{
    public PatchException(string message) : base(message) { }
}

public static class WotHPatcher
{
    const int EnglishColumn = 1;
    const string EnglishCode = "en";
    const double MinCoverage = 0.9;
    const int TermsOffset = 56; // header(PPtr, enabled, PPtr script, name "I2Languages") + 3 bools + 1 int

    const string Changed = "Структура файлов игры не совпадает с ожидаемой (вероятно, вышло обновление игры). " +
        "Проверьте, нет ли новой версии перевода: https://github.com/Ktulh/Whisper-of-the-House-RUS/releases/latest";

    static uint BE32(byte[] d, int p) { return (uint)(d[p] << 24 | d[p + 1] << 16 | d[p + 2] << 8 | d[p + 3]); }
    static long BE64(byte[] d, int p) { return ((long)BE32(d, p) << 32) | BE32(d, p + 4); }
    static void PutBE64(byte[] d, int p, long v) { for (int i = 7; i >= 0; i--) { d[p + i] = (byte)(v & 0xFF); v >>= 8; } }

    public static Dictionary<string, string> LoadTranslation(string path)
    {
        var map = new Dictionary<string, string>(StringComparer.Ordinal);
        string[] lines;
        try { lines = File.ReadAllLines(path, new UTF8Encoding(false, true)); }   // strict: bad bytes must not become '?'
        catch (DecoderFallbackException)
        {
            throw new PatchException("Файл перевода ru.tsv повреждён (не UTF-8). Скачайте архив с переводом заново.");
        }
        foreach (var line in lines)
        {
            if (line.Length == 0 || line[0] == '#') continue;
            int tab = line.IndexOf('\t');
            if (tab <= 0 || tab == line.Length - 1) continue;   // no key, or an empty translation: keep the game's text
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

    // ---- binary helpers (bounds-checked: a changed layout becomes a clean error, not garbage) ----
    class R
    {
        public byte[] D; public int P;
        void Need(long n) { if (n < 0 || (long)P + n > D.Length) throw new PatchException(Changed); }
        public int I32() { Need(4); int v = BitConverter.ToInt32(D, P); P += 4; return v; }
        public void Align() { P = (P + 3) & ~3; }
        public string S() { int n = I32(); Need(n); string v = Encoding.UTF8.GetString(D, P, n); P += n; Align(); return v; }
        public void SkipS() { int n = I32(); Need(n); P += n; Align(); }
        public void Skip(int n) { Need(n); P += n; Align(); }
    }

    class W
    {
        public MemoryStream M = new MemoryStream();
        public void I32(int v) { M.Write(BitConverter.GetBytes(v), 0, 4); }
        public void Align() { while (M.Length % 4 != 0) M.WriteByte(0); }
        public void Raw(byte[] d, int off, int len) { M.Write(d, off, len); }
        public void S(string v) { var b = Encoding.UTF8.GetBytes(v); I32(b.Length); M.Write(b, 0, b.Length); Align(); }
    }

    // ---- I2 LanguageSourceAsset payload ----
    class Parsed
    {
        public int TermCount;
        public List<string> Codes = new List<string>();
        public Dictionary<string, string> English = new Dictionary<string, string>(StringComparer.Ordinal);
    }

    static Parsed ParseI2(byte[] obj)
    {
        var r = new R { D = obj, P = TermsOffset };
        var res = new Parsed();
        int count = r.I32();
        if (count < 1000 || count > 500000) throw new PatchException(Changed);
        int langCount = -1;
        for (int t = 0; t < count; t++)
        {
            string term = r.S();
            int type = r.I32();
            int nl = r.I32();
            if (nl < 1 || nl > 64) throw new PatchException(Changed);
            if (langCount < 0) langCount = nl;
            else if (nl != langCount) throw new PatchException(Changed);
            for (int i = 0; i < nl; i++)
            {
                string v = r.S();
                if (i == EnglishColumn) res.English[term] = v;
            }
            r.Skip(r.I32());                       // flags
            int nt = r.I32();                      // touch-screen variants
            if (nt < 0 || nt > 64) throw new PatchException(Changed);
            for (int i = 0; i < nt; i++) r.SkipS();
        }
        res.TermCount = count;
        // language list: bool(4) + int + string, then count x { name, code, flags }
        r.I32(); r.I32(); r.SkipS();
        int nLang = r.I32();
        if (nLang != langCount) throw new PatchException(Changed);
        for (int i = 0; i < nLang; i++)
        {
            r.SkipS();                             // display name
            res.Codes.Add(r.S());                  // language code
            r.I32();                               // flags
        }
        return res;
    }

    static void CheckEnglishColumn(Parsed p)
    {
        if (p.Codes.Count <= EnglishColumn ||
            !string.Equals(p.Codes[EnglishColumn], EnglishCode, StringComparison.OrdinalIgnoreCase))
            throw new PatchException("В таблице игры изменился порядок языков: колонка английского теперь другая, " +
                "и русский текст попал бы не туда. Файлы игры не тронуты. Нужна новая версия перевода: " +
                "https://github.com/Ktulh/Whisper-of-the-House-RUS/releases/latest");
    }

    static byte[] RebuildI2(byte[] obj, Dictionary<string, string> tr, out int applied)
    {
        var r = new R { D = obj, P = TermsOffset };
        var w = new W();
        w.Raw(obj, 0, TermsOffset);
        int count = r.I32();
        w.I32(count);
        var matched = new HashSet<string>(StringComparer.Ordinal);
        for (int t = 0; t < count; t++)
        {
            int kstart = r.P; string term = r.S(); w.Raw(obj, kstart, r.P - kstart);   // key bytes copied untouched
            int type = r.I32(); w.I32(type);
            int nl = r.I32(); w.I32(nl);
            string ru;
            // any term type: the developers also stored real on-screen text in "Sprite"-type terms (e.g. the grandma's notes).
            // Only keys listed in ru.tsv are ever touched, so sprite/font names stay as they are.
            bool has = tr.TryGetValue(term, out ru);
            for (int i = 0; i < nl; i++)
            {
                int start = r.P;
                r.SkipS();
                if (has && i == EnglishColumn) { w.S(ru); matched.Add(term); }
                else w.Raw(obj, start, r.P - start);
            }
            int fstart = r.P; r.Skip(r.I32()); w.Raw(obj, fstart, r.P - fstart);
            int tstart = r.P; int nt = r.I32(); for (int i = 0; i < nt; i++) r.SkipS(); w.Raw(obj, tstart, r.P - tstart);
        }
        w.Raw(obj, r.P, obj.Length - r.P);
        applied = matched.Count;
        return w.M.ToArray();
    }

    // ---- SerializedFile handling ----
    static readonly byte[] NameSig = Encoding.ASCII.GetBytes("\x0b\0\0\0I2Languages");

    class Located { public int EntryPos; public long ObjStart; public int ObjSize; public long DataOffset; }

    static Located Locate(byte[] d)
    {
        if (d.Length < 64) throw new PatchException("Файл повреждён или это не файл ресурсов Unity.");
        uint version = BE32(d, 8);
        if (version < 22) throw new PatchException("Неподдерживаемая версия файла ресурсов: " + version + ".");
        if (d[16] != 0) throw new PatchException("Неподдерживаемый порядок байтов в файле ресурсов.");
        int metaSize = (int)BE32(d, 20);
        long fileSize = BE64(d, 24);
        long dataOffset = BE64(d, 32);
        if (fileSize != d.Length)
            throw new PatchException("Файл игры повреждён или докачан не полностью (размер не совпадает с заголовком). " +
                "Проверьте целостность файлов в Steam.");
        const int metaStart = 48;
        if (metaSize < 0 || metaStart + (long)metaSize > d.Length || dataOffset < metaStart || dataOffset > d.Length)
            throw new PatchException(Changed);

        // Find the object-table entry {int64 pathId, int64 byteStart, uint32 byteSize, int32 typeId} of I2Languages
        Located found = null;
        for (int p = metaStart; p + 24 <= metaStart + metaSize; p += 4)
        {
            long start = BitConverter.ToInt64(d, p + 8);
            uint size = BitConverter.ToUInt32(d, p + 16);
            if (size < 100000 || start < 0 || dataOffset + start + size > d.Length) continue;
            long at = dataOffset + start + 28; // after PPtr gameObject(12) + enabled(4) + PPtr script(12)
            if (at + NameSig.Length > d.Length) continue;
            bool match = true;
            for (int k = 0; k < NameSig.Length && match; k++) if (d[at + k] != NameSig[k]) match = false;
            if (!match) continue;
            // two candidates = we cannot know which one the game loads: refuse instead of guessing
            if (found != null) throw new PatchException(Changed);
            found = new Located { EntryPos = p, ObjStart = start, ObjSize = (int)size, DataOffset = dataOffset };
        }
        if (found == null) throw new PatchException("Таблица локализации I2Languages не найдена в файле игры. " + Changed);
        return found;
    }

    static byte[] GetObject(byte[] d, Located loc)
    {
        var obj = new byte[loc.ObjSize];
        Buffer.BlockCopy(d, (int)(loc.DataOffset + loc.ObjStart), obj, 0, loc.ObjSize);
        return obj;
    }

    static PatchException Unexpected(Exception ex)
    {
        return new PatchException(Changed + " [" + ex.GetType().Name + ": " + ex.Message + "]");
    }

    const string NoMemory = "Не хватает памяти для обработки файла игры. Закройте другие программы и запустите установщик снова.";

    /// <summary>Share (0..1) of the game's English-column strings that contain Cyrillic letters,
    /// i.e. "is this file already translated?". Independent of the translation version, so it still
    /// recognises a file patched by an older release. The original game has ~0.03% (4 strings).</summary>
    public static double CyrillicShare(string assetsPath)
    {
        try
        {
            byte[] d = File.ReadAllBytes(assetsPath);
            var parsed = ParseI2(GetObject(d, Locate(d)));
            int n = 0, c = 0;
            foreach (string v in parsed.English.Values)
            {
                if (v.Trim().Length == 0) continue;
                n++;
                foreach (char ch in v)
                    if ((ch >= 'А' && ch <= 'я') || ch == 'Ё' || ch == 'ё') { c++; break; }
            }
            return n == 0 ? 0.0 : (double)c / n;
        }
        catch (PatchException) { throw; }
        catch (IOException) { throw; }
        catch (UnauthorizedAccessException) { throw; }
        catch (OutOfMemoryException) { throw new PatchException(NoMemory); }
        catch (Exception ex) { throw Unexpected(ex); }
    }

    public static string Patch(string assetsPath, string translationPath, string outPath)
    {
        try { return DoPatch(assetsPath, translationPath, outPath); }
        catch (PatchException) { throw; }
        catch (IOException) { throw; }
        catch (UnauthorizedAccessException) { throw; }
        catch (OutOfMemoryException) { throw new PatchException(NoMemory); }
        catch (Exception ex) { throw Unexpected(ex); }
    }

    static string DoPatch(string assetsPath, string translationPath, string outPath)
    {
        byte[] d = File.ReadAllBytes(assetsPath);
        Located loc = Locate(d);
        byte[] obj = GetObject(d, loc);
        var tr = LoadTranslation(translationPath);
        if (tr.Count == 0) throw new PatchException("Файл перевода (ru.tsv) пуст или повреждён.");

        Parsed parsed = ParseI2(obj);   // checks 1-2
        CheckEnglishColumn(parsed);     // check 3

        int applied;
        byte[] nobj = RebuildI2(obj, tr, out applied);
        if (applied < MinCoverage * tr.Count)  // check 4
            throw new PatchException(string.Format(
                "В таблице игры найдено только {0} из {1} строк перевода. Игра, вероятно, сильно обновилась. " +
                "Файлы игры не тронуты. Проверьте новую версию перевода: " +
                "https://github.com/Ktulh/Whisper-of-the-House-RUS/releases/latest", applied, tr.Count));

        // Append new object at the end (8-byte aligned relative to data start), repoint entry, fix header size
        long newStart = d.Length - loc.DataOffset;
        int pad = (int)((8 - (newStart % 8)) % 8);
        newStart += pad;
        long newFileSize = loc.DataOffset + newStart + nobj.Length;
        PutBE64(d, 24, newFileSize);
        Buffer.BlockCopy(BitConverter.GetBytes(newStart), 0, d, loc.EntryPos + 8, 8);
        Buffer.BlockCopy(BitConverter.GetBytes((uint)nobj.Length), 0, d, loc.EntryPos + 16, 4);

        using (var fs = new FileStream(outPath, FileMode.Create, FileAccess.Write))
        {
            fs.Write(d, 0, d.Length);
            fs.Write(new byte[pad], 0, pad);
            fs.Write(nobj, 0, nobj.Length);
        }

        try { VerifyOutput(outPath, d, tr, parsed.TermCount); }   // check 5
        catch
        {
            try { File.Delete(outPath); } catch (Exception) { }   // never let cleanup hide the real error
            throw;
        }
        return string.Format("Вписано строк перевода: {0} из {1}", applied, tr.Count);
    }

    // d = original bytes with only header/table fields modified (all of those lie before the data area)
    static void VerifyOutput(string path, byte[] d, Dictionary<string, string> tr, int expectedTerms)
    {
        byte[] n = File.ReadAllBytes(path);
        Located loc = Locate(n);                       // also checks declared size == real size
        if (n.Length < d.Length) throw new PatchException("Проверка записи не пройдена: новый файл короче оригинала.");
        for (long i = loc.DataOffset; i < d.Length; i++)
            if (n[i] != d[i]) throw new PatchException("Проверка записи не пройдена: изменились данные, которые трогать не планировалось.");
        Parsed p = ParseI2(GetObject(n, loc));
        if (p.TermCount != expectedTerms) throw new PatchException("Проверка записи не пройдена: изменилось число строк таблицы.");
        CheckEnglishColumn(p);
        foreach (var kv in tr)
        {
            string v;
            if (p.English.TryGetValue(kv.Key, out v) && v != kv.Value)
                throw new PatchException("Проверка записи не пройдена: строка «" + kv.Key + "» записалась неверно.");
        }
    }
}
