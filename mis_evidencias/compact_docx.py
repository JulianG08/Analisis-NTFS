#!/usr/bin/env python3
"""
Compacta el DOCX que genera pandoc para la ficha de sustentación.

- Cuerpo a 9 pt, sin espaciado extra
- Título/subtítulo/títulos de sección reducidos
- Página A4 con márgenes de 1,1–1,2 cm

Uso: python3 compact_docx.py entrada.docx salida.docx
"""
import re
import sys
import zipfile

SRC, DST = sys.argv[1], sys.argv[2]

with zipfile.ZipFile(SRC) as zin:
    styles = zin.read("word/styles.xml").decode("utf-8")
    document = zin.read("word/document.xml").decode("utf-8")
    others = [(i, zin.read(i.filename)) for i in zin.infolist()
              if i.filename not in ("word/styles.xml", "word/document.xml")]


def sub1(pattern, repl, text, what):
    new, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"no se pudo ajustar: {what}")
    return new


# --- cuerpo: 9 pt y sin aire entre párrafos -------------------------------
styles = sub1(r'(<w:docDefaults>.*?<w:sz w:val=")24("\s*/>)', r"\g<1>18\g<2>", styles, "sz docDefaults")
styles = sub1(r'(<w:docDefaults>.*?<w:szCs w:val=")24("\s*/>)', r"\g<1>18\g<2>", styles, "szCs docDefaults")
styles = sub1(r'(<w:pPrDefault>.*?<w:spacing w:after=")200(")', r"\g<1>40\g<2>", styles, "spacing docDefaults")

# --- título y subtítulo ---------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="Title".*?<w:sz w:val=")56("\s*/>)', r"\g<1>30\g<2>", styles, "Title sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Title".*?<w:szCs w:val=")56("\s*/>)', r"\g<1>30\g<2>", styles, "Title szCs")
styles = sub1(r'(<w:style [^>]*w:styleId="Title".*?<w:spacing w:after=")80("\s+w:line="240")', r"\g<1>20\g<2>", styles, "Title spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="Subtitle".*?<w:sz w:val=")28("\s*/>)', r"\g<1>17\g<2>", styles, "Subtitle sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Subtitle".*?<w:szCs w:val=")28("\s*/>)', r"\g<1>17\g<2>", styles, "Subtitle szCs")

# --- títulos de sección ---------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:spacing w:after=")80("\s+w:before=")360(")', r"\g<1>30\g<2>130\g<3>", styles, "Heading1 spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:sz w:val=")40("\s*/>)', r"\g<1>24\g<2>", styles, "Heading1 sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:szCs w:val=")40("\s*/>)', r"\g<1>24\g<2>", styles, "Heading1 szCs")

# --- párrafos y celdas ----------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="BodyText".*?<w:spacing w:after=")180("\s+w:before=")180(")', r"\g<1>30\g<2>20\g<3>", styles, "BodyText spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="Compact".*?<w:spacing w:after=")36("\s+w:before=")36(")', r"\g<1>10\g<2>10\g<3>", styles, "Compact spacing")

# --- código: 8 pt ---------------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="VerbatimChar".*?<w:sz w:val=")22("\s*/>)', r"\g<1>16\g<2>", styles, "VerbatimChar sz")

# --- anchos de tabla ------------------------------------------------------
# Suma = 10706 twips (A4 menos márgenes). Una lista por tabla, en orden.
WIDTHS = [
    [830, 2540, 1180, 6156],   # 1 mapa de registros: Reg | Objeto | Offset | Datos
    [2500, 2750, 2500, 2956],  # 2 números de oro
    [600, 1700, 3100, 5306],   # 3 runlists
    [2700, 3900, 4106],        # 4 experimento
    [3050, 7656],              # 5 preguntas rápidas
    [3100, 7606],              # 6 comandos
]


def fix_table(tbl, widths):
    """Fija el ancho real de la tabla y reparte las columnas."""
    total = sum(widths)
    tbl = re.sub(r'<w:tblW[^/]*/>',
                 f'<w:tblW w:type="dxa" w:w="{total}" />', tbl, count=1)
    cols = iter(widths)
    tbl = re.sub(r'<w:gridCol w:w="\d+"\s*/>',
                 lambda m: '<w:gridCol w:w="%d" />' % next(cols, widths[-1]),
                 tbl)
    return tbl


def walk_tables(doc):
    """Aplica WIDTHS a cada <w:tbl> del documento, en orden."""
    idx = [0]

    def repl(m):
        i = idx[0]
        if i >= len(WIDTHS):
            raise SystemExit("hay más tablas que anchos definidos")
        idx[0] += 1
        return fix_table(m.group(0), WIDTHS[i])

    doc = re.sub(r"<w:tbl>.*?</w:tbl>", repl, doc, flags=re.S)
    if idx[0] != len(WIDTHS):
        raise SystemExit(f"tablas encontradas: {idx[0]}, anchos: {len(WIDTHS)}")
    return doc


document = walk_tables(document)

# --- A4 y márgenes --------------------------------------------------------
page = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="680" w:right="600" w:bottom="680" w:left="600" '
        'w:header="300" w:footer="300" w:gutter="0"/>')
document = sub1(r"<w:sectPr>", page, document, "sectPr")

with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
    zout.writestr("word/styles.xml", styles)
    zout.writestr("word/document.xml", document)
    for name, data in others:
        zout.writestr(name, data)

print("compactado:", DST)
