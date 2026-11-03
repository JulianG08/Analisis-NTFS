# Laboratorio 1 — NTFS: materiales y guía

Todo el laboratorio se realizó sobre una **imagen de disco de 512 MB** creada para la práctica
(no sobre la carpeta compartida `/media/sf_D_DRIVE`, que es un recurso `vboxsf` del host y no un
dispositivo de bloque).

## Archivos

| Ruta | Qué es |
|---|---|
| `Guia_Lab01_NTFS.md` | **Entregable principal**: guía completa con teoría, procedimientos, tablas de valores reales, evidencias y respuestas a las preguntas de análisis |
| `ntfs_lab.img` | Imagen de disco de 512 MB: MBR + partición NTFS (`LAB_NTFS`) con todos los archivos de prueba |
| `vol_ntfs_solo.img` | Solo el volumen NTFS (sin MBR), para practicar el caso `V = 0` |
| `archivos_prueba/` | Fuentes reproducibles de los archivos de prueba y `generar_archivos.py` |
| `evidencias/` | Volcados hexadecimales, salidas de TSK y cálculos generados con `analizar.py` |

## Estructura del volumen

| Parámetro | Valor |
|---|---|
| Tamaño de la imagen | 536 870 912 B (512 MiB) |
| Partición | inicio sector 2048, tipo 0x07, 1 046 512 sectores |
| Clúster | 4 096 B (8 sectores de 512 B) |
| Registro MFT | 1 024 B |
| LCN de `$MFT` | 4 → offset `0x104000` |
| Raíz | registro MFT 5 → offset `0x105400` |
| Archivo de prueba | `LAB_NTFS.txt`, registro MFT 64 → offset `0x114000`, datos residentes en `0x114178` |
| Serial del volumen | `0x0D8E2D287A1CF381` |

## Contenido de prueba

| Archivo | Rol |
|---|---|
| `LAB_NTFS.txt` (114 B) | Datos residentes (dentro de la MFT) |
| `umbral_residente.txt` (2 000 B) | No residente, un solo run |
| `aleatorio_12MB.bin` (12 MiB) | No residente, verificación por hash |
| `datos_patron_8MB.bin` (8 MiB) | No residente con patrón ASCII visible en la posición calculada |
| `comprimidos/comprimido.txt` (100 000 B → 12 288 B) | Compresión NTFS (unidades de 16 clústeres) |
| `docs/`, `docs/teoria/` | Carpetas con archivos pequeños |
| `muchos/` (60 archivos) | Fuerza `$INDEX_ALLOCATION` con 3 registros `INDX` |

## Uso rápido

```bash
# Ver la tabla de particiones
mmls ntfs_lab.img

# Parámetros del sistema de archivos
fsstat -o 2048 ntfs_lab.img

# Sector de arranque
xxd -s $((2048*512)) -l 512 ntfs_lab.img

# Registro de un archivo y su contenido
istat -o 2048 ntfs_lab.img 64
icat  -o 2048 ntfs_lab.img 64

# Regenerar toda la evidencia (solo lectura)
python3 evidencias/analizar.py

# Recorrer un registro MFT byte a byte
python3 evidencias/parse_mft.py 64
```

## Integridad

```bash
sha256sum ntfs_lab.img
# b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f
```

Si este hash cambia, la imagen fue modificada y las evidencias dejan de corresponder.

## Nota sobre el equipo y EFS

- El volumen se creó con `mkntfs` y se pobló con `ntfs-3g`; por eso el asignador colocó cada archivo
  en un bloque contiguo y **no se logró un ejemplo fragmentado** (se documenta como limitación en §9.6
  de la guía).
- La compresión NTFS sí se generó y se verificó. **EFS (cifrado)** no puede generarse desde Linux:
  requiere Windows y la clave del usuario, por lo que se explica teóricamente en §7.9 y §9.7.
