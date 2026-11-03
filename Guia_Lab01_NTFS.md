# Laboratorio 1 — Exploración de Discos y NTFS

**Asignatura:** Arquitectura del Computador
**Integrantes:** Alejandro Arbelaez Hoyos · Julián David Guarnizo Castrillón
**Documento:** ______________________________________________
**Fecha:** 28 de octubre de 2026

---

## Índice

1. [Introducción y objetivos](#1-introducción-y-objetivos)
2. [Fundamentos teóricos de NTFS](#2-fundamentos-teóricos-de-ntfs)
3. [Herramientas, materiales y precauciones](#3-herramientas-materiales-y-precauciones)
4. [Construcción del volumen de laboratorio](#4-construcción-del-volumen-de-laboratorio)
5. [Parte 2 — Análisis hexadecimal del sector de arranque](#5-parte-2--análisis-hexadecimal-del-sector-de-arranque)
6. [Parte 3 — El directorio raíz: FAT frente a NTFS](#6-parte-3--el-directorio-raíz-fat-frente-a-ntfs)
7. [Parte 4 — Localización de metadatos y datos de un archivo](#7-parte-4--localización-de-metadatos-y-datos-de-un-archivo)
8. [Evidencias, tablas de valores y verificación](#8-evidencias-tablas-de-valores-y-verificación)
9. [Preguntas de análisis](#9-preguntas-de-análisis)
10. [Conclusiones](#10-conclusiones)
11. [Referencias](#11-referencias)
12. [Anexos](#12-anexos)

---

## 1. Introducción y objetivos

Esta guía documenta, paso a paso, cómo se analiza internamente un volumen **NTFS** (New Technology File System) sin depender de las vistas de alto nivel del sistema operativo. Todo el trabajo se realizó sobre una **imagen de disco de 512 MB** creada para el laboratorio, tal como recomienda el enunciado: *"el análisis debe realizarse sobre un disco virtual de laboratorio o una imagen de disco"*.

La diferencia central frente a una explicación superficial es que aquí **cada afirmación se comprueba en los bytes**: se localiza el sector de arranque, se calcula a mano la posición de la MFT, se abre el registro de un archivo concreto en un editor hexadecimal y se verifica que el contenido del archivo está donde la estructura dice que está.

### Objetivos de aprendizaje

Al finalizar esta guía, el lector será capaz de:

1. Explicar la arquitectura de NTFS y el papel de la MFT, los atributos y los índices de directorio.
2. Identificar el sector de arranque del volumen (VBR) y analizar sus campos en hexadecimal.
3. Comparar la organización del directorio raíz en FAT con la de NTFS.
4. Localizar los registros de metadatos de un archivo a partir de la MFT.
5. Interpretar atributos residentes y no residentes, y descifrar los *data runs*.
6. Documentar el procedimiento con evidencias verificables (hexadecimal, cálculos y hashes).

### Alcance y resultados esperados

El volumen de trabajo contiene archivos deliberadamente elegidos para cubrir **todos** los casos que pide el enunciado:

| Archivo / carpeta | Tamaño | Caso que demuestra |
|---|---|---|
| `LAB_NTFS.txt` | 114 B | Datos **residentes** dentro del registro MFT |
| `umbral_residente.txt` | 2 000 B | Paso del umbral: datos **no residentes** con un único *run* |
| `aleatorio_12MB.bin` | 12 MiB | No residente, *run* largo, verificación por LCN |
| `datos_patron_8MB.bin` | 8 MiB | No residente con contenido reconocible en hexadecimal |
| `comprimidos/comprimido.txt` | 100 000 B → 12 288 B | Atributo `$DATA` con **compresión** NTFS |
| `docs/`, `docs/teoria/` | 6 archivos | Índices de directorio y referencias al padre |
| `muchos/` | 60 archivos | `$INDEX_ALLOCATION` con varios registros `INDX` |

---

## 2. Fundamentos teóricos de NTFS

### 2.1 ¿Qué es un sistema de archivos y cuál es su función?

Un **sistema de archivos** es el componente del sistema operativo que decide *cómo* se guarda la información en un medio de almacenamiento y *cómo* se recupera después. Concretamente, cumple cuatro funciones:

1. **Asignación de espacio:** administra el medio como una secuencia de bloques y decide qué bloques pertenecen a qué archivo.
2. **Nombres y jerarquía:** traduce un nombre legible (`C:\datos\informe.txt`) a una ubicación física.
3. **Metadatos:** conserva fechas, tamaños, permisos, propietario y atributos de cada archivo.
4. **Integridad y recuperación:** mantiene estructuras auxiliares (bitmaps, journal) para saber qué está libre, qué está en uso y cómo recuperarse tras un corte de energía.

Sin un sistema de archivos, el disco sería una cinta de bytes sin fronteras: no habría forma de saber dónde empieza un archivo ni dónde termina.

### 2.2 ¿Qué es NTFS y en qué sistemas operativos se utiliza?

**NTFS** es el sistema de archivos nativo de la familia Windows NT (Windows NT 3.1 en adelante: 2000, XP, Vista, 7, 8, 10, 11 y Windows Server). Sustituyó a FAT como sistema principal por sus requisitos de seguridad y robustez.

Características relevantes para el análisis forense:

- **Estructuras basadas en metadatos tipados (atributos)**, no en campos fijos como FAT.
- **Journaling** mediante `$LogFile`, que permite recuperar la coherencia tras un fallo.
- **Seguridad por ACL** almacenada en `$Secure` y referenciada por cada archivo.
- **Compresión y cifrado por archivo** (compresión LZNT1 y EFS).
- **Soporte de volúmenes muy grandes** (hasta 2^64 clústeres teóricos) y nombres largos en Unicode.
- NTFS es **case-sensitive en el almacenamiento** pero Windows lo presenta como *case-insensitive*; Linux (ntfs-3g) permite ambos comportamientos.

Versiones: la 1.2 (NT 3.51), 3.0 (Windows 2000) y **3.1** (XP en adelante). Los metadatos que se ven en este laboratorio declaran la versión 3.1 (The Sleuth Kit la muestra como "Windows XP").

### 2.3 Diferencias entre FAT16, FAT32 y NTFS

| Característica | FAT16 | FAT32 | NTFS |
|---|---|---|---|
| Estructura de metadatos | Entradas de directorio de 32 bytes | Igual que FAT16 | Registros MFT de 1 024 bytes con atributos tipados |
| Ubicación del directorio raíz | Área fija tras la FAT (FAT16) | Cadena de clústeres cuyo inicio está en el BPB | Registro MFT número 5 (`$Root`) |
| Asignación de espacio | Tabla FAT (cadena de clústeres) | Tabla FAT de 32 bits | `$Bitmap` + *data runs* en el atributo `$DATA` |
| Tamaño máximo de archivo | 2 GiB / 4 GiB según clúster | 4 GiB | ~16 EiB (límite práctico del volumen) |
| Tamaño máximo de volumen | 2 GiB (típico) | 2 TiB | 256 TiB (Windows 10/11) |
| Nombres | 8.3, luego VFAT LFN | VFAT LFN | Unicode hasta 255 caracteres |
| Permisos / seguridad | No | No | ACL por archivo |
| Journaling | No | No | Sí (`$LogFile`) |
| Compresión / cifrado | No | No | Sí (`$DATA` comprimido, EFS) |
| Recuperación de archivos borrados | Fácil (la entrada conserva el nombre) | Fácil | Depende del estado del registro MFT |

La diferencia conceptual más importante para este laboratorio: **FAT guarda la información del archivo en una única entrada de 32 bytes y su contenido en una cadena de clústeres descrita por la tabla FAT; NTFS guarda toda la información en un registro de 1 024 bytes compuesto por atributos, y el contenido puede estar incluso dentro de ese mismo registro.**

### 2.4 ¿Qué son los metadatos y por qué son necesarios?

Los **metadatos** son "datos sobre los datos": no son el contenido del archivo, sino la información que permite interpretarlo y localizarlo. En NTFS incluyen, entre otros:

- nombre y referencia al directorio padre,
- cuatro marcas de tiempo (creación, modificación, cambio de MFT, último acceso),
- tamaños lógico y asignado,
- atributos DOS (solo lectura, oculto, sistema, archivo, comprimido, cifrado),
- propietario y lista de control de acceso (ACL),
- ubicación física del contenido.

Sin metadatos no se puede distinguir un archivo de otro ni saber qué clústeres le pertenecen. Y para el análisis forense son *la* evidencia: permiten reconstruir qué ocurrió, cuándo y en qué orden.

### 2.5 Sectores, clústeres, archivos y directorios

| Concepto | Definición | Valor en este laboratorio |
|---|---|---|
| **Sector** | Unidad mínima de direccionamiento del disco (lógica). | 512 bytes |
| **Clúster** | Unidad mínima de asignación del sistema de archivos: uno o más sectores contiguos. | 8 sectores = **4 096 bytes** |
| **Archivo** | Conjunto de datos con nombre, metadatos y contenido. | — |
| **Directorio** | Archivo especial cuyo contenido es un índice de nombres → registros MFT. | `$Root` = registro 5 |

Un archivo de 114 bytes ocupa **un** registro MFT y **cero** clústeres de datos (es residente). Un archivo de 12 MiB ocupa 3 072 clústeres (12 582 912 / 4 096).

> **Advertencia metodológica:** el tamaño del clúster lo define el volumen, no el disco. Nunca debe asumirse 4 096 bytes: hay que leerlo del VBR (campos 0x0B y 0x0D).

### 2.6 La MFT, los atributos y los registros de directorio

La **Master File Table (MFT)** es una base de datos relacional implementada como un archivo: un arreglo de registros de 1 024 bytes (tamaño típico), uno por cada archivo o directorio del volumen. Los primeros registros están reservados para metadatos del sistema:

| Registro | Nombre | Contenido |
|---|---|---|
| 0 | `$MFT` | La propia tabla maestra (se describe a sí misma) |
| 1 | `$MFTMirr` | Copia de los primeros registros críticos |
| 2 | `$LogFile` | Diario de transacciones |
| 3 | `$Volume` | Nombre, versión y estado del volumen |
| 4 | `$AttrDef` | Definición de los tipos de atributo |
| **5** | **`$Root`** | **Directorio raíz** |
| 6 | `$Bitmap` | Mapa de clústeres libres/ocupados |
| 7 | `$Boot` | Código de arranque del volumen |
| 8 | `$BadClus` | Clústeres defectuosos |
| 9 | `$Secure` | Descriptores de seguridad (ACL) |
| 10 | `$UpCase` | Tabla de conversión a mayúsculas |
| 11 | `$Extend` | Directorio de metadatos extendidos |

Cada registro se compone de una **cabecera** y una lista de **atributos**. Un atributo tiene un tipo numérico, un nombre opcional, un tamaño y un contenido que puede ser:

- **residente:** el valor vive dentro del propio registro MFT;
- **no residente:** el valor vive en clústeres externos y el atributo guarda un *runlist* (lista de segmentos).

Atributos que se analizan en esta guía:

| Atributo | Tipo | Función |
|---|---|---|
| `$STANDARD_INFORMATION` | 0x10 | Fechas, atributos DOS, propietario, cuota |
| `$ATTRIBUTE_LIST` | 0x20 | Lista de atributos cuando no caben en un solo registro |
| `$FILE_NAME` | 0x30 | Nombre, referencia al padre, fechas y tamaños "de directorio" |
| `$SECURITY_DESCRIPTOR` | 0x50 | ACL del archivo |
| `$DATA` | 0x80 | Contenido del archivo (residente o no residente) |
| `$INDEX_ROOT` | 0x90 | Raíz del índice de un directorio (vive en la MFT) |
| `$INDEX_ALLOCATION` | 0xA0 | Índice externo del directorio (registros `INDX`) |
| `$BITMAP` | 0xB0 | Mapa de bits del índice del directorio |

Los **registros de directorio** en NTFS no son listas secuenciales como en FAT: son **árboles B+** implementados con `$INDEX_ROOT` (la raíz, siempre residente) y, cuando crece, `$INDEX_ALLOCATION` (bloques de 4 096 bytes con firma `INDX`). Cada entrada del índice contiene el nombre del archivo y su **referencia MFT** (número de registro + número de secuencia).

### 2.7 Diagrama de la organización lógica de un volumen NTFS

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ IMAGEN DE DISCO (ntfs_lab.img, 512 MiB = 1 048 576 sectores de 512 B)        │
│                                                                              │
│  0x00000000 ┌──────────────────────────────────────────┐                     │
│             │ Sector 0: MBR                            │                     │
│             │  · código de arranque                    │                     │
│             │  · tabla de particiones (4 entradas)     │ ← Parte 2 (contexto)│
│             │  · firma 55 AA                           │                     │
│             └──────────────────────────────────────────┘                     │
│  0x00000200 … sectores 1–2047: sin usar (alineación) …                       │
│                                                                              │
│  0x00100000 ┌──────────────────────────────────────────┐  ← VBR (sector 2048)│
│  (1 MiB)    │ VBR / NTFS Boot Sector (512 B)           │  ← Parte 2          │
│             │  0x03 OEM "NTFS    "                     │                     │
│             │  0x0B bytes/sector = 512                 │                     │
│             │  0x0D sectores/clúster = 8               │                     │
│             │  0x30 LCN de $MFT = 4                    │──┐                  │
│             │  0x40 tamaño de registro MFT = 0xF6      │  │                  │
│             └──────────────────────────────────────────┘  │                  │
│                                                           │                  │
│  VOLUMEN NTFS (clúster C = 4 096 B)                       │                  │
│                                                           ▼                  │
│  0x00104000 ┌──────────────────────────────────────────┐                     │
│             │ $MFT: registros de 1 024 B               │  ← Parte 4          │
│             │  #0 $MFT    #1 $MFTMirr   #2 $LogFile    │                     │
│             │  #3 $Volume #4 $AttrDef   #5 $Root  ────┼──┐  ← Parte 3        │
│             │  #6 $Bitmap #7 $Boot      #8 $BadClus   │  │                   │
│             │  … #64 LAB_NTFS.txt  #66 …  #138 …       │  │                  │
│             └──────────────────────────────────────────┘  │                  │
│                                                           │                  │
│  0x00105400 ┌──────────────────────────────────────────┐◄─┘                  │
│             │ Registro #5 = $Root (directorio raíz)    │  ← Parte 3          │
│             │  $INDEX_ROOT  ($I30)  ───────────────┐  │                      │
│             │  $INDEX_ALLOCATION ($I30) ─────────┐ │  │                      │
│             └────────────────────────────────────┼─┼──┘                      │
│                                                  │ │                         │
│  0x040E5000 ┌────────────────────────────────────┘ │                         │
│             │ Registro INDX (4 096 B)              │                         │
│             │  entradas: nombre + referencia MFT   │                         │
│             └──────────────────────────────────────┘                         │
│                                                                              │
│  Clústeres de datos ($DATA no residente)                                     │
│    LCN 20552 → 0x05148000  aleatorio_12MB.bin                                │
│    LCN 24648 → 0x06148000  datos_patron_8MB.bin                              │
│    LCN 36936 → 0x09148000  comprimido.txt (unidades de compresión)           │
└──────────────────────────────────────────────────────────────────────────────┘
```

La idea que este diagrama debe transmitir es exactamente la que pide el enunciado: **NTFS no guarda nombres, fechas y contenido en una sola estructura**. Los nombres y referencias están en los índices del directorio, las fechas y atributos en los registros MFT, y el contenido en el propio registro o en clústeres externos según su tamaño.

### 2.8 Anatomía de un registro MFT (cabecera)

| Offset | Tamaño | Campo | Comentario |
|---|---|---|---|
| 0x00 | 4 | Firma | `FILE` (en uso) o `BAAD` |
| 0x04 | 2 | Offset del Update Sequence Array | Normalmente 0x30 |
| 0x06 | 2 | Número de entradas de la USA | 3 para registros de 1 024 B con sectores de 512 B |
| 0x08 | 8 | $LogFile Sequence Number | |
| 0x10 | 2 | Número de secuencia del registro | |
| 0x12 | 2 | Número de enlaces duros | |
| 0x14 | 2 | Offset del primer atributo | Normalmente 0x38 |
| 0x16 | 2 | Flags | 0x01 = en uso, 0x02 = directorio |
| 0x18 | 4 | Bytes usados en el registro | |
| 0x1C | 4 | Bytes asignados | 1 024 |
| 0x20 | 8 | Referencia al registro base | 0 si es un registro base |
| 0x28 | 2 | Siguiente ID de atributo | |
| 0x2C | 4 | Número de este registro en la MFT | Solo en NTFS 3.1 |

La **Update Sequence Array** es un mecanismo de integridad: si el tamaño del sector es menor que el del registro, NTFS reemplaza los últimos 2 bytes de cada sector por un número de secuencia y guarda los originales en la USA. Un lector debe **restaurar** esos bytes antes de interpretar el registro.

---

## 3. Herramientas, materiales y precauciones

### 3.1 Materiales

- Máquina virtual Linux (Kali) con **The Sleuth Kit**, **ntfs-3g** y utilidades básicas.
- Imagen de disco `ntfs_lab.img` (512 MiB) generada para la práctica.
- Volumen NTFS alternativo `vol_ntfs_solo.img` (la partición sin MBR, para el caso V = 0).

### 3.2 Herramientas utilizadas

| Herramienta | Paquete | Uso en esta guía |
|---|---|---|
| `mmls` | sleuthkit | Leer la tabla de particiones del MBR |
| `fsstat` | sleuthkit | Mostrar los parámetros del sistema de archivos |
| `fls` | sleuthkit | Listar archivos con su número de registro MFT |
| `istat` | sleuthkit | Mostrar atributos y *runlist* de un registro |
| `icat` | sleuthkit | Extraer el contenido de un archivo por número de MFT |
| `xxd`, `hexdump` | vim-common / util-linux | Volcados hexadecimales con offsets |
| `dd`, `sfdisk`, `mmls` | util-linux / sleuthkit | Crear y particionar la imagen |
| `mkntfs` | ntfs-3g | Formatear el volumen NTFS |
| `ntfsinfo`, `ntfscluster`, `ntfscat` | ntfs-3g | Contrastar metadatos y *runs* con otra implementación |
| `sha256sum` | coreutils | Verificar integridad de evidencias |
| `autopsy` | sleuthkit | Interfaz gráfica de análisis (opcional) |
| `fsutil` | Windows | Contraste opcional desde Windows |

### 3.3 Precauciones

1. **Nunca se analiza el disco original en modo escritura.** Todo el trabajo se hace sobre `ntfs_lab.img`; las herramientas TSK abren la imagen en solo lectura.
2. **Registrar el hash de la imagen antes de empezar** (ver §8.3). Si el hash cambia, la evidencia dejó de ser confiable.
3. **No confundir MBR con VBR.** El MBR está en el sector 0 del *disco*; el VBR está en el primer sector del *volumen* (aquí, sector 2048 de la imagen).
4. **Tener en cuenta el desplazamiento de la partición.** Analizar la imagen completa sin restar el offset produce lecturas erróneas.
5. **No asumir tamaños.** Clúster y registro MFT se leen del VBR; pueden ser distintos en cada volumen.
6. **No asumir que un archivo pequeño es residente.** Se comprueba en el atributo `$DATA` (véase `umbral_residente.txt`, 2 000 B, no residente).

---

## 4. Construcción del volumen de laboratorio

El enunciado exige un disco virtual o una imagen. Se construyó una **imagen de disco completa de 512 MiB con MBR**, no solo un volumen suelto, para poder comparar MBR y VBR en la misma práctica.

### 4.1 Creación de la imagen y la tabla de particiones

```bash
# 1) Imagen dispersa de 512 MiB (536 870 912 bytes = 1 048 576 sectores de 512 B)
dd if=/dev/zero of=ntfs_lab.img bs=1M count=0 seek=512

# 2) Tabla de particiones MBR con una partición primaria tipo 07 (NTFS)
#    que comienza en el sector 2048 (offset 1 MiB, alineación habitual)
echo 'label: dos
unit: sectors

start=2048, size=1046512, type=7' | sfdisk ntfs_lab.img

# 3) Formateo NTFS del volumen (clúster de 4 096 B)
dd if=/dev/zero of=vol_ntfs_solo.img bs=512 count=0 seek=1046512
mkntfs -F -Q -L LAB_NTFS -c 4096 -s 512 -p 2048 -H 255 -S 63 vol_ntfs_solo.img 1046512

# 4) Inserción del volumen dentro de la imagen particionada
dd if=vol_ntfs_solo.img of=ntfs_lab.img bs=1M seek=1 conv=notrunc
```

> **Observación técnica:** `mkntfs -p 2048` **no** formatea en un desplazamiento; solo escribe el valor de *sectores ocultos* en el BPB. Por eso el volumen se formatea aparte y luego se inserta con `dd`. Este detalle es una fuente habitual de errores y conviene documentarlo.

### 4.2 Poblado del volumen

Los archivos se generaron con un script reproducible (Anexo A), se copiaron con el volumen montado en `ntfs-3g` y luego se desmontó. La carpeta `comprimidos/` recibió el atributo comprimido **antes** de copiar el archivo, de modo que solo ese archivo quedara comprimido (en NTFS la compresión se hereda del directorio, igual que en Windows con "Comprimir contenido").

### 4.3 Verificación inicial

```
$ mmls ntfs_lab.img
DOS Partition Table
Offset Sector: 0
Units are in 512-byte sectors

      Slot      Start        End          Length       Description
000:  Meta      0000000000   0000000000   0000000001   Primary Table (#0)
001:  -------   0000000000   0000002047   0000002048   Unallocated
002:  000:000   0000002048   0001048559   0001046512   NTFS / exFAT (0x07)
003:  -------   0001048560   0001048575   0000000016   Unallocated
```

```
$ fsstat -o 2048 ntfs_lab.img
FILE SYSTEM INFORMATION
--------------------------------------------
File System Type: NTFS
Volume Serial Number: 0D8E2D287A1CF381
OEM Name: NTFS
Volume Name: LAB_NTFS
Version: Windows XP

METADATA INFORMATION
--------------------------------------------
First Cluster of MFT: 4
First Cluster of MFT Mirror: 65406
Size of MFT Entries: 1024 bytes
Size of Index Records: 4096 bytes
Range: 0 - 139
Root Directory: 5

CONTENT INFORMATION
--------------------------------------------
Sector Size: 512
Cluster Size: 4096
Total Cluster Range: 0 - 130812
```

Estos cuatro datos —**MFT en el clúster 4**, **registros de 1 024 B**, **clúster de 4 096 B** y **raíz en el registro 5**— son los que se van a recalcular a mano en las secciones siguientes.

---

## 5. Parte 2 — Análisis hexadecimal del sector de arranque

### 5.1 MBR frente a VBR: no son equivalentes

| | **MBR** (Master Boot Record) | **VBR** (Volume Boot Record / NTFS Boot Sector) |
|---|---|---|
| Ubicación | Sector 0 **del disco** | Primer sector **del volumen** (aquí, sector 2048) |
| Tamaño | 512 B | 512 B |
| Contenido | Código de arranque + tabla de 4 particiones + firma 55 AA | Parámetros del sistema de archivos (BPB) + código + firma 55 AA |
| Función | Decir **dónde empieza y termina** cada partición | Decir **cómo está organizado** el sistema de archivos dentro de la partición |
| ¿Permite ubicar la MFT? | No | **Sí** (campo 0x30) |

El MBR describe el *disco*; el VBR describe el *volumen*. Para entender NTFS hay que analizar el **VBR**. Un disco puede contener un MBR y ningún NTFS; un volumen NTFS puede existir sin MBR (por ejemplo, una partición extraída o un archivo `.img` del volumen).

### 5.2 Procedimiento

1. Identificar el disco y el volumen:
   ```bash
   mmls ntfs_lab.img          # muestra que la partición NTFS empieza en el sector 2048
   lsblk                      # en un disco real: /dev/sdX, /dev/sdX1
   ```
2. Calcular el desplazamiento del volumen:
   `V = 2048 sectores × 512 B = 1 048 576 B = 0x100000`.
3. Volcar los primeros 512 bytes del volumen:
   ```bash
   xxd -s $((2048*512)) -l 512 ntfs_lab.img
   ```
4. Registrar los campos de la tabla 5.3.
5. Interpretar cada valor y contrastarlo con `fsstat`/`ntfsinfo`.

![Figura 1 — `mmls ntfs_lab.img`: la partición NTFS (tipo 0x07) comienza en el sector 2048 y mide 1 046 512 sectores.](mis_evidencias/capturas/02-Tabla_particiones.png)

### 5.3 Volcado real (primeros 96 bytes del VBR)

```
00100000: eb52 904e 5446 5320 2020 2000 0208 0000  .R.NTFS    .....
00100010: 0000 0000 00f8 0000 3f00 ff00 0008 0000  ........?.......
00100020: 0000 0000 8000 8000 eff7 0f00 0000 0000  ................
00100030: 0400 0000 0000 0000 7eff 0000 0000 0000  ........~.......
00100040: f600 0000 0100 0000 81f3 1c7a 282d 8e0d  ...........z(-..
00100050: 0000 0000 0e1f be71 7cac 22c0 740b 56b4  .......q|.".t.V.
```

El volcado completo está en `mis_evidencias/03_vbr_hex.txt`.

![Figura 2 — Volcado hexadecimal del VBR en 0x100000: se reconocen el OEM ID `NTFS`, los parámetros del BPB y la firma `55 AA` al final del sector.](mis_evidencias/capturas/04-Sector_arranque_hexadecorial.png)

### 5.4 Tabla de campos con los valores encontrados

| Offset | Campo | Bytes | Hex en la imagen | Interpretación |
|---|---|---|---|---|
| 0x00–0x02 | Salto inicial | 3 | `eb 52 90` | `JMP` al código de arranque |
| **0x03–0x0A** | **OEM ID** | 8 | `4e 54 46 53 20 20 20 20` | **`NTFS    `** |
| **0x0B–0x0C** | **Bytes por sector** | 2 | `00 02` | **512** (little-endian) |
| **0x0D** | **Sectores por clúster** | 1 | `08` | **8** |
| 0x0E–0x0F | Sectores reservados | 2 | `00 00` | 0 |
| 0x15 | Descriptor de medio | 1 | `f8` | 0xF8 = disco fijo |
| 0x18–0x19 | Sectores por pista | 2 | `3f 00` | 63 |
| 0x1A–0x1B | Cabezas | 2 | `ff 00` | 255 |
| 0x1C–0x1F | Sectores ocultos | 4 | `00 08 00 00` | 2 048 (inicio de la partición) |
| **0x28–0x2F** | **Total de sectores** | 8 | `ef f7 0f 00 00 00 00 00` | **1 046 511** (0x0FF7EF) ≈ 511 MiB |
| **0x30–0x37** | **LCN inicial de `$MFT`** | 8 | `04 00 00 00 00 00 00 00` | **4** |
| **0x38–0x3F** | **LCN inicial de `$MFTMirr`** | 8 | `7e ff 00 00 00 00 00 00` | **65 406** |
| **0x40** | **Tamaño de registro MFT** | 1 | `f6` | **−10 → 2^10 = 1 024 bytes** |
| 0x44 | Tamaño de registro de índice | 1 | `01` | 1 clúster = 4 096 bytes |
| **0x48–0x4F** | **Número de serie** | 8 | `81 f3 1c 7a 28 2d 8e 0d` | **0x0D8E2D287A1CF381** |
| 0x50–0x53 | Suma de verificación | 4 | `00 00 00 00` | No usada por NTFS |
| **0x1FE–0x1FF** | **Firma de arranque** | 2 | `55 aa` | **55 AA** |

### 5.5 Interpretación de los valores

**a) Orden de bytes.** Todos los campos numéricos son *little-endian*: el valor `00 02` en 0x0B significa 0x0200 = 512, no 0x0002.

**b) Tamaño del clúster.** Del VBR se obtiene directamente:

```
C = bytes por sector × sectores por clúster
C = 512 × 8 = 4 096 bytes
```

**c) El byte 0x40 no es un tamaño directo.** Su codificación es especial:

- si el valor es **positivo** (1…127), indica **clústeres por registro MFT**;
- si es **negativo** (−1…−128), indica que el tamaño es **2^|valor| bytes**.

Aquí `0xF6` = **−10** → `2^10 = 1 024 bytes`. Interpretarlo como "246 bytes" es un error frecuente. El mismo esquema se aplica al byte 0x44 para los registros de índice (aquí `0x01` → 1 clúster = 4 096 B).

**d) Total de sectores.** `0x0FF7EF` = 1 046 511 sectores × 512 = 535 813 632 B ≈ 511 MiB. La partición declarada en el MBR tiene 1 046 512 sectores; el volumen usa uno menos porque el último sector se reserva para la **copia de respaldo del sector de arranque**.

**e) Número de serie.** `0x0D8E2D287A1CF381` es el identificador único del volumen (coincide con `fsstat`). Es el dato que permite correlacionar una imagen con un volumen concreto.

**f) Sectores ocultos (0x1C).** Vale 2 048, exactamente el inicio de la partición. Es la prueba de que el BPB se generó con `-p 2048` y de que el sistema operativo puede calcular el inicio real del volumen a partir del MBR.

### 5.6 Firma del sector de arranque y copia de respaldo

La firma `55 AA` en 0x1FE marca el sector como válido. NTFS guarda además una **copia del VBR en el último sector de la partición**:

```
Último sector de la partición = 2 048 + 1 046 512 − 1 = 1 048 559
Offset copia = 1 048 559 × 512 = 536 862 208 = 0x1FFFDE00
```

> **Precisión:** el campo «total de sectores» del VBR vale 1 046 511. Si se usa directamente como `V + (1 046 510) × 512` se obtiene `0x1FFFDC00`, **un sector antes**, donde el contenido es cero. La copia real está en `0x1FFFDE00` (último sector de la partición) y es **idéntica byte a byte** al VBR, comprobado con `cmp`.

Comparar el VBR con su copia es una comprobación forense rápida: si difieren, el volumen pudo ser modificado o estar dañado.

---

## 6. Parte 3 — El directorio raíz: FAT frente a NTFS

### 6.1 Comparación estructural

| Característica | FAT16 / FAT32 | NTFS |
|---|---|---|
| Registro de archivos | Entrada de directorio de **32 bytes** | Registro de la **MFT** de 1 024 bytes |
| Directorio raíz | **Área fija** de entradas (FAT16) o cadena de clústeres con inicio en el BPB (FAT32) | **Registro MFT número 5** (`$Root`) |
| Organización del directorio | Entradas **consecutivas** en el directorio | **Índice B+**: `$INDEX_ROOT` y, si crece, `$INDEX_ALLOCATION` |
| Metadatos | Campos fijos de la entrada (nombre 8.3, atributos, hora, fecha, primer clúster, tamaño) | Atributos tipados asociados al registro MFT |
| Localización del contenido | Clúster inicial + **cadena en la tabla FAT** | Atributo `$DATA` con *runs* (o datos residentes) |
| Nombres largos | VFAT LFN (entradas auxiliares) | UTF-16 dentro de `$FILE_NAME` |
| Búsqueda de un nombre | Recorrido lineal de las entradas | Recorrido de árbol B+ (ordenado por nombre) |

**Consecuencia práctica:** en FAT el directorio raíz es una región del disco cuya posición y tamaño están fijados por el formato; en NTFS el directorio raíz es **un archivo más**, descrito por el registro 5 y potencialmente fragmentado como cualquier otro archivo.

### 6.2 Procedimiento

1. Calcular el inicio de la MFT (véase §7.2): `0x104000`.
2. Localizar el registro 5:
   ```bash
   python3 parse_mft.py 5          # o bien: istat -o 2048 ntfs_lab.img 5
   ```
3. Verificar la firma `FILE` al inicio del registro.
4. Identificar los atributos `$INDEX_ROOT` (0x90) y `$INDEX_ALLOCATION` (0xA0), ambos con nombre `$I30`.
5. Leer el contenido del índice donde están los nombres y las referencias MFT.
6. Comprobar en el `$BITMAP` (0xB0) qué bloques del índice están en uso.

![Figura 3 — `fls -r -p` del volumen: cada línea muestra el tipo, el número de registro MFT y el nombre; se aprecia `LAB_NTFS.txt` con registro 64 y los `$OrphanFiles` 16–23.](mis_evidencias/capturas/06-Directorio_raiz.png)

### 6.3 Evidencia: registro 5 (`$Root`) en hexadecimal

```
00105400: 4649 4c45 3000 0300 0000 0000 0000 0000  FILE0...........
00105410: 0500 0100 3800 0300 0002 0000 0004 0000  ....8...........
00105420: 0000 0000 0000 0000 0600 0000 0500 0000  ................
00105430: 0b00 0000 0000 0000 1000 0000 4800 0000  ............H...
```

Lectura de la cabecera:

| Offset | Bytes | Campo | Valor |
|---|---|---|---|
| 0x00 | 4 | Firma | `FILE` |
| 0x04 | 2 | Offset USA | 0x0030 |
| 0x06 | 2 | Entradas USA | 3 |
| 0x10 | 2 | Secuencia | 5 |
| 0x12 | 2 | Enlaces duros | 1 |
| 0x14 | 2 | Offset del primer atributo | 0x0038 |
| 0x16 | 2 | Flags | **0x0003 = en uso + directorio** |
| 0x18 | 4 | Bytes usados | 0x0200 = 512 |
| 0x1C | 4 | Bytes asignados | 0x0400 = 1 024 |
| 0x2C | 4 | Número de registro | 5 |

Atributos del registro 5 (recorrido real con `parse_mft.py 5`):

| Offset en el registro | Tipo | Nombre | Tamaño | Residente |
|---|---|---|---|---|
| 0x0038 | 0x10 `$STANDARD_INFORMATION` | — | 72 | Sí |
| 0x0080 | 0x30 `$FILE_NAME` | `.` (raíz) | 96 | Sí |
| 0x00E0 | 0x50 `$SECURITY_DESCRIPTOR` | — | 72 | No (LCN 16 355) |
| **0x0128** | **0x90 `$INDEX_ROOT`** | **`$I30`** | **88** | **Sí** |
| **0x0180** | **0xA0 `$INDEX_ALLOCATION`** | **`$I30`** | **80** | **No (LCN 16 357)** |
| 0x01D0 | 0xB0 `$BITMAP` | `$I30` | 40 | Sí |

![Figura 4 — `istat -o 2048 ntfs_lab.img 5`: registro del directorio raíz con `$INDEX_ROOT` e `$INDEX_ALLOCATION` (`$I30`), `$SECURITY_DESCRIPTOR` no residente y `$BITMAP`.](mis_evidencias/capturas/07-Registro_directorio_raiz.png)

![Figura 5 — Volcado hexadecimal del registro 5 en 0x105400: firma `FILE`, flags `0x0003` (directorio) y los atributos `0x90` (`$INDEX_ROOT`) y `0xA0` (`$INDEX_ALLOCATION`).](mis_evidencias/capturas/08-Directorio_raiz_hexadecimal.png)

### 6.4 El `$INDEX_ROOT` del directorio raíz

El valor residente del `$INDEX_ROOT` (56 bytes, en el offset absoluto 0x105548) es:

```
30 00 00 00 01 00 00 00 00 10 00 00 01 00 00 00
10 00 00 00 28 00 00 00 28 00 00 00 01 00 00 00
00 00 00 00 00 00 00 00 18 00 00 00 03 00 00 00
00 00 00 00 00 00 00 00
```

| Campo | Valor | Significado |
|---|---|---|
| Tipo de atributo indexado | `0x30` | El índice ordena por `$FILE_NAME` |
| Regla de ordenación | `1` | Orden por nombre (mayúsculas colapsadas) |
| Tamaño del bloque de índice | `0x1000` = 4 096 | Cada registro `INDX` ocupa 4 096 B |
| Clústeres por registro de índice | `1` | 1 clúster = 4 096 B |
| Offset a la primera entrada | `0x10` | 16 bytes desde el inicio de la cabecera de índice |
| Tamaño total de entradas | `0x28` = 40 | Solo la entrada de fin |
| **Flags** | **`0x01`** | **El índice continúa en `$INDEX_ALLOCATION`** |

Es decir: la raíz del árbol B+ ya no cabe completamente en el registro MFT y sus entradas viven en bloques externos. Por eso `$INDEX_ROOT` solo conserva la cabecera y el marcador de fin.

### 6.5 El `$INDEX_ALLOCATION` y los registros `INDX`

El atributo es no residente y su *runlist* es `21 01 e5 3f`:

- `0x21` → longitud en 1 byte, offset en 2 bytes;
- longitud = `01` → 1 clúster;
- offset = `0x3FE5` = 16 357 → LCN 16 357.

Posición física:

```
Offset = V + LCN × C = 1 048 576 + 16 357 × 4 096 = 68 046 848 = 0x040E5000
```

```
040e5000: 494e 4458 2800 0900 0000 0000 0000 0000  INDX(...........
040e5010: 0000 0000 0000 0000 2800 0000 e007 0000  ........(.......
040e5020: e80f 0000 0000 0000 0414 dd01 0000 0000  ................
040e5030: 0500 0000 0000 0000 0000 0000 0000 0000  ................
040e5040: 0400 0000 0000 0400 6800 5200 0000 0000  ........h.R.....
040e5090: 0803 2400 4100 7400 7400 7200 4400 6500  ..$.A.t.t.r.D.e.
```

- **Firma `INDX`** en 0x00.
- **VCN** = 0 en 0x10 (primer bloque del índice).
- Cabecera de índice en 0x18: primera entrada en 0x28 (relativa) → offset 0x40, tamaño total 0x07E0, espacio asignado 0x0FE8.
- La primera entrada (0x40) describe `$AttrDef`:

| Offset | Campo | Valor | Interpretación |
|---|---|---|---|
| 0x00 | Referencia MFT | `04 00 00 00 00 00 04 00` | **registro 4**, secuencia 4 → `$AttrDef` |
| 0x08 | Longitud de la entrada | `68 00` | 104 bytes |
| 0x0A | Longitud de la clave | `52 00` | 82 bytes |
| 0x0C | Flags | `00 00` | Entrada normal |
| 0x10 | Clave = `$FILE_NAME` | … | Referencia al padre (5), fechas, tamaños |
| 0x50 | Longitud y namespace del nombre | `08 03` | 8 caracteres, namespace 3 (Win32) |
| 0x52 | Nombre | `24 00 41 00 74 00 …` | **`$AttrDef`** en UTF-16LE |

**Cómo se representan nombres y referencias:** el nombre va en UTF-16LE (`0x24 0x00` = `$`, `0x41 0x00` = `A`, …) y cada entrada lleva la **referencia MFT** de 8 bytes, que es lo que permite saltar del índice al registro con los metadatos completos. Los nombres de los archivos del usuario se ven igual en el resto del bloque; el listado completo, con número de registro, se obtiene con:

```bash
fls -o 2048 ntfs_lab.img | head
#  r/r 64-128-2:  LAB_NTFS.txt
#  d/d 68-144-2:  docs
#  r/r 66-128-2:  aleatorio_12MB.bin
```

### 6.6 El caso de un directorio con muchas entradas

La carpeta `muchos/` (registro MFT 76) contiene 60 archivos. Su `$INDEX_ALLOCATION` tiene *runlist* `31 03 48 80` → 3 clústeres desde el LCN 32 840, es decir 12 288 B = **3 registros `INDX`** enlazados por VCN. Su `$BITMAP` indica cuáles de esos bloques están en uso. En cambio, la carpeta `docs/`, con menos contenido, necesita un solo bloque.

**Respuesta a la pregunta de análisis de la Parte 3:** que el directorio raíz sea un registro MFT aporta (1) **uniformidad** —todo objeto del volumen es un registro con los mismos atributos, incluido el directorio raíz—; (2) **crecimiento ilimitado y ordenado** mediante un árbol B+ con búsquedas O(log n) en lugar de recorridos lineales; (3) **metadatos completos** (fechas, ACL, atributos) para el propio directorio; (4) **fragmentabilidad controlada**, ya que el índice puede repartirse en bloques `INDX` sin mover el registro; y (5) **journaling** de las modificaciones del índice.

---

## 7. Parte 4 — Localización de metadatos y datos de un archivo

### 7.1 Flujo de análisis

```
nombre visible  →  referencia MFT  →  registro MFT  →  atributos  →  datos
   fls              (número N)        OffsetMFT+N×R    0x10/0x30/0x80   residente o LCN
```

### 7.2 Cálculo de la posición de la MFT (con valores reales)

Datos del VBR:

| Parámetro | Valor |
|---|---|
| Bytes por sector (B) | 512 |
| Sectores por clúster (S) | 8 |
| Tamaño de clúster (C = B × S) | **4 096 bytes** |
| LCN inicial de `$MFT` | **4** |
| Desplazamiento del volumen en la imagen (V) | 2 048 × 512 = **1 048 576 B = 0x100000** |

```
OffsetMFT = V + (LCN_MFT × C)
          = 1 048 576 + (4 × 4 096)
          = 1 048 576 + 16 384
          = 1 064 960 bytes = 0x104000
```

Comprobación: en 0x104000 debe aparecer la firma `FILE` del registro 0 (`$MFT`).

```
00104000: 4649 4c45 3000 0300 0000 0000 0000 0000  FILE0...........
```

> Si se analiza solo el volumen (`vol_ntfs_solo.img`), entonces **V = 0** y `OffsetMFT = 16 384 = 0x4000`.

![Figura 6 — `fsstat -o 2048`: confirma bytes por sector 512, clúster 4 096 B, `$MFT` en LCN 4, raíz en el registro 5 y registros de 1 024 B.](mis_evidencias/capturas/03-Parametros_sistema_archivos.png)

![Figura 7 — Firma `FILE` en 0x104000: el offset calculado para la `$MFT` contiene el registro 0, como se esperaba.](mis_evidencias/capturas/05-Firma_FILE_MFT.png)

### 7.3 El archivo de prueba

| Propiedad | Valor |
|---|---|
| Nombre | `LAB_NTFS.txt` |
| Tamaño | **114 bytes** |
| Registro MFT | **64** (0x40) |
| Ubicación | raíz del volumen (`$Root`, registro 5) |
| Creado | 2026-10-21 20:19:44 (EDT) |
| Modificado | 2026-10-21 18:30:00 (EDT) |
| SHA-256 | `ffef8fb0bb1ef274fe4d94d462e99a02275a7ac7366f014fad7a825cdc5fbe6d` |

Contenido exacto:

```text
Arquitectura del Computador
Laboratorio de sistemas de archivos NTFS
Archivo de prueba para análisis hexadecimal
```

### 7.4 Localización del registro 64

```
Offsetregistro = OffsetMFT + (N × R)
               = 1 064 960 + (64 × 1 024)
               = 1 064 960 + 65 536
               = 1 130 496 = 0x114000
```

Volcado (primeras cuatro líneas):

```
00114000: 4649 4c45 3000 0300 0000 0000 0000 0000  FILE0...........
00114010: 0100 0100 3800 0100 f801 0000 0004 0000  ....8...........
00114020: 0000 0000 0000 0000 0400 0000 4000 0000  ............@...
00114030: 0600 0000 0000 0000 1000 0000 4800 0000  ............H...
```

Cabecera interpretada:

| Offset | Campo | Valor | Interpretación |
|---|---|---|---|
| 0x00 | Firma | `FILE` | Registro válido |
| 0x04 | Offset USA | 0x0030 | |
| 0x06 | Entradas USA | 3 | Registro de 1 024 B = 2 sectores + 1 |
| 0x10 | Secuencia | 1 | |
| 0x12 | Enlaces duros | 1 | |
| 0x14 | Offset del primer atributo | 0x0038 | 56 |
| 0x16 | Flags | `0x0001` | **En uso, no es directorio** |
| 0x18 | Bytes usados | 0x01F8 | 504 |
| 0x1C | Bytes asignados | 0x0400 | 1 024 |
| 0x20 | Registro base | 0 | Es un registro base |
| 0x28 | Siguiente ID de atributo | 4 | |
| 0x2C | Número de registro | `40 00 00 00` | **64** ✔ |

### 7.5 Recorrido de atributos (offsets absolutos dentro de la imagen)

| Offset absoluto | Tipo | Nombre | Longitud | Residente | Valor (offset absoluto) |
|---|---|---|---|---|---|
| 0x114038 | 0x10 `$STANDARD_INFORMATION` | — | 72 | Sí | 0x114050 (48 B) |
| 0x114080 | 0x30 `$FILE_NAME` | `LAB_NTFS.txt` | 120 | Sí | 0x114098 (90 B) |
| 0x1140F8 | 0x50 `$SECURITY_DESCRIPTOR` | — | 104 | Sí | 0x114110 (80 B) |
| **0x114160** | **0x80 `$DATA`** | — | **144** | **Sí** | **0x114178 (114 B)** |
| 0x1141F0 | — | Fin de atributos | — | — | `FF FF FF FF` |

El `$FILE_NAME` contiene:

| Campo | Valor |
|---|---|
| Referencia al padre | registro **5** (`$Root`) ✔ |
| Nombre | `LAB_NTFS.txt` (12 caracteres, UTF-16LE) |
| Tamaños | 120 asignado / 0 real (los tamaños reales están en `$DATA`) |
| Fechas | creación, modificación, cambio de MFT, acceso |

Se observa el nombre en UTF-16LE a partir de 0x1140DC (longitud en 0x1140D8 y namespace en 0x1140DA):

```
001140d0: 2000 0000 0000 0000 0c00 4c00 4100 4200   .........L.A.B.
001140e0: 5f00 4e00 5400 4600 5300 2e00 7400 7800  _.N.T.F.S...t.x.
001140f0: 7400 0000 0000 0200 5000 0000 6800 0000  t.......P...h...
```

![Figura 8 — `istat -o 2048 ntfs_lab.img 64`: `$STANDARD_INFORMATION`, `$FILE_NAME` (`LAB_NTFS.txt`, padre 5) y `$DATA` residente de 114 B.](mis_evidencias/capturas/09-Registro_MFT_64.png)

![Figura 9 — Volcado hexadecimal del registro 64 en 0x114000: atributos desde 0x114038, contenido residente en 0x114178 y fin de atributos `FF FF FF FF` en 0x1141F0.](mis_evidencias/capturas/10-Registro_64_Hexadecimal.png)

### 7.6 Caso A — archivo residente: el contenido está en la MFT

El atributo `$DATA` (0x114160) es **residente**: su valor de 114 bytes está en el propio registro, en 0x114178.

```
00114160: 8000 0000 9000 0000 0000 0000 0000 0200  ................
00114170: 7200 0000 1800 0000 4172 7175 6974 6563  r.......Arquitec
00114180: 7475 7261 2064 656c 2043 6f6d 7075 7461  tura del Computa
00114190: 646f 720a 4c61 626f 7261 746f 7269 6f20  dor.Laboratorio
001141a0: 6465 2073 6973 7465 6d61 7320 6465 2061  de sistemas de a
001141b0: 7263 6869 766f 7320 4e54 4653 0a41 7263  rchivos NTFS.Arc
001141c0: 6869 766f 2064 6520 7072 7565 6261 2070  hivo de prueba p
001141d0: 6172 6120 616e c3a1 6c69 7369 7320 6865  ara an..lisis he
```

Desglose:

- `0x114160`: tipo `80 00 00 00` = `$DATA`.
- `0x114164`: longitud del atributo = `90 00 00 00` = 144.
- `0x114168`: byte de no residente = `00` → **residente**.
- `0x114170–0x114173`: longitud del valor = `72 00 00 00` = **114 bytes**.
- `0x114174–0x114175`: offset del valor = `18 00` = 24 → valor en `0x114160 + 0x18 = 0x114178`.
- `0x11416C–0x11416D`: flags del atributo (`00 00`); `0x11416E–0x11416F`: identificador (`02 00`).

Y en 0x114178 aparece, en ASCII, exactamente el texto del archivo. Nótese el `c3 a1` en 0x1141D0: la `á` de "análisis" codificada en UTF-8 de dos bytes. **No hay ningún clúster de datos involucrado:** el contenido vive dentro de la MFT.

Verificación con una herramienta independiente:

```
$ icat -o 2048 ntfs_lab.img 64 | sha256sum
ffef8fb0bb1ef274fe4d94d462e99a02275a7ac7366f014fad7a825cdc5fbe6d  -
```

Coincide con el hash del archivo original (§8.3): el contenido hallado en la MFT es idéntico byte a byte.

![Figura 10 — `icat -o 2048 ntfs_lab.img 64`: el texto extraído coincide exactamente con el contenido de `LAB_NTFS.txt`, lo que confirma la lectura de los datos residentes.](mis_evidencias/capturas/11-Contenido_archivo.png)

### 7.7 Caso B — archivo no residente: los datos están en clústeres

Ejemplo: `aleatorio_12MB.bin`, registro MFT **66**.

**a) El atributo `$DATA` no residente.** Su runlist es `22 00 0c 48 50`:

| Byte | Interpretación |
|---|---|
| `22` | Cabecera: longitud en 2 bytes, offset en 2 bytes |
| `00 0c` | Longitud = **3 072 clústeres** |
| `48 50` | Offset = 0x5048 = **20 552** (delta desde LCN 0, por ser el primer run) |
| `00` | Fin de la lista (*data run terminator*) |

**b) Formato de un *data run*.** Cada entrada se codifica así:

```
┌──────────┬───────────────────┬───────────────────────────┐
│ 1 byte   │ N bytes (low nib) │ M bytes (high nib)        │
│ cabecera │ longitud          │ desplazamiento (delta)     │
│ NL|NO    │ en clústeres      │ con signo, respecto al LCN │
└──────────┴───────────────────┴───────────────────────────┘
```

- El **nibble bajo** indica cuántos bytes ocupa la longitud.
- El **nibble alto** indica cuántos bytes ocupa el desplazamiento.
- El desplazamiento es **relativo al LCN del run anterior** y va **con signo** (complemento a dos): permite saltos hacia atrás.
- `0x00` termina la lista.

**c) VCN frente a LCN.**

| Concepto | Definición |
|---|---|
| **VCN** (Virtual Cluster Number) | Índice del clúster *dentro del archivo*: 0, 1, 2, … para los primeros 4 096 B, siguientes 4 096 B, etc. |
| **LCN** (Logical Cluster Number) | Índice del clúster *dentro del volumen*: posición física relativa al inicio del volumen. |

El runlist traduce VCN → LCN. En este archivo hay un solo run: VCN 0–3 071 → LCN 20 552, es decir, 3 072 clústeres contiguos.

**d) Cálculo de la posición de los datos:**

```
Offset = V + (LCN × C)
       = 1 048 576 + (20 552 × 4 096)
       = 1 048 576 + 84 180 992
       = 85 229 568 = 0x05148000
```

**e) Verificación hexadecimal** (`mis_evidencias/15_aleatorio_hex.txt`):

```
05148000: 4c8b 2f9e 0d3a ...   ← bytes aleatorios del archivo
```

El contenido es binario aleatorio, por lo que no es legible; la comprobación se hace por hash:

```
$ icat -o 2048 ntfs_lab.img 66 | sha256sum
e1825d66ff65c0509fe70da379260938473ee0b0ce5e47adf2d9d97628c68d3a
$ sha256sum archivos_prueba/aleatorio_12MB.bin
e1825d66ff65c0509fe70da379260938473ee0b0ce5e47adf2d9d97628c68d3a
```

![Figura 11 — `istat -o 2048 ntfs_lab.img 66` (`aleatorio_12MB.bin`): atributo `$DATA` no residente de 12 582 912 B y su runlist de 3 072 clústeres.](mis_evidencias/capturas/14-Archivo_grande.png)

![Figura 12 — `icat -o 2048 ntfs_lab.img 66 | sha256sum`: el hash del contenido extraído del clúster coincide con el del archivo original.](mis_evidencias/capturas/15-Hash.png)

**f) Un archivo con contenido reconocible.** `datos_patron_8MB.bin` (registro 67) se llenó con la cadena repetida `NTFS-LAB-CLUSTER-PATTERN-0123456789ABCDEF`. Su runlist `22 00 08 48 60` indica 2 048 clústeres desde el LCN 24 648, es decir:

```
Offset = 1 048 576 + 24 648 × 4 096 = 102 006 784 = 0x06148000
```

```
06148000: 4e54 4653 2d4c 4142 2d43 4c55 5354 4552  NTFS-LAB-CLUSTER
06148010: 2d50 4154 5445 524e 2d30 3132 3334 3536  -PATTERN-0123456
```

Aquí la evidencia es directa: el patrón aparece exactamente en la posición calculada, lo que demuestra que el LCN del runlist es la ubicación física del contenido.

![Figura 13 — `istat -o 2048 ntfs_lab.img 67` (`datos_patron_8MB.bin`): `$DATA` no residente de 8 388 608 B con runlist desde el LCN 24 648.](mis_evidencias/capturas/16-Archivo_patron.png)

![Figura 14 — Hash del contenido de `datos_patron_8MB.bin` extraído por `icat`, idéntico al archivo original.](mis_evidencias/capturas/17-Hash_archivo_patron.png)

### 7.8 El umbral residente / no residente

`umbral_residente.txt` tiene **2 000 bytes**. Su `$DATA` ya es no residente:

```
runlist: 21 01 4c 40   →   1 clúster desde el LCN 16 460
```

Es decir: 2 000 bytes de datos ocupan 4 096 bytes de disco (1 clúster), con un 48,8 % de espacio desaprovechado. El motivo es que un registro MFT de 1 024 B, tras descontar cabecera, `$STANDARD_INFORMATION`, `$FILE_NAME`, `$SECURITY_DESCRIPTOR` y las cabeceras de los atributos, deja menos de 800 B útiles: **no caben 2 000 B**.

Regla práctica (no absoluta): los datos menores de ~700 B suelen ser residentes; a partir de ahí NTFS los externaliza. **Siempre debe comprobarse el byte de no residente del atributo `$DATA`**, porque el umbral exacto depende de cuántos atributos tenga el registro.

![Figura 15 — `istat -o 2048 ntfs_lab.img 65` (`umbral_residente.txt`): con 2 000 B, el atributo `$DATA` ya es no residente.](mis_evidencias/capturas/12-Umbral_residencia.png)

![Figura 16 — Contenido de `umbral_residente.txt` extraído con `icat`: aunque ocupa un clúster completo, se lee correctamente.](mis_evidencias/capturas/13-No_residente.png)

### 7.9 El caso comprimido

`comprimidos/comprimido.txt` (registro MFT **138**, padre 137) tiene 100 000 bytes lógicos pero solo **12 288 bytes** asignados. Su `$DATA` es no residente, con la bandera `0x0001` (comprimido) y unidad de compresión `4` → **2^4 = 16 clústeres = 64 KiB**.

Runlist real: `31 02 48 90 00 01 0e 11 01 02 01 0f`

| Run | VCN | LCN | Longitud | Significado |
|---|---|---|---|---|
| 1 | 0–1 | 36 936 | 2 | Datos comprimidos reales |
| 2 | 2–15 | 36 936 | 14 | Relleno de la unidad de compresión (mismo LCN) |
| 3 | 16 | 36 938 | 1 | Datos del segundo bloque |
| 4 | 17–31 | 36 938 | 15 | Relleno del segundo bloque |

Esta es la firma típica de la compresión NTFS: el archivo se divide en **unidades de compresión** de 16 clústeres; dentro de cada unidad se guardan solo los clústeres necesarios y el resto se representa repitiendo el LCN (el espacio no se asigna de nuevo). Para leer el contenido hay que **descomprimir con LZNT1**; hacerlo a mano es inviable, pero TSK lo resuelve:

```
$ icat -o 2048 ntfs_lab.img 138 | sha256sum
5af063b5fef8a84848e9b7cbbb87fb58ab24c5240cb784bcde724fe90feda8ce
$ sha256sum archivos_prueba/comprimido.txt
5af063b5fef8a84848e9b7cbbb87fb58ab24c5240cb784bcde724fe90feda8ce
```

![Figura 17 — Volcado hexadecimal del `$DATA` comprimido del registro 138 en la posición calculada del primer run (LCN 36 936).](mis_evidencias/capturas/18-Hexadecimal_comprimido_txt.png)

![Figura 18 — `icat -o 2048 ntfs_lab.img 138`: TSK descomprime LZNT1 y devuelve el contenido legible de `comprimido.txt`.](mis_evidencias/capturas/19-Contenido_comprimido_txt.png)

**Sobre EFS:** el cifrado EFS no puede generarse desde Linux. Su análisis exige la clave privada del usuario; sin ella, el atributo `$DATA` aparece cifrado y ni `icat` ni el editor hexadecimal permiten leer el contenido. Se documenta como limitación en §9.7.

### 7.10 Resumen de los archivos analizados

| Archivo | MFT | Atributo `$DATA` | Tamaño lógico | Asignado | Posición del contenido |
|---|---|---|---|---|---|
| `LAB_NTFS.txt` | 64 | Residente | 114 B | — | Registro MFT en 0x114178 |
| `umbral_residente.txt` | 65 | No residente, 1 run | 2 000 B | 4 096 B | LCN 16 460 → 0x0414C000 |
| `aleatorio_12MB.bin` | 66 | No residente, 1 run | 12 582 912 B | 12 582 912 B | LCN 20 552 → 0x05148000 |
| `datos_patron_8MB.bin` | 67 | No residente, 1 run | 8 388 608 B | 8 388 608 B | LCN 24 648 → 0x06148000 |
| `comprimido.txt` | 138 | No residente + comprimido | 100 000 B | 12 288 B | LCN 36 936 → 0x09148000 |

---

## 8. Evidencias, tablas de valores y verificación

### 8.1 Inventario de evidencias

El conjunto **principal** está en `mis_evidencias/` (39 volcados/salidas + `bitacora.md` + 19 capturas en `capturas/`). Cada archivo se generó con el comando registrado en la bitácora.

| Bloque | Archivos | Contenido |
|---|---|---|
| Partición y arranque | `01`–`07` | `mmls`, MBR, VBR, copia del VBR, `fsstat`, `ntfsinfo`, firma `FILE` |
| Directorio raíz | `08`–`11` | `fls` raíz/recursivo e `istat`/hex del registro 5 (`$Root`) |
| Registro del archivo | `12`–`13` | `istat` y hex del registro 64 (`LAB_NTFS.txt`) |
| No residentes | `14`–`18` | `aleatorio_12MB.bin` y `datos_patron_8MB.bin`: runlists y datos |
| Compresión | `19`–`20` | `comprimido.txt`: runlist comprimido y registro 138 |
| Borrados / huérfanos | `21`–`22` | `fls -d` y registro huérfano 16 |
| Volumen sin MBR | `23` | VBR del volumen extraído (V = 0) |
| Experimento sobre copia | `24`–`31`, `37`–`39` | creación/borrado de `prueba_julian.txt`, hashes y bitmap |
| Hallazgos forenses | `32`–`36` | residuo en INDX, desglose, `$BadClus` y huérfanos |
| Bitácora | `bitacora.md` | comando → salida → interpretación de todo el laboratorio |
| Capturas | `capturas/01`–`19` | pantallazos referenciados en las figuras del documento |

La carpeta **`evidencias/`** conserva además los scripts y cálculos auxiliares que cita el informe:

| Archivo | Contenido |
|---|---|
| `04_tabla_vbr.md` | Tabla de campos del VBR con valores reales |
| `05_calculos.txt` | Cálculos de `OffsetMFT` y offsets de registro |
| `17_parse_mft_*.txt` | Recorrido de atributos con offsets |
| `18_hashes.md` | Hashes SHA-256 de imagen y archivos |
| `parse_mft.py` | Parser independiente de registros MFT |
| `analizar.py` | Script que regenera toda la evidencia |

### 8.2 Tabla consolidada del volumen

| Parámetro | Valor |
|---|---|
| Tamaño de la imagen | 536 870 912 B (512 MiB) |
| Partición | 1, tipo 0x07, sector 2048, 1 046 512 sectores |
| Volumen | `LAB_NTFS`, NTFS 3.1 |
| Bytes por sector | 512 |
| Sectores por clúster | 8 |
| Tamaño de clúster | 4 096 B |
| Total de sectores del volumen | 1 046 511 |
| LCN de `$MFT` | 4 |
| Offset de `$MFT` | 0x104000 |
| LCN de `$MFTMirr` | 65 406 (offset 0x1007E000) |
| Registros MFT | 0–139 |
| Tamaño de registro MFT | 1 024 B (0xF6) |
| Tamaño de registro de índice | 4 096 B |
| Número de serie | 0x0D8E2D287A1CF381 |
| Copia del VBR | 0x1FFFDE00 |

### 8.3 Integridad de la evidencia

| Archivo | Bytes | SHA-256 |
|---|---|---|
| `ntfs_lab.img` | 536 870 912 | `b4bdbef333d4afc5c759a33456c5ae3f7837d9cbf859bf0104f8f954543b346f` |
| `vol_ntfs_solo.img` | 535 814 144 | `38f6767a9a9b92cc80443ed594d2f93d4d78a1622e4ea27101bd372f2d7771fc` |
| `LAB_NTFS.txt` | 114 | `ffef8fb0bb1ef274fe4d94d462e99a02275a7ac7366f014fad7a825cdc5fbe6d` |
| `umbral_residente.txt` | 2 000 | `8f85049f4e4e11057249b8b383ca6ca569be2c79e6d9abab9572ae6a0fb9439a` |
| `aleatorio_12MB.bin` | 12 582 912 | `e1825d66ff65c0509fe70da379260938473ee0b0ce5e47adf2d9d97628c68d3a` |
| `datos_patron_8MB.bin` | 8 388 608 | `19be4a3f1f7b30c44397f909c99a219a6b615aa56271d6a52b093cfe019deaee` |
| `comprimido.txt` | 100 000 | `5af063b5fef8a84848e9b7cbbb87fb58ab24c5240cb784bcde724fe90feda8ce` |

![Figura 19 — Verificación de integridad: `sha256sum ntfs_lab.img` coincide con el hash registrado al inicio del laboratorio.](mis_evidencias/capturas/01-Verificación_imagen_trabajo.png)

### 8.4 Comandos de reproducción rápida

```bash
cd "Lab 01"

# Sector de arranque
xxd -s $((2048*512)) -l 512 ntfs_lab.img

# Registro raíz
istat -o 2048 ntfs_lab.img 5

# Registro del archivo de prueba
istat -o 2048 ntfs_lab.img 64
xxd -s 0x114000 -l 1024 ntfs_lab.img

# Contenido (residente / no residente / comprimido)
icat -o 2048 ntfs_lab.img 64
icat -o 2048 ntfs_lab.img 66 | sha256sum
icat -o 2048 ntfs_lab.img 138 | sha256sum

# Archivo con patrón visible en su posición física
xxd -s 0x06148000 -l 64 ntfs_lab.img

# Evidencia completa
python3 evidencias/analizar.py
```

---

## 9. Preguntas de análisis

### 9.1 ¿Por qué el MBR y el sector de arranque NTFS no son equivalentes?

Porque describen objetos distintos y viven en lugares distintos. El **MBR** está en el **sector 0 del disco** y solo contiene un cargador y una tabla de cuatro particiones (inicio, tamaño, tipo, flag de arranque). El **VBR** está en el **primer sector del volumen** y contiene el BPB con los parámetros del sistema de archivos: bytes por sector, sectores por clúster, total de sectores, **LCN de la MFT** y tamaño de los registros.

Evidencia: en esta imagen el MBR (sector 0) describe la partición que empieza en el sector 2048 y de tipo 0x07 (`mis_evidencias/01_mmls.txt`), pero **no contiene el LCN 4**; ese valor solo aparece en el VBR, en el offset 0x30 (`mis_evidencias/03_vbr_hex.txt`, `evidencias/04_tabla_vbr.md`). Sin el VBR no se puede localizar la MFT; sin el MBR no se sabe dónde comienza el volumen. Se necesitan ambos, y en ese orden.

### 9.2 ¿Qué información del sector de arranque permite calcular la ubicación inicial de la MFT?

Tres campos:

1. **Bytes por sector** (0x0B) = 512.
2. **Sectores por clúster** (0x0D) = 8 → clúster C = 4 096 B.
3. **LCN inicial de `$MFT`** (0x30) = 4.

Con ellos y el desplazamiento del volumen:

```
OffsetMFT = V + (LCN_MFT × C) = 1 048 576 + (4 × 4 096) = 1 064 960 = 0x104000
```

Comprobación directa: en 0x104000 hay una firma `FILE`, el registro 0 de la MFT.

### 9.3 ¿Por qué no es correcto buscar el directorio raíz de NTFS como si fuera una estructura fija de FAT16?

Porque en NTFS el directorio raíz **no es un área fija**: es el **registro MFT número 5**, un registro de 1 024 bytes con atributos (`$STANDARD_INFORMATION`, `$FILE_NAME`, `$INDEX_ROOT`, `$INDEX_ALLOCATION`, `$BITMAP`). Su contenido (la lista de nombres) es un índice en árbol B+ que puede repartirse en bloques `INDX` externos.

Evidencia: el `$INDEX_ROOT` del registro 5 tiene el flag `0x01`, que indica que el índice continúa en `$INDEX_ALLOCATION` (LCN 16 357 → 0x040E5000). Si se buscara "una entrada de directorio de 32 bytes tras la FAT" no se encontraría nada, porque esa estructura no existe en NTFS.

### 9.4 ¿Qué diferencias existen entre un atributo residente y uno no residente?

| | Residente | No residente |
|---|---|---|
| Dónde está el valor | Dentro del registro MFT | En clústeres del volumen |
| Qué guarda el atributo | Longitud y offset del valor | `runlist` (VCN→LCN), tamaños asignado/real/inicializado |
| Tamaño | Limitado por el espacio libre del registro (< ~800 B en la práctica) | Ilimitado (hasta el tamaño del volumen) |
| Ejemplo en este laboratorio | `LAB_NTFS.txt` (114 B) en 0x114178 | `aleatorio_12MB.bin` (3 072 clústeres desde LCN 20 552) |
| Efecto forense | El contenido puede recuperarse incluso si los clústeres se reutilizan | El contenido puede quedar inaccesible si los clústeres se reasignan |

La diferencia se ve en un solo byte: el byte de no residente del atributo (0x114168 en el registro 64 vale `00`; en el registro 66 vale `01`).

### 9.5 ¿Qué ocurriría si un archivo tiene tantos atributos que no caben en un único registro MFT?

NTFS crea un **registro de extensión** (registro MFT adicional) y enlaza ambos mediante el atributo **`$ATTRIBUTE_LIST` (0x20)**, que enumera qué atributos están en qué registro. El registro original se convierte en *registro base* y los demás guardan en su cabecera (0x20) la referencia al registro base.

Este laboratorio no llega a ese caso: el registro más cargado (`comprimido.txt`, 138) usa 448–504 de los 1 024 bytes. Pero la estructura está preparada: el campo 0x20 de la cabecera ("referencia al registro base") y el tipo 0x20 existen precisamente para eso. En análisis forense, ignorar `$ATTRIBUTE_LIST` es un error clásico: se pierden atributos que viven fuera del registro principal.

### 9.6 ¿Por qué un nombre de archivo visible en Windows no garantiza que sus datos estén almacenados de forma contigua?

Porque el nombre y el contenido viven en estructuras distintas y el contenido se asigna por clústeres según disponibilidad. El nombre está en `$FILE_NAME`/índice del directorio; el contenido, en `$DATA`, descrito por un `runlist` que admite **varios segmentos** con desplazamientos positivos o negativos.

En este volumen controlado el asignador colocó cada archivo en un solo *run* contiguo (por eso `aleatorio_12MB.bin` tiene un único run de 3 072 clústeres), pero eso es una circunstancia, no una garantía: en un disco con uso real, un archivo de 12 MiB puede estar repartido en decenas de *runs*. El propio formato lo demuestra: la compresión usa runs superpuestos (VCN 2–15 apuntando al mismo LCN), y el runlist está diseñado para saltos arbitrarios.

**Limitación reconocida de esta práctica:** se intentó provocar fragmentación llenando el volumen y liberando bloques alternos; el asignador de `ntfs-3g` reubicó el archivo en un bloque libre contiguo, por lo que la muestra final no quedó fragmentada. La interpretación de *runs* múltiples se documenta con el archivo comprimido (§7.9), que sí presenta cuatro entradas en su runlist.

### 9.7 ¿Qué limitaciones presenta el análisis manual cuando hay fragmentación, compresión, cifrado o atributos extendidos?

| Fenómeno | Efecto sobre el análisis manual | Cómo se manifiesta |
|---|---|---|
| **Fragmentación** | Hay que recorrer y concatenar varios *runs*; un cálculo único de offset es insuficiente | Runlist con varias entradas y VCN crecientes |
| **Compresión** | Los datos están en formato LZNT1 y las unidades de compresión incluyen relleno | Flag `0x0001` en `$DATA`, unidad de compresión 4, runs repetidos |
| **Cifrado (EFS)** | El contenido es criptográficamente inaccesible sin la clave del usuario | Flag de cifrado en `$DATA`; `icat` devuelve bytes sin sentido |
| **Atributos extendidos / `$ATTRIBUTE_LIST`** | Parte de los metadatos está en otros registros MFT | Tipo 0x20 presente; cabecera con registro base ≠ 0 |
| **Archivos dispersos (*sparse*)** | Clústeres no asignados que se leen como ceros | Runs con LCN 0 |
| **Nombres en diferentes *namespaces*** | Un mismo archivo puede tener varias entradas `$FILE_NAME` (DOS 8.3 y Win32) | Varios atributos 0x30 con distinto namespace |

A esto se suma que herramientas de alto nivel pueden **ocultar** estos detalles: `fls` muestra un nombre y un tamaño, pero no dice si el contenido está comprimido ni cuántos runs tiene. Por eso este laboratorio insiste en el hexadecimal y en `istat`/`parse_mft.py`.

---

## 10. Conclusiones

1. **NTFS es una base de datos de metadatos.** Todo objeto del volumen —incluido el directorio raíz— es un registro de la MFT con atributos tipados. Esto explica por qué no existe un "directorio raíz fijo" como en FAT.
2. **El VBR es la llave del volumen.** Con tres campos (bytes por sector, sectores por clúster y LCN de `$MFT`) se calcula la posición exacta de la tabla maestra, y esa posición se verificó hallando la firma `FILE` en 0x104000.
3. **Los cálculos coinciden con la evidencia.** `OffsetMFT = 1 064 960`, `Offsetregistro(64) = 1 130 496`, y en 0x114000 aparece el registro del archivo de prueba; en 0x114178 está su contenido literal.
4. **Residente y no residente no se distinguen por el tamaño "a ojo".** Se distinguen por el byte de no residente del atributo `$DATA`: `LAB_NTFS.txt` (114 B) es residente y `umbral_residente.txt` (2 000 B) ya es no residente.
5. **El runlist es la traducción VCN→LCN.** Interpretarlo correctamente permitió localizar el contenido de un archivo de 12 MiB en 0x05148000 y comprobarlo por hash y por patrón ASCII.
6. **La compresión cambia la geometría del archivo.** `comprimido.txt` ocupa 12 288 B para 100 000 B lógicos, con runs "repetidos" que representan el relleno de las unidades de compresión de 16 clústeres.
7. **La reproducibilidad es parte de la validez.** La imagen se generó con comandos documentados, los archivos con un script de semilla fija y la evidencia con `analizar.py`; los hashes permiten verificar que nada cambió.

---

## 11. Referencias

1. Microsoft Learn. *NTFS overview*. <https://learn.microsoft.com/windows-server/storage/file-server/ntfs-overview>
2. Microsoft Learn. *Master File Table (MFT)*. <https://learn.microsoft.com/windows/win32/fileio/master-file-table>
3. Microsoft Learn. *Boot Sector / NTFS Volume Layout*. Documentación del formato de volumen NTFS.
4. The Sleuth Kit. *Manual pages: `mmls`, `fsstat`, `fls`, `istat`, `icat`*. <https://www.sleuthkit.org/sleuthkit/man/>
5. Carrier, B. *File System Forensic Analysis*. Addison-Wesley, 2005. Capítulos 11–13 (NTFS).
6. Russon, R. y Fledel, Y. *NTFS Documentation*. Proyecto linux-ntfs. <https://flatcap.github.io/linux-ntfs/ntfs/>
7. ntfs-3g / Tuxera. *NTFS-3G User Guide* y documentación de `mkntfs`, `ntfsinfo`, `ntfscluster`.
8. NIST. *SP 800-86: Guide to Integrating Forensic Techniques into Incident Response*, 2006.
9. Autopsy / Sleuth Kit. *Autopsy User Documentation*. <https://www.autopsy.com/support/>

---

## 12. Anexos

### Anexo A — Script de generación de archivos

`archivos_prueba/generar_archivos.py` genera, con semilla fija, todos los archivos de prueba (incluido `LAB_NTFS.txt` con el contenido exacto del enunciado). Volver a ejecutarlo produce exactamente los mismos bytes y, por tanto, los mismos hashes.

### Anexo B — Script de análisis

`evidencias/analizar.py` lee el VBR, calcula los offsets, localiza los registros con `fls`/`istat`, extrae el contenido con `icat` y escribe todos los archivos de evidencia. Es idempotente y de solo lectura sobre la imagen.

### Anexo C — Parser independiente de registros MFT

`evidencias/parse_mft.py <N>` aplica los *fixups* de la Update Sequence Array y recorre los atributos mostrando tipo, longitud, flags, offsets y *runlist* decodificado. Se usó para contrastar los resultados de `istat` con una implementación propia.

### Anexo D — Cómo repetir el laboratorio con otro archivo

```bash
# 1. Elegir un archivo y obtener su número de registro MFT
fls -r -p -o 2048 ntfs_lab.img | grep -i "nombre_del_archivo"

# 2. Leer sus atributos y el runlist
istat -o 2048 ntfs_lab.img <N>

# 3. Calcular el offset del registro
python3 - <<'EOF'
V, C, R = 2048*512, 4096, 1024
LCN_MFT, N = 4, <N>
off_mft = V + LCN_MFT*C
print(hex(off_mft + N*R))
EOF

# 4. Volcar el registro
xxd -s $(( off_mft + N*R )) -l 1024 ntfs_lab.img

# 5. Si es no residente, calcular el offset de los datos
#    Offset = V + LCN * C   (con el primer LCN del runlist)
```

### Anexo E — Advertencia sobre el medio utilizado

El laboratorio se realizó sobre una **imagen de disco de 512 MiB**, no sobre una memoria USB física. La ruta `/media/sf_D_DRIVE` de la máquina virtual es una **carpeta compartida de VirtualBox** (sistema de archivos `vboxsf`), no un dispositivo de bloque: no se le puede aplicar una tabla de particiones, ni formatearla, ni extraerle una imagen con `dd`. Además contenía datos personales del equipo anfitrión, por lo que manipularla habría sido destructivo y no reproducible. La imagen empleada cumple el requisito del enunciado y permite repetir el análisis tantas veces como sea necesario sin riesgo.
