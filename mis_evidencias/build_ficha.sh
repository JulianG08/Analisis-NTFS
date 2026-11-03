#!/usr/bin/env bash
# Genera Ficha_Sustentacion_Lab01.pdf a partir de ficha_sustentacion.md
#   pandoc (md -> docx)  ->  compact_docx.py (9 pt, A4)  ->  LibreOffice (docx -> pdf)
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=/tmp/opencode/ficha
mkdir -p "$TMP"

pandoc mis_evidencias/ficha_sustentacion.md -o "$TMP/raw.docx" --from markdown
python3 mis_evidencias/compact_docx.py "$TMP/raw.docx" "$TMP/ficha.docx"
rm -f "$TMP/ficha.pdf" Ficha_Sustentacion_Lab01.pdf
libreoffice --headless --convert-to pdf --outdir "$TMP" "$TMP/ficha.docx" >/dev/null 2>&1
cp "$TMP/ficha.pdf" Ficha_Sustentacion_Lab01.pdf

pdfinfo Ficha_Sustentacion_Lab01.pdf | grep -E "^Pages|^Page size"
echo "OK -> Ficha_Sustentacion_Lab01.pdf"
