# Bitácora de laboratorio — Análisis de NTFS desde cero

**Ejecuta:** Julian
**Máquina:** Arch Linux (kernel 7.2.11-arch1-1), sleuthkit 4.15.0, ntfs-3g 2026.9.28, ghex 50.4
**Fecha de inicio:** 2026-10-24
**Fecha de cierre:** 2026-10-25
**Imagen analizada:** `ntfs_lab.img` (536 870 912 B = 512 MiB)

---

## 0. Reglas de trabajo

1. La imagen original **nunca se abre en modo escritura**. Solo lectura.
2. Toda escritura (crear/borrar archivos) se hace sobre una **copia** en `trabajo/`.
3. Cada paso se documenta aquí con: comando → salida → interpretación.
4. **Prueba de integridad:** el hash al final del laboratorio debe ser idéntico al inicial.

| | SHA-256 |
|---|---|
| Inicio (2026-10-24) | `b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f` |
| Final (2026-10-25) | `b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f` |
| **¿Idéntico?** | **Sí** — la imagen no sufrió ninguna modificación |

---

## Inventario de evidencias

| Archivo | Paso | Contenido |
|---|---|---|
| `01_mmls.txt` | 1 | Tabla de particiones (`mmls`) y `fdisk -l` |
| `02_mbr_hex.txt` | 1 | Volcado hexadecimal del MBR desde 0x1BE |
| `03_vbr_hex.txt` | 2 | 512 B del sector de arranque NTFS en 0x100000 |
| `04_copia_vbr.txt` | 2 | Comparación VBR ↔ copia de respaldo del último sector |
| `05_fsstat.txt` | 3 | Parámetros del sistema de archivos (`fsstat`) |
| `06_ntfsinfo.txt` | 3 | Contraste con `ntfsinfo` sobre el volumen extraído |
| `07_mft_offset_hex.txt` | 4 | Firma `FILE` del registro `$MFT` en 0x104000 |
| `08_fls_raiz.txt` | 5 | Entradas del directorio raíz |
| `09_fls_recursivo.txt` | 5 | Recorrido recursivo del volumen |
| `10_root_istat.txt` | 5 | Atributos del registro 5 (`$Root`) |
| `11_root_hex.txt` | 5 | Registro 5 completo en hexadecimal |
| `12_istat_64.txt` | 6 | Metadatos de `LAB_NTFS.txt` |
| `13_hex_registro_64.txt` | 6 | Registro MFT 64 completo |
| `14_istat_66.txt` | 7 | Metadatos de `aleatorio_12MB.bin` |
| `15_aleatorio_hex.txt` | 7 | Datos del archivo en 0x05148000 |
| `16_istat_67.txt` | 8.1 | Metadatos de `datos_patron_8MB.bin` |
| `17_hex_registro_67.txt` | 8.1 | Registro MFT 67 y su runlist |
| `18_patron_hex.txt` | 8.1 | Patrón legible en 0x06148000 |
| `19_istat_138.txt` | 8.2 | Metadatos de `comprimido.txt` |
| `20_hex_registro_138.txt` | 8.2 | Registro MFT 138 y su runlist comprimido |
| `21_fls_borrados.txt` | 8.3 | Archivos eliminados / huérfanos |
| `22_istat_16.txt` | 8.3 | Registro huérfano 16 |
| `23_vbr_volumen_solo.txt` | 8.4 | VBR del volumen extraído (V = 0) |
| `24_istat_prueba_nuevo.txt` | 9c | Registro 139 recién creado |
| `25_hex_registro_139.txt` | 9c | Registro 139 en hexadecimal (copia) |
| `26_contraste_139_antes_despues.txt` | 9c | Contraste original (no existe) vs copia (existe) |
| `27_fls_tras_borrado.txt` | 9d | Listado tras el borrado |
| `28_fls_d_tras_borrado.txt` | 9d | `fls -d` tras el borrado |
| `29_istat_139_borrado.txt` | 9d | Registro 139 ya liberado |
| `30_hex_registro_139_borrado.txt` | 9d | Registro 139 en hexadecimal tras borrar |
| `31_hashes_integridad.txt` | 9d | Hash de la imagen y de la copia |
| `32_residuo_nombre_copia.txt` | 10 | Búsqueda del nombre en UTF-16 dentro de la copia |
| `33_desglose_fl_original_copia.txt` | 10 | Conteo por tipo de entrada: original vs copia |
| `34_indx_raiz_nombres.txt` | 10 | Nombres contenidos en el bloque INDX del raíz |
| `35_istat_8_badclus.txt` | 10 | Registro 8 (`$BadClus`) y su stream sparse |
| `36_huerfanos_16_23.txt` | 10 | Huérfanos 16–23 listados por `fls` |
| `37_mft_tamano_antes_despues.txt` | 9c | Crecimiento de `$MFT`: 139 → 140 registros |
| `38_hash_volumen_extraido.txt` | 9a | Hash del volumen extraído (estado previo a la manipulación) |
| `39_bitmap_libre_antes_despues.txt` | 9c | Clústeres libres antes y después: 124 887 → 124 887 |

