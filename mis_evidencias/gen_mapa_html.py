#!/usr/bin/env python3
"""
Inserta la sección «1½ · Mapa de la MFT» en Visualizador_NTFS.html.

Toma los datos reales de mapa_registros.json y los embebe en el <script>
(sin fetch: el visualizador se abre con doble clic, file://).

Idempotente: los tres bloques van entre marcadores MAPA-MFT y se reemplazan.

Uso: python3 gen_mapa_html.py [mapa_registros.json] [Visualizador_NTFS.html]
"""
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "mapa_registros.json"
HTML = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else BASE.parent / "Visualizador_NTFS.html"

data = json.loads(SRC.read_text(encoding="utf-8"))


def compact(r):
    """Reduce cada registro a lo que el visualizador necesita."""
    item = {"n": r["n"], "nm": r.get("name") or "", "k": r["kind"]}
    if r.get("exists"):
        item["f"] = r["flags"]
        item["l"] = r["links"]
        item["s"] = r["seq"]
        item["u"] = r["used"]
    d = r.get("data")
    if d:
        dd = {"sz": d.get("size", 0), "res": bool(d.get("resident"))}
        if d.get("resident"):
            dd["off"] = d.get("value_offset_hex")
        else:
            dd["off"] = d.get("data_offset_hex")
            dd["runs"] = d.get("runs") or []
            if d.get("sparse"):
                dd["sp"] = True
            if d.get("compressed"):
                dd["cp"] = True
        item["d"] = dd
    return item


records = [compact(r) for r in data["records"]]
blob = json.dumps(records, ensure_ascii=False, separators=(",", ":"))

CSS = """
  /* MAPA-MFT-CSS:INICIO */
  .mftbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:4px 0 8px; }
  .mftbar input { width:250px; }
  .mftgrid { display:grid; grid-template-columns:repeat(20,minmax(0,1fr)); gap:4px; margin:10px 0 4px; }
  @media(max-width:760px){ .mftgrid { grid-template-columns:repeat(10,minmax(0,1fr)); } }
  .mcell { background:#475569; border-radius:5px; height:30px; display:flex; align-items:center;
           justify-content:center; font-size:.72rem; font-weight:600; color:#0f172a; cursor:pointer;
           border:1px solid transparent; transition:filter .12s; }
  .mcell:hover { filter:brightness(1.25); }
  .mcell.sel { outline:3px solid #fff; outline-offset:-3px; }
  .mcell.dim { opacity:.18; }
  .mcell.solo { border:2px dashed #fff; }
  /* MAPA-MFT-CSS:FIN */
"""

HTML_BLOCK = """
<!-- MAPA-MFT:INICIO -->
<section>
  <h2>1½ · Mapa de la MFT: los 140 registros</h2>
  <p class="mut">Cada casilla es un registro de 1 024 bytes; su offset es <code>0x104000 + n×1024</code>.
  Haz clic en una casilla para ver su ficha completa, o escribe un nombre para localizarlo.</p>
  <div class="mftbar">
    <input id="mftBuscar" type="search" placeholder="buscar: ficha_07 · comprimido · $MFT">
    <span class="mut" id="mftCuenta"></span>
  </div>
  <div class="legend" id="mftLeyenda"></div>
  <div class="mftgrid" id="mftGrid"></div>
  <div class="info" id="mftDetalle">Haz clic en un registro del mapa.</div>
</section>
<!-- MAPA-MFT:FIN -->
"""

