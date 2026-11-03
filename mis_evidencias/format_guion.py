#!/usr/bin/env python3
"""
Formatea el DOCX del guion de sustentación generado por pandoc.

- A4 con márgenes de 2 cm
- Cuerpo a 11 pt, interlineado cómodo para leer en voz alta
- Títulos y citas reducidos
- Tablas con anchos reales (pandoc los calcula para carta y no caben en A4)

Uso: python3 format_guion.py entrada.docx salida.docx
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


# --- cuerpo ---------------------------------------------------------------
styles = sub1(r'(<w:docDefaults>.*?<w:sz w:val=")24("\s*/>)', r"\g<1>22\g<2>", styles, "sz docDefaults")
styles = sub1(r'(<w:docDefaults>.*?<w:szCs w:val=")24("\s*/>)', r"\g<1>22\g<2>", styles, "szCs docDefaults")
styles = sub1(r'(<w:pPrDefault>.*?<w:spacing w:after=")200(")', r"\g<1>120\g<2>", styles, "spacing docDefaults")

# --- título y subtítulo ---------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="Title".*?<w:sz w:val=")56("\s*/>)', r"\g<1>34\g<2>", styles, "Title sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Title".*?<w:szCs w:val=")56("\s*/>)', r"\g<1>34\g<2>", styles, "Title szCs")
styles = sub1(r'(<w:style [^>]*w:styleId="Subtitle".*?<w:sz w:val=")28("\s*/>)', r"\g<1>22\g<2>", styles, "Subtitle sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Subtitle".*?<w:szCs w:val=")28("\s*/>)', r"\g<1>22\g<2>", styles, "Subtitle szCs")

# --- títulos de sección ---------------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:spacing w:after=")80("\s+w:before=")360(")',
              r"\g<1>90\g<2>300\g<3>", styles, "Heading1 spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:sz w:val=")40("\s*/>)', r"\g<1>28\g<2>", styles, "Heading1 sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading1".*?<w:szCs w:val=")40("\s*/>)', r"\g<1>28\g<2>", styles, "Heading1 szCs")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading2".*?<w:spacing w:after=")80("\s+w:before=")160(")',
              r"\g<1>80\g<2>260\g<3>", styles, "Heading2 spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading2".*?<w:sz w:val=")32("\s*/>)', r"\g<1>24\g<2>", styles, "Heading2 sz")
styles = sub1(r'(<w:style [^>]*w:styleId="Heading2".*?<w:szCs w:val=")32("\s*/>)', r"\g<1>24\g<2>", styles, "Heading2 szCs")

# --- párrafos, citas y celdas --------------------------------------------
styles = sub1(r'(<w:style [^>]*w:styleId="BodyText".*?<w:spacing w:after=")180("\s+w:before=")180(")',
              r"\g<1>90\g<2>40\g<3>", styles, "BodyText spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="BlockText".*?<w:spacing w:after=")100("\s+w:before=")100(")',
              r"\g<1>70\g<2>70\g<3>", styles, "BlockText spacing")
styles = sub1(r'(<w:style [^>]*w:styleId="BlockText".*?w:left=")480("\s+w:right=")480(")',
              r"\g<1>360\g<2>180\g<3>", styles, "BlockText indent")

# cita: barra azul a la izquierda para ver de un golpe qué se dice en voz alta
styles = sub1(
    r'(<w:style [^>]*w:styleId="BlockText".*?<w:pPr>)',
    r'\g<1><w:pBdr><w:left w:val="single" w:sz="12" w:space="10" w:color="38BDF8"/></w:pBdr>',
    styles, "BlockText border")

# celdas de tabla: 10 pt y sin aire
styles = sub1(
    r'(<w:style [^>]*w:styleId="Compact".*?<w:spacing w:after=")36("\s+w:before=")36("\s*/>)',
    r'\g<1>16\g<2>16\g<3><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>',
    styles, "Compact sz")

# --- A4 con márgenes de 2 cm ---------------------------------------------
page = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="567" w:footer="567" w:gutter="0"/>')
document = sub1(r"<w:sectPr>", page, document, "sectPr")

# --- anchos de tabla (suma = 9638 twips = A4 menos 2+2 cm) ---------------
USABLE = 11906 - 2 * 1134
WIDTHS = [
    [2200, 1250, 1400, 1250, 3538],   # 1 reparto y cronómetro
    [4300, 5338],                    # 2 números de oro
    [3600, 6038],                    # 3 preguntas de reserva
    [2500, 3100, 4038],              # 4 checklist de demos
]


def fix_table(tbl, widths):
    total = sum(widths)
    tbl = re.sub(r'<w:tblW[^/]*/>', f'<w:tblW w:type="dxa" w:w="{total}" />', tbl, count=1)
    cols = iter(widths)
    return re.sub(r'<w:gridCol w:w="\d+"\s*/>',
                  lambda m: '<w:gridCol w:w="%d" />' % next(cols, widths[-1]), tbl)


idx = [0]


def walk(m):
    i = idx[0]
    if i >= len(WIDTHS):
        raise SystemExit("hay más tablas que anchos definidos")
    idx[0] += 1
    return fix_table(m.group(0), WIDTHS[i])


document = re.sub(r"<w:tbl>.*?</w:tbl>", walk, document, flags=re.S)
if idx[0] != len(WIDTHS):
    raise SystemExit(f"tablas encontradas: {idx[0]}, anchos: {len(WIDTHS)}")
if sum(WIDTHS[0]) != USABLE:
    raise SystemExit("los anchos no suman el ancho útil de A4")

# ninguna fila de tabla se parte entre páginas
document = re.sub(r"<w:trPr>", "<w:trPr><w:cantSplit/>", document)
document = re.sub(r"<w:tr>", "<w:tr><w:trPr><w:cantSplit/></w:trPr>", document)

with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
    zout.writestr("word/styles.xml", styles)
    zout.writestr("word/document.xml", document)
    for name, data in others:
        zout.writestr(name, data)

print("formateado:", DST)