> Nota: `06_lab_ntfs_icat_original.txt` es un archivo vacío de 0 B que quedó de una redirección fallida; no se usa y no forma parte del conjunto de evidencias.

---

## Paso 0 — Preparación

- Paquetes instalados: `sleuthkit` 4.15.0, `ntfs-3g` 2026.9.28 (incluye `ntfsprogs`), `ghex` 50.4
- Hash base de la imagen: `b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f`
- Se trabajó siempre con `-o 2048` (offset de la partición) para las herramientas de TSK, y con copias del volumen en `trabajo/` cuando la herramienta no acepta `-o`.

---

## Paso 1 — Identificación del disco y la partición (MBR)

**Comando:**

```bash
{ echo '$ mmls ntfs_lab.img'; mmls ntfs_lab.img; echo; \
  echo '$ fdisk -l ntfs_lab.img'; fdisk -l ntfs_lab.img; } | tee mis_evidencias/01_mmls.txt
xxd -s 0x1BE -l 70 ntfs_lab.img | tee mis_evidencias/02_mbr_hex.txt
```

**Salida (resumen):** `mmls` distingue una tabla DOS con 2048 sectores no asignados al inicio, una única partición `NTFS / exFAT (0x07)` y 16 sectores no asignados al final. `fdisk` confirma 1 048 576 sectores de 512 B (511 MiB) y la partición `ntfs_lab.img1` en los sectores 2048–1048559.

**Interpretación:**

La imagen no *es* una partición: es un **disco** con una partición dentro. Por eso todas las herramientas de TSK necesitan `-o 2048` (2048 × 512 = 1 048 576 = **0x100000**). La entrada de partición en 0x1BE decodifica así:

| Offset | Campo | Bytes | Valor | Interpretación |
|---|---|---|---|---|
| 0x1BE | Estado | `00` | No arrancable | Sin sistema operativo instalado |
| 0x1BF–0x1C1 | CHS inicio | `20 21 00` | — | Sector 32, cilindro 0 (obsoleto) |
| 0x1C2 | Tipo | `07` | NTFS / exFAT | Sistema de archivos NTFS |
| 0x1C3–0x1C5 | CHS fin | `44 33 41` | — | Fin de la partición (obsoleto) |
| 0x1C6–0x1C9 | LBA inicio | `00 08 00 00` | 2048 | Primer sector de la partición |
| 0x1CA–0x1CD | Sectores | `F0 F7 0F 00` | 1 046 512 | Tamaño de la partición |
| 0x1FE–0x1FF | Firma | `55 AA` | Válida | MBR correcto |

2048 + 1 046 512 + 16 = 1 048 576 sectores: la suma cuadra exactamente con el tamaño del disco.

---

## Paso 2 — Análisis hexadecimal del sector de arranque (VBR)

**Comando:**

```bash
xxd -s 0x100000 -l 512 ntfs_lab.img | tee mis_evidencias/03_vbr_hex.txt
# copia de respaldo del VBR: último sector de la partición
xxd -s 0x1FFFDE00 -l 512 ntfs_lab.img | cmp - <(xxd -s 0x100000 -l 512 ntfs_lab.img) \
  && echo "LOS 512 BYTES SON IDÉNTICOS" | tee mis_evidencias/04_copia_vbr.txt
```

> **Corrección a la guía:** la copia de respaldo del VBR está en el **sector 1 048 559**, es decir en **0x1FFFDE00** (último sector de la partición: 2048 + 1 046 512 − 1). Los valores `0x1FFFDC00` (§5.6) y `0x1FFFE000` son incorrectos: en ellos el contenido es cero. Verificado: solo 0x1FFFDE00 contiene `eb 52 90 4e 54 46 53 20 20 20 20 00 02 08`.

**Tabla de campos:**

