#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrae y documenta la evidencia del Laboratorio 1 (NTFS) a partir de ntfs_lab.img.

Uso:  python3 analizar.py
Salida: archivos de evidencia en este mismo directorio + resumen por consola.

Todo el analisis es de solo lectura sobre la imagen: nunca se abre el volumen en
modo escritura ni se tocan sectores del dispositivo original.
"""
import hashlib
import os
import re
import struct
import subprocess

AQUI = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(os.path.dirname(AQUI), "ntfs_lab.img")
IMGQ = f'"{IMG}"'   # ruta entre comillas para el shell
SRC = os.path.join(os.path.dirname(AQUI), "archivos_prueba")
PART_START = 2048          # sector donde comienza la particion (tabla MBR)
V = PART_START * 512       # desplazamiento del volumen dentro de la imagen


def sh(cmd):
    """Ejecuta un comando y devuelve su salida (texto)."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout + r.stderr


def guardar(nombre, texto):
    ruta = os.path.join(AQUI, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return ruta


def guardar_bin(nombre, datos):
    with open(os.path.join(AQUI, nombre), "wb") as f:
        f.write(datos)


# --------------------------------------------------------------------------
# 1. Sector de arranque (VBR) y tabla de campos
# --------------------------------------------------------------------------
raw = open(IMG, "rb").read()
vbr = raw[V:V + 512]
u16 = lambda o: struct.unpack_from("<H", vbr, o)[0]
u32 = lambda o: struct.unpack_from("<I", vbr, o)[0]
u64 = lambda o: struct.unpack_from("<Q", vbr, o)[0]
i8 = lambda o: struct.unpack_from("<b", vbr, o)[0]

B = u16(0x0B)                 # bytes por sector
S = vbr[0x0D]                 # sectores por cluster
C = B * S                     # tamano de cluster
LCN_MFT = u64(0x30)
LCN_MIRR = u64(0x38)
mft_val = i8(0x40)            # 0xF6 = -10 -> 2^10
R = 1 << (-mft_val) if mft_val < 0 else mft_val * C
idx_val = i8(0x44)
RIDX = 1 << (-idx_val) if idx_val < 0 else idx_val * C
SERIAL = u64(0x48)
TOTAL = u64(0x28)
OFF_MFT = V + LCN_MFT * C

tabla = f"""# Tabla 2.1 - Campos del VBR de NTFS (valores reales de ntfs_lab.img)

| Offset | Campo | Bytes | Valor hexadecimal | Valor decimal / interpretacion |
|---|---|---|---|---|
| 0x00-0x02 | Instruccion de salto (JMP) | 3 | `{vbr[0:3].hex()}` | Salto al codigo de arranque |
| 0x03-0x0A | OEM ID | 8 | `{vbr[3:11].hex()}` | `{vbr[3:11].decode('ascii', 'replace')}` |
| 0x0B-0x0C | Bytes por sector | 2 | `{vbr[0x0B:0x0D].hex()}` | {B} |
| 0x0D | Sectores por cluster | 1 | `{vbr[0x0D]:02x}` | {S} |
| 0x0E-0x0F | Sectores reservados | 2 | `{vbr[0x0E:0x10].hex()}` | {u16(0x0E)} |
| 0x15 | Descriptor de medio | 1 | `{vbr[0x15]:02x}` | 0xF8 = disco fijo |
| 0x18-0x19 | Sectores por pista | 2 | `{vbr[0x18:0x1A].hex()}` | {u16(0x18)} |
| 0x1A-0x1B | Cabezas | 2 | `{vbr[0x1A:0x1C].hex()}` | {u16(0x1A)} |
| 0x1C-0x1F | Sectores ocultos | 4 | `{vbr[0x1C:0x20].hex()}` | {u32(0x1C)} (= inicio de la particion) |
| 0x28-0x2F | Total de sectores | 8 | `{vbr[0x28:0x30].hex()}` | {TOTAL} (0x{TOTAL:X}) |
| 0x30-0x37 | LCN inicial de $MFT | 8 | `{vbr[0x30:0x38].hex()}` | {LCN_MFT} |
| 0x38-0x3F | LCN inicial de $MFTMirr | 8 | `{vbr[0x38:0x40].hex()}` | {LCN_MIRR} |
| 0x40 | Tamano de registro MFT | 1 | `{vbr[0x40]:02x}` | {mft_val} -> 2^{abs(mft_val)} = {R} bytes |
| 0x44 | Tamano de registro de indice | 1 | `{vbr[0x44]:02x}` | {idx_val} cluster = {RIDX} bytes |
| 0x48-0x4F | Numero de serie del volumen | 8 | `{vbr[0x48:0x50].hex()}` | 0x{SERIAL:016X} |
| 0x1FE-0x1FF | Firma de arranque | 2 | `{vbr[0x1FE:0x200].hex()}` | 55 AA |
"""
guardar("04_tabla_vbr.md", tabla)

# --------------------------------------------------------------------------
# 2. Calculos de offsets
# --------------------------------------------------------------------------
calc = f"""# Calculo de offsets (valores reales)

## Parametros leidos del VBR
- Bytes por sector  B = {B}
- Sectores por cluster S = {S}
- Tamano de cluster  C = B x S = {B} x {S} = {C} bytes
- LCN inicial de $MFT = {LCN_MFT}
- Desplazamiento del volumen en la imagen V = {PART_START} x 512 = {V} bytes = 0x{V:X}
- Tamano de registro MFT R = {R} bytes (byte 0x40 = 0x{vbr[0x40]:02x} = {mft_val} -> 2^{-mft_val})

## Offset del inicio de la MFT
OffsetMFT = V + (LCN_MFT x C)
          = {V} + ({LCN_MFT} x {C})
          = {V} + {LCN_MFT * C}
          = {OFF_MFT} bytes = 0x{OFF_MFT:X}

## Offset del registro N de la MFT
Offsetregistro = OffsetMFT + (N x R)
  N = 5   ($Root)      -> {OFF_MFT} + 5 x {R}   = {OFF_MFT + 5*R}   = 0x{OFF_MFT + 5*R:X}
  N = 64  (LAB_NTFS.txt) -> {OFF_MFT} + 64 x {R} = {OFF_MFT + 64*R} = 0x{OFF_MFT + 64*R:X}

## Offset de los datos de un archivo no residente
Offsetdatos = V + (LCN x C)
  ejemplo LCN=20552 -> {V} + 20552 x {C} = {V + 20552*C} = 0x{V + 20552*C:X}
"""
guardar("05_calculos.txt", calc)

# --------------------------------------------------------------------------
# 3. Volcados de estructuras
# --------------------------------------------------------------------------
guardar("01_mmls.txt", sh(f"mmls {IMGQ}"))
guardar("02_fsstat.txt", sh(f"fsstat -o {PART_START} {IMGQ}"))
guardar("03_vbr_hex.txt", sh(f"xxd -s {V} -l 512 {IMGQ}"))

# registro 0 de la MFT ($MFT)
guardar("06_mft_registro0_hex.txt",
        sh(f"xxd -s {OFF_MFT} -l 256 {IMGQ}"))
# registro 5 ($Root)
guardar("07_root_istat.txt", sh(f"istat -o {PART_START} {IMGQ} 5"))
guardar("08_root_hex.txt", sh(f"xxd -s {OFF_MFT + 5*R} -l {R} {IMGQ}"))
# listados
fls = sh(f"fls -r -p -o {PART_START} {IMGQ}")
guardar("09_fls_recursivo.txt", fls)
guardar("10_fls_eliminados.txt", sh(f"fls -r -d -p -o {PART_START} {IMGQ}"))


def nreg(nombre):
    """Numero de registro MFT (inodo) de un archivo segun fls."""
    m = re.search(r"^\S+\s+(\d+)-\d+-\d+:\s+" + re.escape(nombre) + r"\s*$", fls, re.M)
    return int(m.group(1)) if m else None


def istat(n):
    return sh(f"istat -o {PART_START} {IMGQ} {n}")


def runlist(n):
    """Primer LCN y lista de runs de %DATA no residente."""
    out = istat(n)
    m = re.search(r"Type: \$DATA \(128-\d+\).*?Non-Resident.*?\n(.*?)(?:\n\n|\Z)", out, re.S)
    if not m:
        return None
    pares = [int(x) for x in re.findall(r"\d+", m.group(1))]
    return pares


def sha(b):
    return hashlib.sha256(b).hexdigest()


objetivo = "LAB_NTFS.txt"
n_lab = nreg(objetivo)
guardar("11_istat_LAB_NTFS.txt", istat(n_lab))
guardar("12_hex_registro_LAB_NTFS.txt",
        sh(f"xxd -s {OFF_MFT + n_lab*R} -l {R} {IMGQ}"))
contenido = sh(f"icat -o {PART_START} {IMGQ} {n_lab}")
guardar_bin("13_contenido_extraido_LAB_NTFS.txt", contenido.encode())
guardar_bin("13b_contenido_original_LAB_NTFS.txt",
            open(os.path.join(SRC, objetivo), "rb").read())

resumen = [f"Archivo de prueba: {objetivo}  -> registro MFT {n_lab}",
           f"  offset del registro = 0x{OFF_MFT + n_lab*R:X}",
           f"  sha256 extraido  = {sha(contenido.encode())}",
           f"  sha256 original  = {sha(open(os.path.join(SRC, objetivo),'rb').read())}"]

# archivos no residentes de interes
for nombre, etiqueta in [("aleatorio_12MB.bin", "aleatorio_12MB"),
                         ("datos_patron_8MB.bin", "datos_patron_8MB"),
                         ("comprimidos/comprimido.txt", "comprimido")]:
    n = nreg(nombre)
    if n is None:
        resumen.append(f"{nombre}: NO encontrado en fls")
        continue
    info = istat(n)
    guardar(f"14_istat_{etiqueta}.txt", info)
    pares = runlist(n)
    resumen.append(f"{nombre} -> registro MFT {n}, primer LCN {pares[0] if pares else '?'}")
    if pares:
        lcn = pares[0]
        guardar(f"15_hex_datos_{etiqueta}.txt",
                sh(f"xxd -s {V + lcn*C} -l 160 {IMGQ}"))
        resumen.append(f"   offset de datos = V + LCN*C = {V} + {lcn}*{C} = {V + lcn*C} = 0x{V + lcn*C:X}")

guardar("16_resumen.txt", "\n".join(resumen) + "\n")
print("\n".join(resumen))
print("\nEvidencias escritas en:", AQUI)