JS = """
/* MAPA-MFT-JS:INICIO */
/* ---------- 1½. Mapa de la MFT (datos reales embebidos) ---------- */
const MFT = __DATA__;
const MFT_COLOR = {system:'#34d399', reserved:'#fbbf24', orphan:'#fb923c',
                   free:'#475569', dir:'#22d3ee', file:'#60a5fa'};
const MFT_ETIQ  = {system:'metadato del sistema', reserved:'reservado, sin nombre',
                   orphan:'huérfano (libre, sin nombre)', free:'libre',
                   dir:'directorio', file:'archivo'};

const mftGrid = document.getElementById('mftGrid');
const mftDet  = document.getElementById('mftDetalle');
const mftCnt  = document.getElementById('mftCuenta');
const mftBus  = document.getElementById('mftBuscar');

const hex = n => '0x' + n.toString(16).toUpperCase();
const hex4 = n => '0x' + n.toString(16).toUpperCase().padStart(4, '0');
const num = n => n.toLocaleString('es');

function mftDatos(r){
  const d = r.d;
  if (!d) return '<span class="mut">Sin <code>$DATA</code>: registro de metadatos o directorio ' +
                 '(el contenido está en el índice o repartido en otros atributos).</span>';
  if (d.res && d.sz === 0)
    return '<code>$DATA</code> <b>vacío</b> (0 B): este registro no guarda contenido propio.';
  if (d.res) return '<b>Residente</b> · ' + num(d.sz) + ' B dentro del propio registro, en <code>' +
                    d.off + '</code> · 0 clústeres.';
  const runs = d.runs.map(x => x[0] === null
      ? 'disperso ×' + num(x[1])
      : 'LCN ' + num(x[0]) + ' + ' + num(x[1])).join(' · ');
  let extra = '';
  if (d.sp) extra = ' <span class="mut">(run disperso: no ocupa espacio real)</span>';
  if (d.cp) extra = ' <span class="mut">(comprimido LZNT1: 2 clústeres de datos + relleno disperso)</span>';
  return '<b>No residente</b> · ' + num(d.sz) + ' B · runlist: <code>' + runs + '</code>' + extra +
         (d.off ? '<br>Datos en <code>' + d.off + '</code>' : '');
}

function mftLinea(r){
  if (r.n === 139)
    return '<b>Registro 139 · no existe en <code>ntfs_lab.img</code></b> <span class="mut">(solo en la copia de trabajo)</span><br>' +
           'En la imagen original la MFT tiene 139 registros (0–138). Al crear <code>prueba_julian.txt</code> ' +
           'apareció este registro y, al borrarlo, quedó <b>libre</b>: sequence 1→2, links 1→0, flags <code>0x0001</code>→' +
           '<code>0x0000</code>.<br>En la copia solo-volumen (V = 0) está en <code>0x4000 + 139×1024 = 0x26C00</code>.';
  let h = '<b>Registro ' + r.n + (r.nm ? ' · ' + r.nm : '') + '</b> ' +
          '<span class="mut">(' + MFT_ETIQ[r.k] + ')</span><br>';
  h += 'Offset: <code>0x104000 + ' + r.n + '×1024 = ' + hex(0x104000 + r.n * 1024) + '</code>';
  if (r.u !== undefined)
    h += ' &nbsp;·&nbsp; bytes usados: <b>' + num(r.u) + '</b> de 1 024' +
         '<br>flags <code>' + hex4(r.f) + '</code>' +
         ' &nbsp;·&nbsp; links ' + r.l + ' &nbsp;·&nbsp; sequence ' + r.s;
  h += '<br>' + mftDatos(r);
  return h;
}

function mftSel(n, scroll){
  const cel = mftGrid.children[n];
  [...mftGrid.children].forEach(c => c.classList.remove('sel'));
  if (cel) { cel.classList.add('sel'); if (scroll) cel.scrollIntoView({block:'nearest'}); }
  mftDet.innerHTML = mftLinea(MFT[n]);
}

MFT.forEach(r => {
  const c = document.createElement('div');
  c.className = 'mcell' + (r.n === 139 ? ' solo' : '');
  c.style.background = MFT_COLOR[r.k] || '#475569';
  c.style.color = r.k === 'free' ? '#e2e8f0' : '#0f172a';
  c.textContent = r.n;
  c.title = r.n + (r.nm ? ' · ' + r.nm : '') + ' (' + MFT_ETIQ[r.k] + ')';
  c.onclick = () => mftSel(r.n, false);
  mftGrid.appendChild(c);
});

/* leyenda con recuento */
const cuenta = {};
MFT.forEach(r => { cuenta[r.k] = (cuenta[r.k] || 0) + 1; });
document.getElementById('mftLeyenda').innerHTML =
  Object.keys(MFT_COLOR).map(k =>
    '<span><i style="background:' + MFT_COLOR[k] + '"></i>' + MFT_ETIQ[k] +
    ' · ' + cuenta[k] + '</span>').join('') +
  '<span><i style="background:#475569;border:2px dashed #fff"></i>139 · solo en la copia</span>';

/* buscador */
const norm = s => s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
mftBus.oninput = () => {
  const q = norm(mftBus.value.trim());
  let hits = 0;
  MFT.forEach(r => {
    const ok = !q || norm(r.nm).includes(q) || String(r.n) === q;
    mftGrid.children[r.n].classList.toggle('dim', !ok);
    if (ok && q) { hits++; mftSel(r.n, false); }
  });
  mftCnt.textContent = q ? hits + (hits === 1 ? ' registro' : ' registros') : '';
};

mftSel(64, false);
/* MAPA-MFT-JS:FIN */
"""


def swap(text, ini, fin, block):
    """Reemplaza el bloque entre marcadores o lo inserta si no existe."""
    i = text.find(ini)
    if i >= 0:
        j = text.find(fin, i)
        return text[:i] + block.strip("\n") + text[j + len(fin):]
    return text


html = HTML.read_text(encoding="utf-8")

# 1) CSS
if "/* MAPA-MFT-CSS:INICIO */" in html:
    html = swap(html, "/* MAPA-MFT-CSS:INICIO */", "/* MAPA-MFT-CSS:FIN */", CSS)
else:
    html = html.replace("</style>", CSS.rstrip() + "\n</style>", 1)

# 2) sección HTML, antes de la sección 2
if "<!-- MAPA-MFT:INICIO -->" in html:
    html = swap(html, "<!-- MAPA-MFT:INICIO -->", "<!-- MAPA-MFT:FIN -->", HTML_BLOCK)
else:
    anchor = "<section>\n  <h2>2 · Cómo se encuentra"
    if anchor not in html:
        raise SystemExit("no encuentro la sección 2 para insertar el mapa")
    html = html.replace(anchor, HTML_BLOCK.strip("\n") + "\n\n" + anchor, 1)

# 3) JS, antes del </script> final
js = JS.replace("__DATA__", blob)
if "/* MAPA-MFT-JS:INICIO */" in html:
    html = swap(html, "/* MAPA-MFT-JS:INICIO */", "/* MAPA-MFT-JS:FIN */", js)
else:
    k = html.rfind("</script>")
    html = html[:k] + js.strip("\n") + "\n" + html[k:]

HTML.write_text(html, encoding="utf-8")
print("insertado en", HTML, "|", len(records), "registros |", len(blob), "B de datos")
