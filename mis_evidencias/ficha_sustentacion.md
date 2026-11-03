---
title: "Ficha de sustentación · Laboratorio 1 NTFS"
subtitle: "Alejandro Arbelaez Hoyos y Julián David Guarnizo Castrillón · Arquitectura del Computador · UCO · 28 de octubre de 2026"
---

# 1 · La cadena, en una línea

```
MBR ....... sector 0  →  partición empieza en el sector 2048
V ......... 2048 × 512 = 0x100000        (imagen completa; TSK con -o 2048)
VBR ....... 512 B/sector · 8 sect/clúster = 4096 B · registro = 1024 B · $MFT en LCN 4
MFT ....... 0x100000 + 4×4096 = 0x104000 (comprobar firma "FILE")
Registro n  0x104000 + n×1024
Atributos . 0x10 fechas · 0x30 nombre · 0x50 permisos · 0x80 dato
Datos ..... residente (dentro del registro) ó runlist → V + LCN×4096
```

**Trampa:** imagen completa → `V = 0x100000` (TSK con `-o 2048`); volumen extraído → `V = 0`, sin `-o`, MFT en `0x4000`, registro 139 en `0x26C00`.

# 2 · Mapa de registros (`ntfs_lab.img`)

| Reg | Objeto | Offset | Dónde están sus datos |
|:---:|:-----------------------|:--------|:---------------------------------------------------------------|
| 0 | `$MFT` | `0x104000` | no res.: 35 clústeres desde LCN 4 · 139 registros |
| 1 | `$MFTMirr` | `0x104400` | LCN 65 406 → `0x1007E000` |
| 2 | `$LogFile` | `0x104800` | journaling |
| 3 | `$Volume` | `0x104C00` | nombre `LAB_NTFS` |
| 4 | `$AttrDef` | `0x105000` | tabla de atributos |
| **5** | **`$Root`** (raíz) | **`0x105400`** | índice → LCN 16 357 = `0x040E5000` |
| 6 | `$Bitmap` | `0x105800` | 124 887 clústeres libres |
| 7 | `$Boot` | `0x105C00` | 8 192 B desde LCN 0 (el VBR) |
| 8 | `$BadClus` | `0x106000` | `$Bad` **sparse**: 535 810 048 B, 0 clústeres reales |
| 9 | `$Secure` | `0x106400` | `$SDS` / `$SDH` / `$SII` |
| 10 | `$UpCase` | `0x106800` | tabla Unicode |
| 11 | `$Extend` | `0x106C00` | 24 `$Quota` · 25 `$ObjId` · 26 `$Reparse` |
| 12–15 | — | `0x107000` | 4 registros **en uso, sin nombre** → `fls` no los muestra |
| 16–23 | — | `0x108000` | 8 **libres, sin nombre** → `$OrphanFiles` |
| 27–63 | — | `0x10AC00` | 37 libres |
| **64** | `LAB_NTFS.txt` | **`0x114000`** | **residente**: 114 B en `0x114178`, 0 clústeres |
| 65 | `umbral_residente.txt` | `0x114400` | 2 000 B · LCN 16 460 → `0x0414C000` |
| 66 | `aleatorio_12MB.bin` | `0x114800` | 12 582 912 B · LCN 20 552 → `0x05148000` |
| 67 | `datos_patron_8MB.bin` | `0x114C00` | 8 388 608 B · LCN 24 648 → `0x06148000` |
| 68 | `docs/` | `0x115000` | 69–73 (5 archivos) · 74 `teoria/` · 75 archivo |
| 76 | `muchos/` | `0x117000` | 77–136: 60 fichas · índice de 3 bloques INDX |
| 77–136 | `ficha_01`…`ficha_60` | `0x117400` | 60 fichas **residentes**, una por registro |
| 137 | `comprimidos/` | `0x126400` | contiene el 138 |
| 138 | `comprimido.txt` | `0x126800` | 100 000 B → 12 288 B · LCN 36 936 → `0x09148000` |
| 139 | *(no existe)* | `0x126C00` | solo en la copia: `prueba_julian.txt`, borrado |

*Comprobación:* en cada offset deben leerse los bytes `46 49 4C 45` (`FILE`). Conteos: 89 archivos, 5 directorios + raíz, 8 huérfanos, 103 entradas.

# 3 · Números de oro

| Dato | Valor | Dato | Valor |
|:---------------------|:-------------------------|:----------------------|:-----------------------------|
| Inicio partición / V | sector 2048 · `0x100000` | Clúster / registro | 4 096 B / 1 024 B |
| `$MFT` | `0x104000` | Raíz (reg. 5) | `0x105400` |
| INDX raíz | `0x040E5000` (LCN 16 357) | `$MFTMirr` | LCN 65 406 · `0x1007E000` |
| VBR de respaldo | sector 1 048 559 · **`0x1FFFDE00`** | Clústeres | 130 813 · libres 124 887 (95,5 %) |
| SHA-256 imagen | `b4bdbef3…346f` = al inicio | SHA-256 `LAB_NTFS.txt` | `ffef8fb0…fbe6d` |

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# 4 · Runlists clave

