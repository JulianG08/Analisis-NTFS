---
title: "Guion de sustentación · Laboratorio 1 NTFS"
subtitle: "Alejandro Arbelaez Hoyos · Julián David Guarnizo Castrillón · Arquitectura del Computador · UCO · 28 de octubre de 2026"
---

# 1 · Antes de empezar

- Abrir `Visualizador_NTFS.html` a pantalla completa (doble clic; funciona sin servidor ni internet).
- Dejar dos ventanas listas: el PPT y el navegador, para alternar con Alt+Tab.
- Tener impresa la ficha de repaso (2 caras A4): es la red de seguridad para los números.
- Probar una vez cada demo: mapa del disco, mapa de la MFT, pasos, VBR, registro 64 y calculadora.
- Si falla el proyector, se sigue igual con la ficha y el PDF, sin pausar.

**Reparto:** Alejandro abre (bloques 1–3), Julián lleva la parte técnica central (bloques 4–6), los dos cubren los casos especiales, el experimento y el cierre.

# 2 · Reparto y cronómetro

| Bloque | Tiempo | Diapositivas | Quién | Demo en pantalla |
|:-------------------|:---------|:---------------|:--------------|:----------------------------------------------|
| 1 · Idea y contexto | 0:00–1:10 | 1 · 2 · 3 | Alejandro | — |
| 2 · Montaje y MBR | 1:10–2:20 | 4 · 5 | Julián | Sección 1 · mapa del disco |
| 3 · VBR | 2:20–3:10 | 6 | Julián | Sección 3 · VBR en hexadecimal |
| 4 · Raíz y cálculo | 3:10–4:30 | 7 · 8 | Alejandro | Sección 2 · pasos |
| 5 · Residente | 4:30–5:30 | 9 | Julián | Sección 4 · registro 64 |
| 6 · No residente | 5:30–6:30 | 10 | Julián | Sección 5 · calculadora |
| 7 · Casos especiales | 6:30–7:20 | 11 | Ambos | Sección 1½ · mapa de la MFT |
| 8 · Experimento | 7:20–8:30 | 12 | Alejandro | Sección 1½ · registro 139 |
| 9 · Cierre | 8:30–9:20 | 13 | Ambos | — |
| Preguntas | 9:20–10:00 | — | Ambos | — |

# 3 · Números de oro

| Dato | Valor |
|:------------------------------------|:---------------------------------------------------------------|
| V (inicio del volumen) | sector 2048 × 512 = **0x100000** (1 048 576) |
| Clúster / registro MFT | 4 096 B / 1 024 B |
| Inicio de la MFT | LCN 4 → **0x104000** |
| Registro 64 | 0x104000 + 64 × 1024 = **0x114000** |
| Contenido residente de `LAB_NTFS.txt` | **0x114178** (114 B, 0 clústeres) |
| `aleatorio_12MB.bin` | LCN 20 552 → **0x5148000** |
| `datos_patron_8MB.bin` | LCN 24 648 → **0x6148000** |
| Índice de la raíz (INDX) | LCN 16 357 → **0x040E5000** |
| Copia de la MFT | LCN 65 406 → **0x1007E000** |
| VBR de respaldo | sector 1 048 559 → **0x1FFFDE00** |
| Clústeres | 130 813 totales · 124 887 libres |
| SHA-256 de la imagen | `b4bdbef3…346f` (inicial = final) |

# 4 · Guion, bloque por bloque

## Bloque 1 · 0:00–1:10 · Diapositivas 1, 2 y 3

**Qué se ve:** portada, la cadena MBR → VBR → MFT → Registro → Datos, y la comparación FAT / NTFS.

**D1 (0:00–0:20).**

> Somos Alejandro Arbelaez y Julián David Guarnizo. Nuestra idea en una frase: con cuatro datos del sector de arranque calculamos dónde está cualquier archivo de este volumen, y lo demostramos con bytes reales, no con herramientas.

**D2 (0:20–0:40).** Señalar la cadena de la diapositiva.

> Es una cadena: cada eslabón entrega el dato que necesita el siguiente. Todo sale de algo que NTFS deja leer: no inventamos ningún número.

**D3 (0:40–1:10).**

> En FAT la carpeta raíz es una zona fija del disco y los directorios solo dicen «la caja empieza aquí». En NTFS todo es un archivo con metadatos: la raíz es el registro 5, la MFT es un catálogo de fichas de 1 024 bytes, y cada atributo viene tipado con su propio código.

**Frase para recordar:** *FAT guarda direcciones; NTFS guarda fichas con descripciones.*

## Bloque 2 · 1:10–2:20 · Diapositivas 4 y 5

**Demo:** sección **1 · Mapa del disco** → clic en el bloque morado «VBR / arranque».

> Esto no está a escala, pero sí el orden: en el sector 0 está el MBR, luego 1 MiB sin asignar, y la partición empieza en el sector 2048. La imagen completa son 512 MiB; el volumen NTFS ocupa 511.

> El SHA-256 de la imagen es `b4bdbef3…346f`, idéntico antes y después de todo el laboratorio. Trabajamos siempre sobre copias.

**D5 (2:20).**

