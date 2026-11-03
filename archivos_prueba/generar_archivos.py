#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera los archivos de prueba del Laboratorio 1 (NTFS) de forma reproducible.
Semilla fija -> mismos bytes en cada ejecucion -> los hashes del anexo coinciden.
"""
import json
import os
import random

BASE = os.path.dirname(os.path.abspath(__file__))

def w(rel, data):
    p = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    print(f"{rel:45s} {os.path.getsize(p):>9d} bytes")

# 1) Archivo obligatorio de la guia (contenido exacto, 3 lineas, UTF-8)
w("LAB_NTFS.txt",
  "Arquitectura del Computador\n"
  "Laboratorio de sistemas de archivos NTFS\n"
  "Archivo de prueba para análisis hexadecimal\n")

# 2) Justo por encima del umbral residente (~700-800 B) -> NO residente, 1 run
rnd = random.Random(2026)
chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,;-\n"
w("umbral_residente.txt", "".join(rnd.choice(chars) for _ in range(2000)))

# 3) Archivo grande NO residente (12 MiB, PRNG determinista)
rnd = random.Random(12345)
w("aleatorio_12MB.bin", bytes(rnd.getrandbits(8) for _ in range(12 * 1024 * 1024)))

# 4) Carpeta docs con archivos pequenos (residentes) y uno no residente
w("docs/notas_laboratorio.txt",
  "Notas de laboratorio\n"
  "=====================\n"
  "Volumen: LAB_NTFS (imagen de 512 MB)\n"
  "Cluster: 4096 bytes (8 sectores de 512)\n"
  "Registro MFT: 1024 bytes\n"
  "MFT en LCN: 4  ->  offset 0x4000 respecto del volumen\n"
  "Directorio raiz: registro MFT numero 5\n")
w("docs/resumen_ntfs.txt",
  "NTFS organiza los metadatos en registros de 1024 bytes llamados\n"
  "entradas de la MFT. Cada entrada contiene atributos tipados:\n"
  "0x10 STANDARD_INFORMATION, 0x30 FILE_NAME, 0x80 DATA.\n"
  "Este archivo cabe completo dentro del registro (residente).\n")
w("docs/tabla_offsets.csv",
  "offset,campo,bytes\n"
  "0x03,OEM ID,8\n"
  "0x0B,Bytes por sector,2\n"
  "0x0D,Sectores por cluster,1\n"
  "0x28,Total de sectores,8\n"
  "0x30,LCN de $MFT,8\n"
  "0x38,LCN de $MFTMirr,8\n"
  "0x40,Tamano de registro MFT,1\n"
  "0x48,Numero de serie,8\n"
  "0x1FE,Firma de arranque,2\n")
w("docs/datos.json",
  json.dumps({"volumen": "LAB_NTFS", "clusters": 130813, "bytes_por_cluster": 4096,
              "mft_lcn": 4, "mft_registro": 1024}, indent=2) + "\n")
w("docs/LEEME.md",
  "# Carpeta docs\nArchivos de prueba del Laboratorio 1 de NTFS.\n")
w("docs/teoria/apuntes_tsk.txt",
  "Comandos de The Sleuth Kit usados en la practica:\n"
  "  mmls   -> tabla de particiones (MBR/GPT)\n"
  "  fsstat -> parametros del sistema de archivos (B, S, LCN de $MFT)\n"
  "  fls    -> listado recursivo con el numero de registro MFT\n"
  "  istat  -> atributos y runlist de un registro MFT\n"
  "  icat    -> contenido de un archivo por numero de registro\n")

# 5) 60 archivos diminutos -> fuerza $INDEX_ALLOCATION en la carpeta
for i in range(1, 61):
    w(f"muchos/ficha_{i:02d}.txt",
      f"Ficha {i:02d} del Laboratorio 1\n"
      f"Registro MFT a localizar con fls.\n"
      f"Marca de verificacion: NTFS-{i:02d}-{i * 37:04d}\n")

# 6) Archivo altamente comprimible (~100 KB) - se escribe en el volumen con
#    compresion activa desde la fase de copiado (ver crear_comprimido.sh).
w("comprimido.txt",
  ("Arquitectura del Computador - Laboratorio de NTFS\n" * 2000))

print("\nTotal generado en:", BASE)
