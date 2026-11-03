#!/usr/bin/env python3
"""
Genera el mapa de registros MFT de ntfs_lab.img (solo lectura).

Salida: mapa_registros.json
  - Un objeto por registro 0..139 con cabecera, atributos y ubicación de $DATA.

Uso:  python3 mapa_registros.py [imagen] [salida.json]
"""
import json
import struct
import subprocess
import sys

IMG = sys.argv[1] if len(sys.argv) > 1 else "ntfs_lab.img"
OUT = sys.argv[2] if len(sys.argv) > 2 else "mapa_registros.json"

OFFSET_PART = 2048 * 512          # V = 0x100000
REC = 1024
MFT = OFFSET_PART + 4 * 4096      # 0x104000
CLUSTER = 4096
FIRST = 0
LAST = 139

ATTR = {0x10: "STANDARD_INFORMATION", 0x20: "ATTRIBUTE_LIST", 0x30: "FILE_NAME",
        0x40: "OBJECT_ID", 0x50: "SECURITY_DESCRIPTOR", 0x60: "VOLUME_NAME",
        0x70: "VOLUME_INFORMATION", 0x80: "DATA", 0x90: "INDEX_ROOT",
        0xA0: "INDEX_ALLOCATION", 0xB0: "BITMAP", 0xC0: "REPARSE_POINT",
        0xD0: "EA_INFORMATION", 0xE0: "EA", 0x100: "LOGGED_UTILITY_STREAM"}


def runs(buf):
    """Decodifica una runlist NTFS -> [(lcn, largo), ...]"""
    out, lcn, i = [], 0, 0
    while i < len(buf):
        head = buf[i]
        if head == 0:
            break
        ln, on = head & 0x0F, head >> 4
        if ln == 0:
            break
        length = int.from_bytes(buf[i + 1:i + 1 + ln], "little")
        if on == 0:                      # run disperso: sin LCN
            out.append([None, length])
            i += 1 + ln
            continue
        raw = buf[i + 1 + ln:i + 1 + ln + on]
        delta = int.from_bytes(raw, "little", signed=True)
        lcn += delta
        out.append([lcn, length])
        i += 1 + ln + on
    return out


def attributes(rec):
    """Recorre la cadena de atributos y devuelve una lista de dicts."""
    attrs = []
    off = struct.unpack_from("<H", rec, 0x14)[0]
    while off + 8 <= len(rec):
        typ, length = struct.unpack_from("<II", rec, off)
        if typ == 0xFFFFFFFF or length == 0:
            break
        non_res = rec[off + 0x08]
        name_len = rec[off + 0x09]
        name_off = struct.unpack_from("<H", rec, off + 0x0A)[0]
        name = rec[off + name_off:off + name_off + name_len * 2].decode("utf-16le", "replace") if name_len else ""
        a = {"type": ATTR.get(typ, hex(typ)), "name": name, "len": length, "resident": non_res == 0}
        if non_res == 0:
            vlen, voff = struct.unpack_from("<IH", rec, off + 0x10)
            a["size"] = vlen
            a["value_offset"] = MFT + 0  # se rellena fuera (necesita base)
            a["_val_abs"] = off + voff  # relativo al registro
        else:
            roff = struct.unpack_from("<H", rec, off + 0x20)[0]
            alloc, real, init = struct.unpack_from("<QQQ", rec, off + 0x28)
            a["size"] = real
            a["alloc_size"] = alloc
            a["init_size"] = init
            a["runs"] = runs(rec[off + roff:off + length])
            a["compression_unit"] = struct.unpack_from("<H", rec, off + 0x22)[0]
        attrs.append(a)
        off += length
    return attrs


def fls_names():
    """nombre -> numero de registro MFT (incluye borrados y huerfanos)."""
    out = {}
    try:
        txt = subprocess.run(["fls", "-o", "2048", "-r", "-p", IMG],
                             capture_output=True, text=True, check=True).stdout
    except Exception:
        return out
    for line in txt.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, name = parts
        fields = meta.split()
        if len(fields) < 2:
            continue
        try:
            n = int(next(f.split("-")[0] for f in fields if f.split("-")[0].isdigit()), 10)
        except (StopIteration, ValueError):
            continue
        out.setdefault(n, name.strip())
    return out


def main():
    blob = open(IMG, "rb").read()
    names = fls_names()
    recs = []
    for n in range(FIRST, LAST + 1):
        base = MFT + n * REC
        rec = blob[base:base + REC]
        sig = rec[:4]
        entry = {"n": n, "offset": base, "offset_hex": hex(base), "exists": sig == b"FILE"}
        if not entry["exists"]:
            entry["name"] = None
            entry["kind"] = "free"
            recs.append(entry)
            continue
        seq, links = struct.unpack_from("<HH", rec, 0x10)
        flags = struct.unpack_from("<H", rec, 0x16)[0]
        used = struct.unpack_from("<I", rec, 0x18)[0]
        attrs = attributes(rec)
        is_dir = bool(flags & 0x0002)
        name = names.get(n)
        if name and n <= 26 and ":" in name:
            name = name.split(":", 1)[0]
        if n == 5:
            name = "$Root"
        if n <= 11:
            kind = "system"
        elif n <= 15:
            kind = "reserved"      # en uso pero sin nombre
        elif n <= 23:
            kind = "orphan"        # libres sin nombre
        elif n <= 26:
            kind = "system"        # $Extend
        elif flags & 0x0001 == 0:
            kind = "free"
        else:
            kind = "dir" if is_dir else "file"
        entry.update({
            "name": name,
            "kind": kind,
            "is_dir": is_dir,
            "flags": flags,
            "links": links,
            "seq": seq,
            "used": used,
            "attrs": [],
        })
        for a in attrs:
            item = {
                "type": a["type"],
                "name": a["name"],
                "resident": a["resident"],
                "size": a.get("size", 0),
            }
            if a["resident"]:
                item["value_offset_hex"] = hex(base + a["_val_abs"])
            else:
                item["runs"] = a["runs"]
                first = next((r[0] for r in a["runs"] if r[0] is not None), None)
                item["lcn"] = first
                item["data_offset_hex"] = hex(OFFSET_PART + first * CLUSTER) if first is not None else None
                if any(r[0] is None for r in a["runs"]) and a["size"]:
                    if a.get("compression_unit"):
                        item["compressed"] = True
                    else:
                        item["sparse"] = True
                if a.get("compression_unit"):
                    item["compression_unit"] = a["compression_unit"]
            entry["attrs"].append(item)
        # $DATA principal: el de mayor tamaño (cubre el caso $Bad de $BadClus)
        datas = [x for x in entry["attrs"] if x["type"] == "DATA"]
        main_data = max(datas, key=lambda x: x["size"]) if datas else None
        entry["data"] = main_data
        recs.append(entry)

    doc = {
        "imagen": IMG,
        "V_hex": hex(OFFSET_PART),
        "cluster": CLUSTER,
        "record_size": REC,
        "mft_offset_hex": hex(MFT),
        "formula": "offset = 0x%X + n * 1024" % MFT,
        "total_clusters": 130813,
        "free_clusters": 124887,
        "records": recs,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("escrito:", OUT, "|", len(recs), "registros")


if __name__ == "__main__":
    main()