> El MBR describe el disco; el VBR describe el volumen. Del MBR solo necesitamos un número: el sector de inicio, 2048. Con eso ya tenemos V = 2048 × 512 = 1 048 576 = 0x100000. A partir de ahí, todo se mide desde V.

## Bloque 3 · 2:20–3:10 · Diapositiva 6

**Demo:** sección **3 · El sector de arranque (VBR) en hexadecimal**. Clic en el campo verde, luego el celeste y luego el rojo.

> Estos son los primeros 96 bytes reales del volumen. En el verde, `00 02`: son 512, pero se lee al revés —little-endian: primero el byte menos significativo—, o sea 0x0200 = 512.

> En el celeste, un `08`: 8 sectores por clúster, es decir 4 096 bytes por clúster. Y en el offset 0x30, un `04`: la MFT empieza en el clúster 4.

> El byte 0x40 dice `f6`: es −10 con signo, y la regla es 2 elevado al valor absoluto, así que 2¹⁰ = 1 024 bytes por registro.

> **Si preguntan por la copia del VBR:** está al final de la partición, en el sector 1 048 559 = 0x1FFFDE00, con la misma firma 55 AA y los mismos números.

## Bloque 4 · 3:10–4:30 · Diapositivas 7 y 8

**D7 (3:10).**

> En NTFS la raíz no es una zona fija: es el registro 5, con un índice pequeño dentro del registro y un índice grande en clústeres, en 0x040E5000. La carpeta `muchos/`, con 60 archivos, ocupa tres bloques INDX.

**Demo:** sección **2 · Cómo se encuentra un archivo, paso a paso** → botones 1, 3 y 4.

> Paso 1: del MBR saco el sector 2048 y con él V. Paso 2: del VBR saco 4 096 y el LCN 4. Paso 3: la MFT está en 1 048 576 + 4 × 4 096 = 0x104000. Y con eso ya puedo ir a cualquier ficha: la de `LAB_NTFS.txt` es la 64, o sea 0x114000.

> Comprobación: en esas dos direcciones se leen los bytes 46 49 4C 45, que en ASCII son «FILE», la firma de todo registro válido. Eso es lo que convierte un cálculo en un cálculo comprobado.

## Bloque 5 · 4:30–5:30 · Diapositiva 9

**Demo:** sección **4 · La ficha de LAB_NTFS.txt** → clic en el bloque rosa (`$DATA`) y luego en el verde (el contenido).

> Los atributos van en cadena desde el byte 0x38: fechas, nombre, permisos y el `$DATA`.

> El atributo `$DATA` tiene un byte en su cabecera: 00 significa residente y 01 no residente. Ahí se decide todo, no por el tamaño del archivo.

> Aquí el byte es 00, así que los 114 bytes están dentro de la propia ficha, en 0x114178, y no ocupa ningún clúster. Por eso `icat` devuelve ese texto y su SHA-256 coincide con el del archivo original.

## Bloque 6 · 5:30–6:30 · Diapositiva 10

**Demo:** sección **5 · Residente vs. no residente**. En la calculadora, escribir 20552 y después 24648.

> En un archivo grande el byte es 01 y la ficha ya no guarda los datos: guarda una runlist, que son las direcciones de las cajas.

> Cómo se lee `22 00 0C 48 50`: el primer byte dice «cuento 2 bytes de longitud y 2 de desplazamiento»; `00 0C` son 3 072 clústeres; `48 50` es 0x5048, el desplazamiento desde el run anterior. Con V + LCN × 4 096 llegamos a 0x5148000.

> Verificación con patrón: el LCN 24 648 cae en 0x6148000 y ahí se lee `NTFS-LAB-CLUSTER-PATTERN`. Ver un patrón legible prueba que el dato no está fragmentado.

## Bloque 7 · 6:30–7:20 · Diapositiva 11

**Demo:** sección **1½ · Mapa de la MFT**. Cuatro acciones, en este orden:

1. Clic en **65** → umbral residente.
2. Clic en **138** → comprimido.
3. Clic en **8** → `$BadClus`.
4. Escribir `comprimidos` en el buscador.

> Este mapa lo generamos leyendo los 140 registros con un parser propio en Python y verificando cada uno con `istat`.

> El 65 es el umbral: 2 000 bytes ya no caben en 1 024, así que pasa a no residente y ocupa un clúster de 4 096, o sea el 48,8 %.

> El 138 está comprimido: 100 000 bytes ocupan 12 288 en disco. Su runlist mezcla clústeres reales con huecos —disperso por 14, clúster, disperso por 15—: la compresión LZNT1 deja zonas que NTFS no ocupa.

> El 8 es `$BadClus`: declara 535 810 048 bytes, todo el volumen, pero con un único run disperso. Tamaño lógico enorme, cero clústeres reales y cero sectores malos.

**Trampa que conviene aclarar uno mismo:**

> Ojo con dos tramos que parecen iguales: 12–15 están en uso pero sin nombre, y por eso no salen en `fls`; 16–23 están libres y sin nombre, y TSK los recupera como `$OrphanFiles`. La diferencia está en los flags.