| Offset | Campo | Bytes | Hex | Interpretación |
|---|---|---|---|---|
| 0x03–0x0A | OEM ID | 8 | `4E 54 46 53 20 20 20 20` | `NTFS    ` |
| 0x0B–0x0C | Bytes por sector | 2 | `00 02` | 512 |
| 0x0D | Sectores por clúster | 1 | `08` | 8 |
| 0x28–0x2F | Total de sectores | 8 | `EF F7 0F 00 00 00 00 00` | 1 046 511 |
| 0x30–0x37 | LCN inicial de `$MFT` | 8 | `04 00 00 00 00 00 00 00` | 4 |
| 0x38–0x3F | LCN inicial de `$MFTMirr` | 8 | `7E FF 00 00 00 00 00 00` | 65 406 |
| 0x40 | Tamaño de registro MFT | 1 | `F6` | −10 → 2¹⁰ = 1024 B |
| 0x48–0x4F | Número de serie | 8 | `81 F3 1C 7A 28 2D 8E 0D` | 0x0D8E2D287A1CF381 |
| 0x1FE–0x1FF | Firma de arranque | 2 | `55 AA` | Sector válido |

**Interpretación (cálculo del clúster):**

```
C = B × S = 512 × 8 = 4096 bytes
Total sectores = 1 046 511 → 1 046 511 × 512 = 535 813 632 B ≈ 511 MiB
Total clústeres = 1 046 511 / 8 = 130 813,875 → 130 813 clústeres, rango 0–130 812
(130 813 × 4096 = 535 810 048 B = tamaño del stream $Bad de $BadClus)
```

El byte 0x40 vale `0xF6`; como es negativo, se interpreta como 2^|−10| = 1024 B por registro. La copia de respaldo del VBR (0x1FFFDE00) es **idéntica byte a byte** al VBR principal, como exige NTFS.

---

## Paso 3 — Parámetros del sistema de archivos (fsstat / ntfsinfo)

**Comando:**

```bash
fsstat -o 2048 ntfs_lab.img | tee mis_evidencias/05_fsstat.txt
ntfsinfo -m vol_ntfs_solo.img | tee mis_evidencias/06_ntfsinfo.txt
```

**Salida (resumen):**

| Dato | `fsstat` | `ntfsinfo` |
|---|---|---|
| Tipo / versión | NTFS, Windows XP | NTFS 3.1 |
| Sector / clúster | 512 B / 4096 B | 512 B / 4096 B |
| Tamaño de registro MFT | 1024 B | 1024 B |
| Tamaño de bloque de índice | 4096 B | 4096 B |
| Rango de registros | 0 – 139 | — |
| `$MFT` / `$MFTMirr` | LCN 4 / LCN 65 406 | LCN 4 / LCN 65 406 (4 clústeres) |
| Directorio raíz | registro 5 | — |
| Clústeres totales | 0 – 130 812 | 130 813 |
| Clústeres libres | — | 124 887 (95,5 %) |
| Nombre de volumen | `LAB_NTFS` | `LAB_NTFS` |

**Contraste entre herramientas:**

Ambas coinciden en todos los parámetros estructurales, así que los datos del VBR son correctos. `fsstat` añade el límite superior del rango de registros MFT (0–139): el `$MFT` mide 142 336 B = **139 registros** (0–138), y el 139 es el primer número que aún no existe (por eso `istat` lo rechaza en el Paso 9). `ntfsinfo` aporta el detalle de la zona MFT (0–16 355), el tamaño real de `$Bitmap` (16 352 B) y el conteo de clústeres libres. La diferencia de 1 clúster en el total se debe a que `fsstat` informa el **último índice** (130 812) y `ntfsinfo` el **conteo** (130 813).

---

## Paso 4 — Cálculo de la posición de la MFT

**Fórmula y sustitución:**

```
C = B × S = 512 × 8 = 4096
OffsetMFT = V + (LCN_MFT × C) = 1 048 576 + (4 × 4096) = 1 064 960 = 0x104000
```

**Verificación (firma FILE):**

```bash
xxd -s 0x104000 -l 64 ntfs_lab.img | tee mis_evidencias/07_mft_offset_hex.txt
```

```
00104000: 4649 4c45 3000 0300 0000 0000 0000 0000  FILE0...........
00104010: 0100 0100 3800 0100 9801 0000 0004 0000  ....8...........
```

La firma `FILE` (`46 49 4C 45`) aparece exactamente en el offset calculado: el registro 0 (`$MFT`) es el primero de la tabla. El offset de cualquier registro N es:

```
Offset(N) = 0x104000 + N × 1024        (imagen con MBR, V = 0x100000)
Offset(N) = 0x004000 + N × 1024        (volumen extraído, V = 0)
```

---

## Paso 5 — Directorio raíz: registro MFT nº 5

