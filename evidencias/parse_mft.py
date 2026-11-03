#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_mft.py - Recorre un registro de la MFT de NTFS byte a byte.

Uso:  python3 parse_mft.py <registro_MFT>

Lee ntfs_lab.img, aplica la correccion del Update Sequence Array (USA) y
muestra la cabecera y la lista de atributos con sus offsets absolutos dentro
de la imagen.  Sirve como comprobacion independiente de istat (The Sleuth Kit).
"""
import struct
import sys
import os

IMG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ntfs_lab.img")
PART_START = 2048
V = PART_START * 512

TIPOS = {
    0x10: "$STANDARD_INFORMATION",
    0x20: "$ATTRIBUTE_LIST",
    0x30: "$FILE_NAME",
    0x40: "$OBJECT_ID",
    0x50: "$SECURITY_DESCRIPTOR",
    0x60: "$VOLUME_NAME",
    0x70: "$VOLUME_INFORMATION",
    0x80: "$DATA",
    0x90: "$INDEX_ROOT",
    0xA0: "$INDEX_ALLOCATION",
    0xB0: "$BITMAP",
    0xC0: "$REPARSE_POINT",
    0xD0: "$EA_INFORMATION",
    0xE0: "$EA",
    0x100: "$LOGGED_UTILITY_STREAM",
}


def main(n):
    raw = open(IMG, "rb").read()
    vbr = raw[V:V + 512]
    B = struct.unpack_from("<H", vbr, 0x0B)[0]
    S = vbr[0x0D]
    C = B * S
    lcn = struct.unpack_from("<Q", vbr, 0x30)[0]
    off_mft = V + lcn * C
    val = struct.unpack_from("<b", vbr, 0x40)[0]
    R = 1 << (-val) if val < 0 else val * C
    off = off_mft + n * R
    rec = bytearray(raw[off:off + R])

    print(f"Imagen............: {IMG}")
    print(f"Offset del registro: {off} = 0x{off:X}  (MFT en 0x{off_mft:X}, R={R})")
    print(f"Firma.............: {rec[0:4].decode('ascii', 'replace')}")
    usa_off, usa_cnt = struct.unpack_from("<HH", rec, 4)
    print(f"USA (fixups)......: offset {usa_off}, {usa_cnt} entradas")
    print(f"Secuencia.........: {struct.unpack_from('<H', rec, 16)[0]}")
    print(f"Hard links........: {struct.unpack_from('<H', rec, 18)[0]}")
    attr_off, flags = struct.unpack_from("<HH", rec, 20)
    print(f"Offset atributos..: {attr_off}")
    print(f"Flags.............: 0x{flags:04x} " +
          ("IN_USE " if flags & 1 else "LIBRE ") + ("DIRECTORY" if flags & 2 else "ARCHIVO"))
    print(f"Bytes usados......: {struct.unpack_from('<I', rec, 24)[0]}")
    print(f"Bytes asignados...: {struct.unpack_from('<I', rec, 28)[0]}")

    # Aplicar los fixups: el ultimo word de cada sector se reemplaza por el
    # valor guardado en el Update Sequence Array.
    usa = [struct.unpack_from("<H", rec, usa_off + 2 * i)[0] for i in range(usa_cnt)]
    for i in range(1, usa_cnt):
        pos = i * B - 2
        rec[pos:pos + 2] = struct.pack("<H", usa[i])

    print("\nAtributos:")
    p = attr_off
    while True:
        tipo = struct.unpack_from("<I", rec, p)[0]
        if tipo == 0xFFFFFFFF:
            print(f"  0x{p:04x}  fin de atributos (0xFFFFFFFF)")
            break
        largo = struct.unpack_from("<I", rec, p + 4)[0]
        nr = rec[p + 8]
        nlen, noff = rec[p + 9], struct.unpack_from("<H", rec, p + 10)[0]
        ida = struct.unpack_from("<H", rec, p + 14)[0]
        nombre = rec[p + noff:p + noff + 2 * nlen].decode("utf-16-le", "replace") if nlen else ""
        etiqueta = TIPOS.get(tipo, f"0x{tipo:X}")
        print(f"  0x{p:04x}  tipo 0x{tipo:03X} {etiqueta:<22} len={largo:<4} id={ida}"
              + (f"  nombre='{nombre}'" if nombre else ""))
        if nr == 0:
            vlen = struct.unpack_from("<I", rec, p + 16)[0]
            voff = struct.unpack_from("<H", rec, p + 20)[0]
            ini = p + voff
            print(f"          RESIDENTE  valor: {vlen} bytes en absoluto 0x{ini:X} (relativo +0x{voff:X})")
            if vlen:
                muestra = rec[ini:ini + vlen]
                if tipo == 0x30:      # FILE_NAME
                    print(f"          nombre real: {muestra[66:66 + 2*muestra[64]].decode('utf-16-le','replace')}")
                    print(f"          padre MFT  : {struct.unpack_from('<Q', muestra, 0)[0] & 0xFFFFFFFFFFFF}")
                elif tipo in (0x80, 0x90):
                    print(f"          primeros bytes: {muestra[:32]!r}")
        else:
            svcn, evcn = struct.unpack_from("<QQ", rec, p + 16)
            roff, cu = struct.unpack_from("<HH", rec, p + 32)
            alloc, real, init = struct.unpack_from("<QQQ", rec, p + 40)
            print(f"          NO RESIDENTE  VCN {svcn}-{evcn}  unidad de compresion={cu}")
            print(f"          offset runlist +0x{roff:X}  alloc={alloc} real={real} init={init}")
            rb = rec[p + roff:p + largo]
            print(f"          runlist (hex): {rb[:24].hex(' ')}")
            # decodificar mapping pairs
            i, lcn, vcn = 0, 0, svcn
            while i < len(rb) and rb[i] != 0:
                h = rb[i]
                nl, no = h & 0x0F, h >> 4
                i += 1
                if nl == 0:
                    break
                length = int.from_bytes(rb[i:i + nl], "little")
                i += nl
                delta = int.from_bytes(rb[i:i + no], "little", signed=True)
                i += no
                lcn += delta
                print(f"            VCN {vcn:<8} LCN {lcn:<8} longitud {length:<6} clusters")
                vcn += length
        p += largo


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
