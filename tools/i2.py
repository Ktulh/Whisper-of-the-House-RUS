"""Reader/writer for the serialized I2 Localization LanguageSourceAsset (no typetree needed).

Layout (Unity 2021.3, little-endian, 4-byte aligned):
  MonoBehaviour header: PPtr m_GameObject, u8 m_Enabled (aligned), PPtr m_Script, string m_Name
  LanguageSourceData mSource:
    u8 x3 (bools, aligned)       -- UserAgrees..., GoogleLiveSyncIsUptoDate
    i32 ?                        -- kept verbatim (the "prefix" below)
    List<TermData> mTerms        -- {string Term; i32 TermType; string[] Languages; u8[] Flags; string[] Languages_Touch}
    ... everything after mTerms is kept verbatim except mLanguages, which we parse for reference.
"""
import struct

TERMS_COUNT_OFFSET = 56  # verified against the shipped asset


class Reader:
    def __init__(self, d, p=0):
        self.d, self.p = d, p

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def align(self):
        self.p = (self.p + 3) & ~3

    def s(self):
        n = self.i32()
        v = self.d[self.p:self.p + n].decode("utf-8")
        self.p += n
        self.align()
        return v

    def bytes_arr(self):
        n = self.i32()
        v = self.d[self.p:self.p + n]
        self.p += n
        self.align()
        return v


class Writer:
    def __init__(self):
        self.b = bytearray()

    def i32(self, v):
        self.b += struct.pack("<i", v)

    def align(self):
        while len(self.b) % 4:
            self.b.append(0)

    def s(self, v):
        e = v.encode("utf-8")
        self.i32(len(e))
        self.b += e
        self.align()

    def bytes_arr(self, v):
        self.i32(len(v))
        self.b += v
        self.align()


def parse(raw):
    r = Reader(raw, TERMS_COUNT_OFFSET)
    terms = []
    for _ in range(r.i32()):
        term = r.s()
        ttype = r.i32()
        langs = [r.s() for _ in range(r.i32())]
        flags = r.bytes_arr()
        touch = [r.s() for _ in range(r.i32())]
        terms.append({"term": term, "type": ttype, "langs": langs, "flags": flags, "touch": touch})
    tail = raw[r.p:]
    # languages list lives right after: bool(4) + i32 + string(appname) + List<LanguageData>
    t = Reader(tail)
    t.i32(); t.i32(); t.s()
    languages = []
    for _ in range(t.i32()):
        name, code = t.s(), t.s()
        flags = t.i32()  # u8 + align
        languages.append({"name": name, "code": code, "flags": flags})
    return {"head": raw[:TERMS_COUNT_OFFSET], "terms": terms, "tail": tail, "languages": languages}


def serialize(doc):
    w = Writer()
    w.b += doc["head"]
    w.i32(len(doc["terms"]))
    for t in doc["terms"]:
        w.s(t["term"])
        w.i32(t["type"])
        w.i32(len(t["langs"]))
        for v in t["langs"]:
            w.s(v)
        w.bytes_arr(t["flags"])
        w.i32(len(t["touch"]))
        for v in t["touch"]:
            w.s(v)
    w.b += doc["tail"]
    return bytes(w.b)