**Comando:**

```bash
fls -o 2048 ntfs_lab.img | tee mis_evidencias/08_fls_raiz.txt
fls -o 2048 -r ntfs_lab.img | tee mis_evidencias/09_fls_recursivo.txt
istat -o 2048 ntfs_lab.img 5 | tee mis_evidencias/10_root_istat.txt
xxd -s 0x105400 -l 1024 ntfs_lab.img | tee mis_evidencias/11_root_hex.txt
```

**Cabecera del registro** (0x104000 + 5 × 1024 = **0x105400**): firma `FILE`, secuencia 5, en uso + directorio (`0x0003`), 1 enlace, primer atributo en 0x38, registro base 0, número de registro 5.

**Atributos encontrados:**

| Offset | Tipo | Nombre | Longitud | Residente |
|---|---|---|---|---|
| 0x105438 | 0x10 `$STANDARD_INFORMATION` | — | 72 | Sí (48 B) |
| 0x105480 | 0x30 `$FILE_NAME` | `.` | 96 | Sí (68 B) |
| 0x1054E0 | 0x50 `$SECURITY_DESCRIPTOR` | — | 72 | No (4140 B, LCN 16 355–16 356) |
| 0x105528 | 0x90 `$INDEX_ROOT` | `$I30` | 88 | Sí (56 B) |
| 0x105580 | 0xA0 `$INDEX_ALLOCATION` | `$I30` | 80 | No (4096 B, 1 clúster) |
| 0x1055D0 | 0xB0 `$BITMAP` | `$I30` | 40 | Sí (8 B) |

**Interpretación:**

El registro 5 es el directorio raíz: sus flags valen 0x0003 (en uso + directorio) y contiene seis atributos. El contenido del directorio no está en el registro sino en un árbol B+: el `$INDEX_ROOT` (residente, nombre `$I30` en UTF-16) solo guarda la cabecera con la bandera de «índice grande», y el `$INDEX_ALLOCATION` (no residente) apunta mediante el data run `21 01 e5 3f` al clúster 16 357, es decir a:

```
0x100000 + 16 357 × 4096 = 68 046 848 = 0x040E5000
```

Allí aparece la firma `INDX`. `fls` recorre el índice y devuelve los 22 nombres de la raíz con su número de registro MFT (`08_fls_raiz.txt`), más la entrada virtual `$OrphanFiles` que TSK añade al final. Los cinco archivos de sistema de primer nivel (`$MFT`, `$MFTMirr`, `$LogFile`, `$Volume`, `$AttrDef`) y los cuatro directorios (`$Extend`, `docs`, `muchos`, `comprimidos`) se listan con su registro y su tipo de atributo.

---

## Paso 6 — Localización del archivo de prueba y sus datos

| Dato | Valor |
|---|---|
| Nombre | `LAB_NTFS.txt` |
| Registro MFT | 64 (0x40) |
| Offset del registro (`OffsetMFT + N×R`) | 1 064 960 + 65 536 = **1 130 496 = 0x114000** |
| Tamaño | 114 B |
| Fecha de modificación | 2026-10-21 17:30:00 (−05) |
| ¿Residente o no? (byte en 0x114168) | **Residente** (`00`) |
| Offset del contenido | **0x114178** (valor del atributo en 0x114160 + 0x18) |
| SHA-256 original | `ffef8fb0bb1ef274fe4d94d462e99a02275a7ac7366f014fad7a825cdc5fbe6d` |
| SHA-256 extraído con `icat` | `ffef8fb0bb1ef274fe4d94d462e99a02275a7ac7366f014fad7a825cdc5fbe6d` |
| **¿Coinciden?** | **Sí** — el contenido de la MFT es idéntico byte a byte al archivo original |

Comandos:

```bash
istat -o 2048 ntfs_lab.img 64 | tee mis_evidencias/12_istat_64.txt
xxd -s 0x114000 -l 1024 ntfs_lab.img | tee mis_evidencias/13_hex_registro_64.txt
icat -o 2048 ntfs_lab.img 64 | sha256sum
sha256sum archivos_prueba/LAB_NTFS.txt
```

Recorrido de atributos del registro 64:

| Offset absoluto | Tipo | Nombre | Longitud | Residente | Valor |
|---|---|---|---|---|---|
| 0x114038 | 0x10 `$STANDARD_INFORMATION` | — | 72 | Sí | 0x114050 (48 B) |
| 0x114080 | 0x30 `$FILE_NAME` | `LAB_NTFS.txt` | 120 | Sí | 0x114098 (90 B) |
| 0x1140F8 | 0x50 `$SECURITY_DESCRIPTOR` | — | 104 | Sí | 0x114110 (80 B) |
| **0x114160** | **0x80 `$DATA`** | — | **144** | **Sí** | **0x114178 (114 B)** |
| 0x1141F0 | — | Fin de atributos | — | — | `FF FF FF FF` |

