#!/usr/bin/env bash
# Genera Guion_Sustentacion_Lab01.docx a partir de guion_sustentacion.md
#   pandoc (md -> docx)  ->  format_guion.py (A4, 11 pt, tablas)  ->  DOCX final
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=/tmp/opencode/guion
mkdir -p "$TMP"

pandoc mis_evidencias/guion_sustentacion.md -o "$TMP/raw.docx" --from markdown
python3 mis_evidencias/format_guion.py "$TMP/raw.docx" Guion_Sustentacion_Lab01.docx

# comprobación rápida: páginas y tamaño A4 vía PDF temporal
libreoffice --headless --convert-to pdf --outdir "$TMP" Guion_Sustentacion_Lab01.docx >/dev/null 2>&1
pdfinfo "$TMP/Guion_Sustentacion_Lab01.pdf" | grep -E "^Pages|^Page size"
echo "OK -> Guion_Sustentacion_Lab01.docx"