| Reg | Runlist | Lectura | Resultado |
|:---:|:----------------|:--------------------------------------|:----------------------------|
| 64 | — | residente, valor en `0x114178` | 114 B, 0 clústeres |
| 65 | `21 01 4C 40` | 1 clúster desde 0x404C | LCN 16 460 → `0x0414C000` |
| 66 | `22 00 0C 48 50` | 3 072 clústeres desde 0x5048 | LCN 20 552 → `0x05148000` |
| 67 | `22 00 08 48 60` | 2 048 clústeres desde 0x6048 | LCN 24 648 → `0x06148000` |
| 138 | `31 02 48 90 …` | 2 + relleno, 1 + relleno | LCN 36 936 / 36 938 → `0x09148000` |

**Cómo se lee:** `22` = longitud en 2 bytes, desplazamiento en 2 bytes · `00 0C` = 3 072 · `48 50` = 0x5048 (delta con signo desde el run anterior) · `00` = fin.

# 5 · Residente o no: lo decide **un byte**

El byte de *no residente* del atributo `$DATA` (offset +0x08 del atributo): `00` = el valor está dentro del registro · `01` = hay runlist. **No lo decide el tamaño.**

# 6 · Experimento sobre copia (V = 0)

| Campo | Crear `prueba_julian.txt` | Borrar |
|:-------------------------|:------------------------------------|:----------------------------------|
| Registro | aparece el **139** (antes: «too large») | sigue ahí, marcado libre |
| Sequence | 1 | **1 → 2** |
| Links | 1 | **1 → 0** |
| Flags | `0x0001` | **`0x0000`** |
| USN (3 sitios) | `06` | **`07`** |
| `$FILE_NAME` y `$DATA` (48 B) | presentes | **intactos** |
| `$MFT` / `$Bitmap` | 142 336 → **143 360 B** | 124 887 libres (**sin cambio**) |

**Frase:** *borrar en NTFS es marcar, no sobrescribir*. La MFT creció un registro sin pedir clúster nuevo (cabía en el último clúster ya asignado).

# 7 · Tres hallazgos forenses

1. **INDX con residuo:** `umbral_residente.txt` aparece **dos veces** en el bloque del raíz, igual en la imagen original → residuo previo, no del experimento. El nombre borrado **no** está en el índice, pero sí en el registro 139 (`0x26CDA`).
2. **Huérfanos 16–23:** `Not Allocated`, links 0, sin `$FILE_NAME`, secuencia = nº de registro, fechas de formateo → **no son borrados de usuario**. Y 12–15 están en uso pero sin nombre: invisibles para `fls`.
3. **`$BadClus`:** 535 810 048 B (= 130 813 × 4096, todo el volumen) con un único run **disperso** → tamaño lógico ≠ espacio ocupado; 0 clústeres malos.

# 8 · Preguntas rápidas

| Pregunta | Respuesta en una línea |
|:---------------------------|:-------------------------------------------------------------------------------|
| ¿MBR = VBR? | No: el MBR describe el disco; el VBR, el volumen (clúster, registro, MFT). |
| ¿Qué datos ubican la MFT? | `0x0B`=512, `0x0D`=8, `0x30`=4 → `0x100000 + 4×4096 = 0x104000`. |
| ¿La raíz es zona fija? | No: es el registro 5 (`$Root`) con `$INDEX_ROOT` + `$INDEX_ALLOCATION`. |
| ¿Residente o no residente? | Un byte: `00` dentro del registro; `01` con runlist. |
| ¿Y si no caben los atributos? | `$ATTRIBUTE_LIST` + registros de extensión. Aquí no hizo falta: 138 usa 448 B. |
| ¿Nombre = datos contiguos? | No: el nombre va en `$FILE_NAME`/índice; los datos en `$DATA`, con N runs. |
| ¿Límites del análisis manual? | Fragmentación, LZNT1, EFS y `$ATTRIBUTE_LIST`: ahí hacen falta `istat`/`icat`. |
| ¿Evidencia confiable? | SHA-256 inicial = final; escrituras solo en la copia; `icat` = archivo original. |

# 9 · Comandos que cito (y qué demuestra cada uno)

| Comando | Qué demuestra |
|:-----------------------------------|:-----------------------------------------------------------------------------|
| `mmls ntfs_lab.img` | tabla DOS: partición NTFS en el sector 2048 |
| `fsstat -o 2048 ntfs_lab.img` | clúster 4 096 · registro 1 024 · MFT en LCN 4 · 130 813 clústeres |
| `fls -o 2048 -r ntfs_lab.img` | 22 nombres en la raíz; 16–23 no aparecen |
| `istat -o 2048 ntfs_lab.img 64` | `$DATA` **residente** de 114 B, 0 clústeres |
| `istat -o 2048 ntfs_lab.img 138` | runlist comprimida: 3 clústeres para 100 000 B |
| `icat -o 2048 ntfs_lab.img 66` | los datos extraídos coinciden (`cmp`) con el original |
| `dd bs=512 skip=2048` | copia solo-volumen: V = 0, MFT en `0x4000` |
| `sha256sum ntfs_lab.img` | hash inicial = final → imagen intacta |

*Evidencias:* `mis_evidencias/01…39`, capturas 16–19 y `bitacora.md`.