El nombre `LAB_NTFS.txt` está en UTF-16LE a partir de 0x1140DC; en 0x1141D0 aparece `c3 a1` (la `á` de «análisis» en UTF-8). **No hay ningún clúster de datos involucrado:** el contenido vive dentro de la propia MFT.

---

## Paso 7 — Archivo no residente: decodificación de data runs

- Registro: `aleatorio_12MB.bin` → nº **66** (hex **0x42**), registro en 0x104000 + 66×1024 = **0x114800**
- Runlist: `22 00 0c 48 50` → desglose byte a byte:

| Byte(s) | Significado |
|---|---|
| `22` | Cabecera: nibble bajo 2 = longitud en 2 bytes; nibble alto 2 = offset en 2 bytes |
| `00 0c` | Longitud = **3 072 clústeres** (3 072 × 4096 = 12 582 912 B) |
| `48 50` | Offset = 0x5048 = **20 552** (delta desde LCN 0, por ser el primer run) |
| `00` | Fin de la lista (*data run terminator*) |

```
Offset = V + (LCN × C) = 1 048 576 + (20 552 × 4096) = 85 229 568 = 0x05148000
```

**Verificación (hash / patrón legible):**

```bash
istat -o 2048 ntfs_lab.img 66 | tee mis_evidencias/14_istat_66.txt
xxd -s 0x05148000 -l 64 ntfs_lab.img | tee mis_evidencias/15_aleatorio_hex.txt
icat -o 2048 ntfs_lab.img 66 | sha256sum
sha256sum archivos_prueba/aleatorio_12MB.bin
# ambos: e1825d66ff65c0509fe70da379260938473ee0b0ce5e47adf2d9d97628c68d3a
```

El contenido es binario pseudoaleatorio, no legible en hexadecimal; por eso la verificación se hace por hash. El runlist confirma que los 12 MB son **un solo run contiguo** desde el LCN 20 552 y que el atributo `$DATA` tiene el byte de no residente en 1.

---

## Paso 8 — Casos especiales

### 8.1 Archivo con patrón legible (`datos_patron_8MB.bin`)

Registro **67**, `$DATA` no residente de 8 388 608 B, runlist `22 00 08 48 60`: 2 048 clústeres desde el LCN **24 648**.

```
Offset = 1 048 576 + (24 648 × 4096) = 102 006 784 = 0x06148000
```

```
06148000: 4e54 4653 2d4c 4142 2d43 4c55 5354 4552  NTFS-LAB-CLUSTER
06148010: 2d50 4154 5445 524e 2d30 3132 3334 3536  -PATTERN-0123456
```

La cadena `NTFS-LAB-CLUSTER-PATTERN-0123456789ABCDEF` se repite en la posición calculada: la evidencia es directa y demuestra que el LCN del runlist es la ubicación física del contenido. Evidencias: `16_istat_67.txt`, `17_hex_registro_67.txt`, `18_patron_hex.txt`.

### 8.2 Archivo comprimido (`comprimido.txt`)

Registro **138** (padre 137, directorio `comprimidos`), 100 000 B lógicos pero solo **12 288 B** asignados. Flags `Archive, Compressed`, unidad de compresión 4 → 2⁴ = 16 clústeres = 64 KiB.

Runlist real: `31 02 48 90 00 01 0e 11 01 02 01 0f`

| Run | VCN | LCN | Longitud | Significado |
|---|---|---|---|---|
| 1 | 0–1 | 36 936 | 2 | Datos comprimidos reales |
| 2 | 2–15 | 36 936 | 14 | Relleno de la unidad de compresión (mismo LCN) |
| 3 | 16 | 36 938 | 1 | Datos del segundo bloque |
| 4 | 17–31 | 36 938 | 15 | Relleno del segundo bloque |

La repetición del LCN es la firma de la compresión NTFS: dentro de cada unidad solo se guardan los clústeres necesarios y el resto no se vuelve a asignar. El contenido exige descompresión LZNT1, que TSK resuelve:

```bash
icat -o 2048 ntfs_lab.img 138 | sha256sum
sha256sum archivos_prueba/comprimido.txt
# ambos: 5af063b5fef8a84848e9b7cbbb87fb58ab24c5240cb784bcde724fe90feda8ce
```