## Bloque 8 · 7:20–8:30 · Diapositiva 12

**Demo:** en el mismo mapa, clic en **139** (la casilla con borde punteado); después escribir `ficha_30` en el buscador.

> En la imagen original la MFT llega al registro 138. En la copia creamos `prueba_julian.txt` y nació el registro 139. Después lo borramos y sigue ahí: la secuencia pasó de 1 a 2, los enlaces de 1 a 0, los flags de 0x0001 a 0x0000, y el nombre y el contenido están intactos.

> Borrar en NTFS es marcar, no sobrescribir. Además, la MFT creció de 142 336 a 143 360 bytes, un solo registro, sin pedir un clúster nuevo, y el `$Bitmap` no se movió de 124 887 libres: cabía en el último clúster ya asignado.

## Bloque 9 · 8:30–9:20 · Diapositiva 13

> Cuatro conclusiones. Uno: NTFS es una base de datos de metadatos. Dos: el VBR es la llave del volumen, y con cuatro datos basta. Tres: residente o no residente se decide en un solo byte. Cuatro: cálculo, bytes y hash coinciden; la imagen original tiene el mismo SHA-256 al inicio y al final.

> Si quieren comprobarlo, los comandos están en la sección 6 del visualizador: `mmls`, `fsstat`, `xxd -s 0x114000` e `icat -o 2048 ntfs_lab.img 64`.

## Frases de emergencia

- Si me pierdo, vuelvo a la cadena: MBR → VBR → MFT → registro → datos.
- Ese número está comprobado y anotado en la ficha: página 2.
- No lo calculé a ojo: lo verifiqué con `istat` y con el hash.
- Si quieren, lo vemos ahora mismo en el visualizador.
- Antes de inventar un dato: «eso no lo medimos en este laboratorio».

```{=openxml}
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
```

# 5 · Preguntas de reserva

| Si preguntan | Respuesta en una línea |
|:--------------------------------------|:---------------------------------------------------------------|
| ¿MBR es lo mismo que VBR? | No: el MBR describe el disco; el VBR, el volumen (clúster, registro y LCN de la MFT). |
| ¿Cómo sabes dónde está la MFT? | `0x0B` = 512, `0x0D` = 8 y `0x30` = 4 → 0x100000 + 4 × 4096 = 0x104000; ahí se lee «FILE». |
| ¿La raíz es una zona fija? | No: es el registro 5, con `$INDEX_ROOT` y `$INDEX_ALLOCATION`. |
| ¿Residente o no residente? | Un byte del atributo `$DATA`: 00 dentro de la ficha, 01 con runlist. |
| ¿Y si los atributos no caben? | `$ATTRIBUTE_LIST` con registros de extensión; aquí no hizo falta: el más cargado usa 448 B. |
| ¿El nombre indica dónde están los datos? | No: el nombre vive en el índice y en `$FILE_NAME`; los datos, en `$DATA`, repartidos en N runs. |
| ¿Qué límites tiene el análisis manual? | Fragmentación, compresión LZNT1, cifrado EFS y `$ATTRIBUTE_LIST`; ahí se usan `istat` e `icat`. |
| ¿Cómo sabes que la evidencia es confiable? | SHA-256 inicial igual al final, escrituras solo en la copia y cada `icat` coincide con su archivo. |

# 6 · Tres detalles que no se deben decir mal

1. **Registro 138:** usa 448 de 1 024 bytes. No decir «unos 500».
2. **VBR de respaldo:** `0x1FFFDE00` (sector 1 048 559), no 0x1FFFDC00.
3. **Registro 139:** no existe en `ntfs_lab.img`; existe solo en la copia después del experimento. Decirlo antes de que lo pregunten da credibilidad.

# 7 · Plan B

- Si el tiempo aprieta: saltar la diapositiva 7; se ganan unos 40 segundos.
- Si sobra tiempo: buscar `ficha_07` en el mapa y comparar con `istat`.
- Si el navegador falla: seguir con el PPT y la ficha; los números están todos ahí.
- Si una demo no carga: describirla en una frase y continuar; nunca quedarse esperando la pantalla.

# 8 · Checklist de demos antes de entrar

| Sección del visualizador | Acción | Qué debe verse |
|:------------------------------------|:-------------------------------|:---------------------------------------------------------|
| 1 · Mapa del disco | Clic en «VBR / arranque» | 512 B/sector · 8 sectores/clúster · MFT en clúster 4 |
| 1½ · Mapa de la MFT | Clic en 65, 138 y 8 | Umbral no residente · comprimido con huecos · `$BadClus` disperso |
| 2 · Pasos | Botones 1, 3 y 4 | V = 0x100000 · MFT = 0x104000 · registro 64 = 0x114000 |
| 3 · VBR en hexadecimal | Clic en verde, celeste y rojo | 512 · 4 096 · LCN 4 |
| 4 · Registro 64 | Clic en `$DATA` y en el contenido | Byte 00 → residente · texto en 0x114178 |
| 5 · Calculadora | Escribir 20552 y 24648 | 0x5148000 y 0x6148000 |
| Buscador del mapa | Escribir `ficha_30` | 1 registro, seleccionado en el mapa |