Evidencias: `19_istat_138.txt`, `20_hex_registro_138.txt`.

### 8.3 Archivos eliminados / huérfanos (`fls -d`)

```bash
fls -o 2048 -d -r ntfs_lab.img | tee mis_evidencias/21_fls_borrados.txt
istat -o 2048 ntfs_lab.img 16 | tee mis_evidencias/22_istat_16.txt
```

Aparecen ocho registros huérfanos (16 a 23) bajo la entrada virtual `$OrphanFiles`. El registro 16 confirma el patrón: `Not Allocated File`, `Links: 0`, secuencia igual al número de registro y **un solo atributo** (`$STANDARD_INFORMATION` de 48 B), sin `$FILE_NAME`. Son registros preformateados que nunca llegaron a usarse, no archivos borrados por un usuario.

### 8.4 Volumen sin MBR (`vol_ntfs_solo.img`, V = 0)

```bash
# Extrae el volumen (sin MBR) si no existe; vol_ntfs_solo.img ya está en la raíz.
dd if=ntfs_lab.img of=vol_ntfs_solo.img bs=512 skip=2048 count=1046512 status=none
xxd -s 0 -l 512 vol_ntfs_solo.img | tee mis_evidencias/23_vbr_volumen_solo.txt
fsstat vol_ntfs_solo.img
ntfsinfo -m vol_ntfs_solo.img | tee mis_evidencias/06_ntfsinfo.txt
```

El VBR queda ahora en el offset **0** y la MFT en `0 + 4 × 4096 = 0x4000`. La firma `FILE` del registro 0 se comprueba en 0x4000, y el registro N está en `0x4000 + N × 1024`. `fsstat` sin `-o` devuelve los mismos parámetros que con `-o 2048`, lo que demuestra que la partición empieza exactamente en 0x100000. Esta copia es la que se usa con `ntfsinfo`, porque esa herramienta no acepta `-o`.

---

## Paso 9 — Manipulación sobre copia (experimento controlado)

- Copia usada: `trabajo/copia_volumen.img` — **copia del volumen** (sin MBR), equivalente a `volumen_solo.img`, de modo que en ella V = 0

```bash
dd if=ntfs_lab.img of=trabajo/copia_volumen.img bs=512 skip=2048 count=1046512 status=none
sudo mkdir -p /mnt/ntfs_lab
sudo mount -t ntfs-3g -o loop trabajo/copia_volumen.img /mnt/ntfs_lab
echo "Julian 10/2026 - prueba de escritura controlada" | sudo tee /mnt/ntfs_lab/prueba_julian.txt
sudo umount /mnt/ntfs_lab
```

- Hash de la copia antes / después:

| Momento | SHA-256 |
|---|---|
| Antes (volumen recién extraído) | `38f6767a9a9b92cc80443ed594d2f93d4d78a1622e4ea27101bd372f2d7771fc` |
| Después (tras crear y borrar) | `07c026ee6fa2b4536345d15514f1a35cc72885f2ae164dbb35bfa057172b9c30` |
| Imagen original (sin tocar) | `b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f` |

El hash del volumen extraído (`38f6767a…`) coincide con el de `vol_ntfs_solo.img`, que nunca se manipuló: confirma que el punto de partida del experimento era una copia fiel del volumen. La imagen original conserva su hash.

**Qué cambió al crear el archivo:**

| Elemento | Antes | Después |
|---|---|---|
| Registro MFT 139 | inexistente para TSK («inode number is too large») | asignado, secuencia 1, `Links: 1`, flags `0x01` |
| `$FILE_NAME` | — | `prueba_julian.txt`, padre 5 (`$Root`) |
| `$DATA` | — | **residente, 48 B** en 0x26D80 |
| Texto almacenado | — | `Julian 10/2026 - prueba de escritura controlada` (+ `0A`) |
| `$Bitmap` (clústeres libres) | 124 887 | **124 887** (sin cambio) |

El contenido es residente, así que **no se asignó ni un solo clúster de datos** y `$Bitmap` no cambia (comprobado con `ntfsinfo` antes y después: `39_bitmap_libre_antes_despues.txt`). Pero hay un matiz que conviene documentar: el `$MFT` **sí creció un registro**. En la imagen original su `$DATA` mide 142 336 B (139 registros, 0–138) y tras la creación mide 143 360 B (140 registros, 0–139):

```
Original:  142 336 B / 1024 = 139 registros
Copia:     143 360 B / 1024 = 140 registros
Diferencia:   1 024 B = 1 registro
```

Ese kilobyte adicional cabía en el **último clúster ya asignado** a `$MFT` (el volumen asignó 35 clústeres = 143 360 B desde el formateo), por lo que NTFS solo tuvo que extender el tamaño válido del stream, sin pedir un clúster nuevo. Evidencia: `37_mft_tamano_antes_despues.txt`.

**Qué cambió al borrar el archivo:**

```bash
sudo mount -t ntfs-3g -o loop trabajo/copia_volumen.img /mnt/ntfs_lab
sudo rm /mnt/ntfs_lab/prueba_julian.txt
sudo umount /mnt/ntfs_lab
```

| Campo | Antes del borrado | Después del borrado |
|---|---|---|
| Sequence (0x26C10) | 1 | **2** |
| Links (0x26C12) | 1 | **0** |
| Flags (0x26C16) | `01 00` (en uso) | `00 00` (libre) |
| USN (0x26C30, 0x26DFE, 0x26FFE) | `06 00` | **`07 00`** |
| `$FILE_NAME` | `prueba_julian.txt` | **sigue igual** (no se borra) |
| `$DATA` residente | 48 B | **sigue igual** en 0x26D80 |

Conclusión del experimento: borrar en NTFS es **marcar** el registro como libre (bit de uso, enlaces y número de secuencia), no sobrescribir. El nombre y el contenido siguen íntegros en la MFT hasta que el registro se reutilice. Evidencias: `24`–`31`, `37`, `38`, `39`.

---

## Paso 10 — Hallazgos forenses propios

### 10.1 Residuo de metadatos en el bloque `INDX` del directorio raíz

Se extrajeron los nombres del bloque INDX del raíz (LCN 16 357) tanto de la imagen original como de la copia:

```bash
dd if=trabajo/copia_volumen.img bs=4096 skip=16357 count=1 status=none | strings -el \
  | tee mis_evidencias/34_indx_raiz_nombres.txt
# la misma lectura sobre el original: 16357 + 256 (los 0x100000 de la partición / 4096)
dd if=ntfs_lab.img bs=4096 skip=16613 count=1 status=none | strings -el
```

Resultado **idéntico en original y copia** (el INDX no lo modificó nuestro experimento):

- `umbral_residente.txt` aparece **dos veces**. La raíz tiene una sola entrada con ese nombre (`fls` la lista una vez), así que la segunda aparición es un **residuo de una operación anterior del índice**: el espacio de una entrada antigua quedó en el bloque y no se reutilizó. Es una inconsistencia **preexistente de la imagen**, no un artefacto del laboratorio: aparece igual en `ntfs_lab.img`.
- `prueba_julian.txt` **no aparece**.

Y en cambio, buscando el nombre en UTF-16LE por toda la copia:

```bash
grep -aboP 'p\x00r\x00u\x00e\x00b\x00a\x00_\x00j\x00u\x00l\x00i\x00a\x00n' \
  trabajo/copia_volumen.img | tee mis_evidencias/32_residuo_nombre_copia.txt
# 158938:prueba_julian    (0x26CDA, dentro del registro MFT 139)
```

**Una sola aparición, y está en la MFT, no en el índice.** Conclusión forense: tras el borrado, NTFS elimina la entrada del índice (las entradas se desplazan y el nombre se sobrescribe), pero **no limpia el registro MFT**; el `$FILE_NAME` sobrevive en el registro 139. Por eso `fls` sigue recuperando el nombre aunque el índice ya no lo tenga: TSK, en modo recursivo, recorre la MFT y muestra los registros no asignados con nombre bajo `$OrphanFiles` o como entrada suelta. Se comprobó el desglose por tipo de entrada (`33_desglose_fl_original_copia.txt`): la única diferencia entre original y copia es **una línea `-/r`**, la del archivo borrado.

Dos lecciones: (a) el índice de directorio es una fuente **volátil** del nombre; la fuente persistente es el registro MFT; (b) una entrada duplicada en el INDX es un indicio de actividad previa en el directorio que merece revisarse.

### 10.2 Registros MFT sin bit de uso (16–23)

Los registros 16 a 23 se listan como huérfanos (`$OrphanFiles/OrphanFile-16` … `-23`) y comparten un patrón inequívoco:

- `Not Allocated File`, `Links: 0`, sin atributo `$FILE_NAME` ni `$DATA`.
- Solo `$STANDARD_INFORMATION` de 48 B.
- Número de secuencia igual al número de registro (16→16, …, 23→23).
- Marcas de tiempo **idénticas a las de creación del volumen**: `2026-10-21 19:19:44.759524`.

Interpretación: es coherente con el formateo mediante `mkntfs`, que al crear el volumen reserva un bloque de registros y les asigna la hora de formateo; como nunca se usaron, quedaron sin nombre ni datos y con `Links: 0`. **No son archivos borrados por un usuario** (un borrado real conservaría `$FILE_NAME`, como se demostró en el Paso 9). Su valor forense es el contrario: sirven para *descartar* actividad y demuestran que la zona inicial de la MFT está reservada por el formateador. Evidencias: `21`, `22`, `36`.

### 10.3 Stream *sparse* de `$BadClus`

```bash
istat -o 2048 ntfs_lab.img 8 | tee mis_evidencias/35_istat_8_badclus.txt
```

```
Entry: 8        Sequence: 8        Allocated File        Links: 1
Flags: Hidden, System
Type: $DATA (128-2)   Name: N/A    Resident       size: 0
Type: $DATA (128-1)   Name: $Bad  Non-Resident   size: 535 810 048   init_size: 0
```

El stream `$Bad` mide **535 810 048 B = 130 813 clústeres × 4096 B**, es decir exactamente el tamaño del volumen, pero su `init_size` es **0** y no tiene ningún run asignado: es un archivo **disparsable (*sparse*)**. NTFS lo define así a propósito: todos los clústeres del volumen están "virtualmente" dentro de `$Bad` y solo se asignarían de verdad los que se detectaran defectuosos. Al no haber runs, el volumen **no tiene clústeres malos** y el archivo no ocupa espacio real. Es un buen ejemplo de que en NTFS el tamaño lógico de un stream no dice nada sobre el espacio ocupado: hay que leer el runlist.

---

## Paso 11 — Capturas

| Captura | Muestra |
|---|---|
| `capturas/01-Verificación_imagen_trabajo.png` | Hash inicial y copia de trabajo |
| `capturas/02-Tabla_particiones.png` | `mmls` / `fdisk` con la partición en el sector 2048 |
| `capturas/03-Parametros_sistema_archivos.png` | `fsstat` con clúster de 4096 B y `$MFT` en LCN 4 |
| `capturas/04-Sector_arranque_hexadecorial.png` | VBR en 0x100000 con OEM ID y firma 55 AA |
| `capturas/05-Firma_FILE_MFT.png` | Firma `FILE` en 0x104000 |
| `capturas/06-Directorio_raiz.png` | `fls` recursivo del volumen |
| `capturas/07-Registro_directorio_raiz.png` | `istat` del registro 5 (`$Root`) con `$INDEX_ROOT` e `$INDEX_ALLOCATION` |
| `capturas/08-Directorio_raiz_hexadecimal.png` | Hex del registro 5 en 0x105400, tipos `0x90`/`0xA0` e `INDX` |
| `capturas/09-Registro_MFT_64.png` | `istat` del registro 64 con `$FILE_NAME` y `$DATA` residente |
| `capturas/10-Registro_64_Hexadecimal.png` | Hex del registro 64 en 0x114000; fin de atributos `ffffffff` en 0x1141F0 |
| `capturas/11-Contenido_archivo.png` | Texto de `LAB_NTFS.txt` extraído con `icat` |
| `capturas/12-Umbral_residencia.png` | `umbral_residente.txt` ya no residente |
| `capturas/13-No_residente.png` | `aleatorio_12MB.bin` y su runlist |
| `capturas/14-Archivo_grande.png` | `datos_patron_8MB.bin` y su runlist |
| `capturas/15-Hash.png` | Coincidencia de hashes con `icat` |
| `capturas/16-Archivo_patron.png` | Patrón `NTFS-LAB-CLUSTER` en 0x06148000 |
| `capturas/17-Hash_archivo_patron.png` | Hash del archivo de patrón |
| `capturas/18-Hexadecimal_comprimido_txt.png` | Hex del `$DATA` comprimido del registro 138 |
| `capturas/19-Contenido_comprimido_txt.png` | Contenido descomprimido de `comprimido.txt` |

---

## Cierre — Integridad final

```bash
sha256sum ntfs_lab.img
```

```
b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f  ntfs_lab.img
```

El hash final es **idéntico** al inicial: la imagen original no fue modificada en ningún momento. Todas las escrituras del laboratorio se hicieron sobre las copias de `trabajo/`, cuyo hash sí cambió (`07c026ee6fa2b4536345d15514f1a35cc72885f2ae164dbb35bfa057172b9c30`), y ese cambio es la prueba de que el experimento del Paso 9 se ejecutó realmente sobre una copia y no sobre la evidencia.
