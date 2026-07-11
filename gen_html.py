#!/usr/bin/env python3
"""
gen_html.py - genera un singolo file HTML autonomo e offline da fse.db.

Uso: python3 gen_html.py fse.db orari-fse.html [cartella_fonts]

I font (IBM Plex Sans / IBM Plex Mono, licenza OFL) sono incorporati in base64:
il file non fa nessuna richiesta di rete. Se la cartella fonts/ manca, ripiega
sui font di sistema.
"""

import base64
import datetime as dt
import json
import os
import sys

import fse

FONTS = [
    ("Plex", 400, "ibm-plex-sans-latin-400-normal.woff2"),
    ("Plex", 600, "ibm-plex-sans-latin-600-normal.woff2"),
    ("Plex", 700, "ibm-plex-sans-latin-700-normal.woff2"),
    ("PlexMono", 400, "ibm-plex-mono-latin-400-normal.woff2"),
    ("PlexMono", 600, "ibm-plex-mono-latin-600-normal.woff2"),
]


def css_fonts(cartella):
    if not cartella or not os.path.isdir(cartella):
        return "/* font di sistema: cartella fonts/ non trovata */"
    out = []
    for fam, peso, nome in FONTS:
        p = os.path.join(cartella, nome)
        if not os.path.exists(p):
            continue
        b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
        out.append(
            "@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format('woff2')}" % (fam, peso, b64)
        )
    return "\n".join(out)


def costruisci_dati(db):
    con = fse.apri(db)

    fermate = [r["nome"] for r in con.execute("SELECT nome FROM fermate ORDER BY id")]
    id2idx_f = {r["id"]: i for i, r in enumerate(con.execute("SELECT id FROM fermate ORDER BY id"))}

    linee, id2idx_l = [], {}
    for i, r in enumerate(con.execute("SELECT id, linea, direzione, descrizione FROM linee ORDER BY id")):
        id2idx_l[r["id"]] = i
        linee.append([r["linea"], r["direzione"], r["descrizione"]])

    val = {}
    for r in con.execute("SELECT DISTINCT validita FROM corse"):
        v = r["validita"]
        freq = v.split("_", 1)[1]
        giorni, tipologia = fse._giorni_frequenza(con, freq)
        val[v] = {
            "g": sorted(giorni),
            "t": {"Feriale": "F", "Festivo": "X", "Feriale e festivo": "FX"}[tipologia],
            "ab": freq[-1] if (freq.endswith(" - A") or freq.endswith(" - B")) else None,
            "d": con.execute(
                "SELECT descrizione FROM legenda_validita WHERE validita=?", (v,)
            ).fetchone()[0],
        }
    val_keys = sorted(val)
    id2idx_v = {v: i for i, v in enumerate(val_keys)}

    corse, id2idx_c = [], {}
    for r in con.execute("SELECT * FROM corse ORDER BY id"):
        id2idx_c[r["id"]] = len(corse)
        corse.append({
            "c": r["codice"], "l": id2idx_l[r["linea_id"]], "v": id2idx_v[r["validita"]],
            "n": r["nota"], "nt": r["nota_tipo"], "nd": r["nota_dal"], "na": r["nota_al"],
            "t": [],
        })
    for r in con.execute("SELECT corsa_id, fermata_id, minuti FROM transiti ORDER BY corsa_id, sequenza"):
        corse[id2idx_c[r["corsa_id"]]]["t"].append([id2idx_f[r["fermata_id"]], r["minuti"]])

    idx_f = {n: i for i, n in enumerate(fermate)}
    loc = []
    for r in con.execute("SELECT id, nome FROM localita ORDER BY nome"):
        membri = [idx_f[x["nome"]] for x in con.execute(
            "SELECT nome FROM fermate WHERE localita_id=? ORDER BY nome", (r["id"],))]
        loc.append({"n": r["nome"], "f": membri})

    meta = {r["chiave"]: r["valore"] for r in con.execute("SELECT chiave, valore FROM meta")}

    return {
        "localita": loc,
        "fermate": fermate,
        "linee": linee,
        "validita": [dict(val[v], k=v) for v in val_keys],
        "corse": corse,
        "festivi": sorted(fse.FESTIVI),
        "dal": meta["validita_orario_dal"],
        "al": meta["validita_orario_al"],
        "settAPari": fse.SETT_A_PARI,
    }


HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#C1121F">
<title>Orari FSE &middot; servizio automobilistico</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icona-192.png">
<link rel="apple-touch-icon" href="icona-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Orari FSE">
<meta name="description" content="Orario del servizio automobilistico FSE, consultabile offline.">
<style>
__FONTS__

:root{
  --rosso:#C1121F;
  --rosso-cupo:#8E0A18;
  --rosso-tenue:#FBEDEE;
  --rosso-filo:#F0CFD3;
  --inchiostro:#14161A;
  --grigio:#5C626C;
  --grigio-2:#8B919B;
  --filo:#E2E5EA;
  --filo-2:#EEF0F3;
  --fondo:#FFFFFF;
  --fondo-2:#F7F8FA;
  --verde:#0F6B4F;
  --sans:'Plex',system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:'PlexMono',ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--fondo);color:var(--inchiostro);
  font-family:var(--sans);font-size:16px;line-height:1.5;
}
.foglio{max-width:800px;margin:0 auto;padding:0 22px}

/* testata */
.testata{background:var(--rosso);color:#fff;padding:26px 0 22px}
.marchio{
  display:flex;align-items:center;gap:10px;
  font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:rgba(255,255,255,.85);
}
.marchio:before{content:"";width:24px;height:3px;background:#fff;flex:none}
h1{font-size:clamp(28px,6.4vw,38px);font-weight:700;letter-spacing:-.022em;line-height:1.1;margin:12px 0 0}
.vigenza{font-family:var(--mono);font-size:12px;color:rgba(255,255,255,.85);margin:8px 0 0}

/* modi */
nav{display:flex;gap:4px;border-bottom:1px solid var(--filo);margin:0 0 26px}
nav button{
  appearance:none;background:none;border:0;cursor:pointer;font-family:inherit;
  font-size:14px;font-weight:600;color:var(--grigio);
  padding:14px 16px;border-bottom:3px solid transparent;margin-bottom:-1px;
}
nav button:hover{color:var(--inchiostro)}
nav button[aria-selected="true"]{color:var(--rosso);border-bottom-color:var(--rosso)}
nav button:focus-visible{outline:2px solid var(--rosso);outline-offset:-3px}

/* modulo */
.campo{margin:0 0 16px}
label{
  display:block;font-size:11px;font-weight:600;letter-spacing:.1em;
  text-transform:uppercase;color:var(--grigio);margin:0 0 6px;
}
input,select{
  width:100%;padding:12px 13px;font:inherit;color:var(--inchiostro);
  background:var(--fondo);border:1px solid var(--filo);border-radius:3px;
}
input:hover,select:hover{border-color:var(--grigio-2)}
input:focus,select:focus{outline:0;border-color:var(--rosso);box-shadow:0 0 0 3px var(--rosso-tenue)}
.campo{position:relative}
.proposte{
  position:absolute;z-index:40;left:0;right:0;top:100%;margin-top:3px;
  background:#fff;border:1px solid var(--filo);border-radius:3px;
  box-shadow:0 8px 24px rgba(20,22,26,.14);
  max-height:290px;overflow-y:auto;-webkit-overflow-scrolling:touch;
}
.proposte[hidden]{display:none}
.proposta{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  width:100%;text-align:left;background:none;border:0;cursor:pointer;
  padding:12px 14px;font:inherit;color:var(--inchiostro);
  border-bottom:1px solid var(--filo-2);
}
.proposta:last-child{border-bottom:0}
.proposta:hover,.proposta.attiva{background:var(--fondo-2)}
.proposta.loc{background:var(--rosso-tenue);font-weight:600}
.proposta.loc:hover,.proposta.loc.attiva{background:#F6DDE0}
.proposta .conta{
  flex:none;font-family:var(--mono);font-size:11px;color:var(--rosso);
  border:1px solid var(--rosso-filo);border-radius:2px;padding:1px 6px;background:#fff;
}
.proposta em{font-style:normal;background:#FDE9A9;border-radius:2px}
.proposte .vuota{padding:12px 14px;font-size:13px;color:var(--grigio-2)}
.suggerimento{margin:7px 0 0;font-size:12px;color:var(--grigio-2);line-height:1.5}
.suggerimento b{color:var(--grigio);font-weight:600}
.riga-3{display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:12px}
@media (max-width:520px){.riga-3{grid-template-columns:1fr}}
.azione{
  width:100%;padding:14px;margin-top:6px;cursor:pointer;border:0;border-radius:3px;
  background:var(--rosso);color:#fff;font-family:inherit;font-size:15px;font-weight:600;
}
.azione:hover{background:var(--rosso-cupo)}
.azione:focus-visible{outline:2px solid var(--inchiostro);outline-offset:2px}
.inverti{
  margin-top:8px;padding:7px 11px;cursor:pointer;border-radius:3px;
  background:none;border:1px solid var(--filo);color:var(--grigio);
  font-family:inherit;font-size:13px;font-weight:600;
}
.inverti:hover{border-color:var(--rosso);color:var(--rosso)}

/* esito */
.intestazione-esito{
  display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;
  margin:30px 0 0;padding:0 0 10px;border-bottom:2px solid var(--inchiostro);
}
.giorno{font-size:19px;font-weight:600;letter-spacing:-.01em}
.conteggio{font-family:var(--mono);font-size:12px;color:var(--grigio)}
.bollo{
  display:inline-block;margin-left:8px;padding:2px 8px;border-radius:2px;
  font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;vertical-align:2px;
}
.bollo.feriale{background:var(--fondo-2);color:var(--grigio);border:1px solid var(--filo)}
.bollo.festivo{background:var(--rosso-tenue);color:var(--rosso);border:1px solid var(--rosso-filo)}

/* riga corsa */
.corsa{
  display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;
  width:100%;text-align:left;background:none;border:0;border-bottom:1px solid var(--filo-2);
  cursor:pointer;padding:15px 4px;font:inherit;color:inherit;
}
.corsa:hover{background:var(--fondo-2)}
.corsa:focus-visible{outline:2px solid var(--rosso);outline-offset:-2px}
.corsa[aria-expanded="true"]{background:var(--fondo-2);border-bottom-color:transparent}
.ora{font-size:27px;font-weight:600;line-height:1;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.tratta{position:relative;height:28px}
.tratta:before{content:"";position:absolute;left:0;right:7px;top:50%;height:2px;background:var(--filo)}
.tratta:after{
  content:"";position:absolute;right:0;top:calc(50% - 4.5px);
  border-left:8px solid var(--filo);border-top:5px solid transparent;border-bottom:5px solid transparent;
}
.durata{
  position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
  background:var(--fondo);padding:0 9px;
  font-family:var(--mono);font-size:11px;color:var(--grigio);white-space:nowrap;
}
.corsa:hover .durata,.corsa[aria-expanded="true"] .durata{background:var(--fondo-2)}
.fermata{display:block;margin-top:4px;font-size:11px;color:var(--grigio);font-weight:400;max-width:15ch}
.coda{text-align:right}
.coda .fermata{max-width:none}
.altre-salite{
  grid-column:1/-1;margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--grigio);
}
.altre-salite b{color:var(--inchiostro);font-weight:600}
.coda .ora{font-size:20px;color:var(--grigio);font-weight:400}
.targhetta{margin-top:5px;display:flex;justify-content:flex-end;align-items:center;gap:6px}
.corsa-bollo{
  background:var(--rosso);color:#fff;border-radius:2px;padding:2px 7px;
  font-family:var(--mono);font-size:12px;font-weight:600;letter-spacing:.02em;
}
.codice{font-family:var(--mono);font-size:11px;color:var(--grigio-2)}
.nota-corsa{
  grid-column:1/-1;margin-top:6px;padding:5px 9px;border-left:3px solid var(--rosso);
  background:var(--rosso-tenue);color:var(--rosso-cupo);font-size:12px;
}
@media (max-width:420px){
  .corsa{gap:10px}
  .ora{font-size:23px}
  .coda .ora{font-size:17px}
}

/* percorso */
.percorso{background:var(--fondo-2);border-bottom:1px solid var(--filo);padding:0 16px 18px}
.scheda{padding:14px 0 12px;border-bottom:1px solid var(--filo);margin-bottom:10px}
.scheda .titolo{font-size:15px;font-weight:600}
.scheda .sotto{font-size:13px;color:var(--grigio);margin-top:2px}
.stato{display:inline-flex;align-items:center;gap:7px;margin-top:9px;font-size:13px;font-weight:600}
.stato:before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor;flex:none}
.stato.si{color:var(--verde)}
.stato.no{color:var(--rosso)}
.regola-validita{font-family:var(--mono);font-size:11px;color:var(--grigio);margin-top:8px;line-height:1.6}
.avvertenza-ab{color:var(--rosso);font-family:var(--mono);font-size:11px;margin-top:4px}
.sosta{display:grid;grid-template-columns:58px 18px 1fr;align-items:center;gap:12px;padding:3px 0}
.sosta .t{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;text-align:right;color:var(--grigio)}
.sosta .p{position:relative;min-height:24px;height:100%}
.sosta .p:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:2px;background:var(--filo);transform:translateX(-50%)}
.sosta:first-of-type .p:before{top:50%}
.sosta:last-child .p:before{bottom:50%}
.sosta .p:after{
  content:"";position:absolute;left:50%;top:50%;width:8px;height:8px;border-radius:50%;
  background:var(--fondo-2);border:2px solid var(--grigio-2);transform:translate(-50%,-50%);
}
.sosta.capo .p:after{background:var(--rosso);border-color:var(--rosso);width:11px;height:11px}
.sosta .n{font-size:14px;color:var(--grigio)}
.sosta.evid .n,.sosta.evid .t{color:var(--inchiostro);font-weight:600}
.sosta.evid .p:after{border-color:var(--rosso);background:#fff}
.domani{color:var(--rosso);font-size:10px;font-weight:600;margin-left:2px}

/* messaggi */
.messaggio{
  margin:24px 0 0;padding:16px 18px;background:var(--fondo-2);
  border-left:3px solid var(--grigio-2);border-radius:0 3px 3px 0;font-size:14px;
}
.messaggio.errore{background:var(--rosso-tenue);border-left-color:var(--rosso)}
.messaggio b{font-weight:600}
.scelte{margin:10px 0 0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:6px}
.scelte button{
  background:#fff;border:1px solid var(--filo);border-radius:3px;cursor:pointer;
  font-family:var(--mono);font-size:13px;color:var(--inchiostro);padding:6px 10px;
}
.scelte button:hover{border-color:var(--rosso);color:var(--rosso)}
.scelte button.agg{background:var(--rosso);border-color:var(--rosso);color:#fff;font-weight:600}
.scelte button.agg:hover{background:var(--rosso-cupo);color:#fff}

#banner{
  position:fixed;left:0;right:0;bottom:0;z-index:90;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:14px 18px calc(14px + env(safe-area-inset-bottom));
  background:var(--inchiostro);color:#fff;font-size:14px;
  box-shadow:0 -6px 24px rgba(20,22,26,.28);
}
#banner[hidden]{display:none}
#banner button{
  flex:none;background:var(--rosso);color:#fff;border:0;border-radius:3px;
  padding:9px 16px;font:inherit;font-weight:600;cursor:pointer;
}
#banner button:hover{background:var(--rosso-cupo)}
.versione{
  display:inline-block;margin-top:12px;padding:3px 8px;border:1px solid var(--filo);
  border-radius:2px;font-family:var(--mono);font-size:11px;color:var(--grigio-2);
}
.versione b{color:var(--inchiostro);font-weight:600}
footer{
  margin:44px 0 0;border-top:3px solid var(--rosso);padding:16px 0 40px;
  font-size:12px;color:var(--grigio);line-height:1.7;
}
footer b{color:var(--inchiostro);font-weight:600}
footer .cifre{font-family:var(--mono);color:var(--grigio-2)}
@media (prefers-reduced-motion:no-preference){
  .percorso{animation:apri .16s ease-out}
  @keyframes apri{from{opacity:0}to{opacity:1}}
}
</style>
</head>
<body>

<div class="testata">
  <div class="foglio">
    <div class="marchio">Ferrovie del Sud Est &middot; servizio automobilistico</div>
    <h1>Quadro orario</h1>
    <p class="vigenza" id="vigenza"></p>
  </div>
</div>

<div class="foglio">

<nav role="tablist">
  <button role="tab" id="tab-tratta" aria-selected="true">Tratta</button>
  <button role="tab" id="tab-linea" aria-selected="false">Linea</button>
  <button role="tab" id="tab-corsa" aria-selected="false">Corsa</button>
</nav>

<form id="f-tratta" onsubmit="return false">
  <div class="campo">
    <label for="da">Parti da</label>
    <input id="da" placeholder="Tocca per scegliere, o scrivi" autocomplete="off"
           enterkeyhint="search" role="combobox" aria-expanded="false" aria-autocomplete="list">
    <div class="proposte" id="p-da" role="listbox" hidden></div>
    <p class="suggerimento">Le citt&agrave; con pi&ugrave; fermate hanno in cima una voce
      <b>&laquo;tutte le fermate&raquo;</b> che le cerca insieme.</p>
  </div>
  <div class="campo">
    <label for="a">Arrivi a</label>
    <input id="a" placeholder="Tocca per scegliere, o scrivi" autocomplete="off"
           enterkeyhint="search" role="combobox" aria-expanded="false" aria-autocomplete="list">
    <div class="proposte" id="p-a" role="listbox" hidden></div>
    <button type="button" class="inverti" id="inverti">&#8646; Inverti</button>
  </div>
  <div class="riga-3">
    <div class="campo"><label for="data">Giorno</label><input type="date" id="data"></div>
    <div class="campo"><label for="dalle">Dalle</label><input type="time" id="dalle"></div>
    <div class="campo"><label for="alle">Alle</label><input type="time" id="alle"></div>
  </div>
  <button class="azione" id="cerca">Cerca corse</button>
</form>

<form id="f-linea" hidden onsubmit="return false">
  <div class="campo">
    <label for="linea">Linea e direzione</label>
    <select id="linea"></select>
  </div>
  <div class="campo"><label for="data2">Giorno</label><input type="date" id="data2"></div>
  <button class="azione" id="cerca2">Mostra le corse del giorno</button>
</form>

<form id="f-corsa" hidden onsubmit="return false">
  <div class="campo">
    <label for="codice">Codice corsa</label>
    <input id="codice" placeholder="es. 41015" autocomplete="off"
           enterkeyhint="search" role="combobox" aria-expanded="false" aria-autocomplete="list">
    <div class="proposte" id="p-codice" role="listbox" hidden></div>
  </div>
  <div class="campo"><label for="data3">Giorno</label><input type="date" id="data3"></div>
  <button class="azione" id="cerca3">Apri la corsa</button>
</form>

<div id="esito"></div>

<footer>
  <b>Fonte:</b> P.d.E. automobilistico FSE, 6 luglio &ndash; 13 settembre 2026.
  <span class="cifre" id="cifre"></span><br><br>
  <b>Feriale non vuol dire "non domenica".</b> Le corse Lun-Sab e Sab non circolano nei
  giorni festivi. Il <b>15 agosto 2026 cade di sabato</b>: quel giorno circolano le corse
  Dom/Fes, non le Lun-Sab.<br><br>
  <b>Da confermare con FSE:</b> la corrispondenza settimana A/B non &egrave; dichiarata per il
  2026 (la legenda del P.d.E. la definisce solo per il 2023). Qui A = settimana ISO pari.
  Riguarda <b id="nab"></b> corse, segnalate nel dettaglio.<br><br>
  Solo corse dirette, nessuna coincidenza calcolata. Funziona senza connessione.<br>
  <span class="versione">versione <b>__VERSIONE__</b></span>
</footer>

<div id="banner" hidden>
  <span>&Egrave; disponibile una versione aggiornata dell&rsquo;orario.</span>
  <button id="aggiorna">Aggiorna</button>
</div>

</div>
<script>
const D = __DATI__;

const GIORNI_LUNGHI = ["luned\u00ec","marted\u00ec","mercoled\u00ec","gioved\u00ec","venerd\u00ec","sabato","domenica"];
const MESI = ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio",
              "agosto","settembre","ottobre","novembre","dicembre"];

const gs = d => (d.getDay() + 6) % 7;
const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
const daIso = s => new Date(s + "T12:00:00");
const eFestivo = d => gs(d) === 6 || D.festivi.includes(iso(d));

function settimanaIso(d){
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const capodanno = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil(((t - capodanno) / 86400000 + 1) / 7);
}
const letteraAB = d => {
  const pari = settimanaIso(d) % 2 === 0;
  return D.settAPari ? (pari ? "A" : "B") : (pari ? "B" : "A");
};

function attiva(corsa, d){
  const g = iso(d);
  if (g < D.dal || g > D.al)
    return {ok:false, motivo:`fuori dal periodo dell'orario (${D.dal} \u2192 ${D.al})`};
  if (corsa.nt === "escluso" && g >= corsa.nd && g <= corsa.na)
    return {ok:false, motivo:corsa.n};
  if (corsa.nt === "solo" && !(g >= corsa.nd && g <= corsa.na))
    return {ok:false, motivo:corsa.n};
  const v = D.validita[corsa.v], festivo = eFestivo(d);
  if (v.t === "X"){
    /* "le domeniche ED I GIORNI FESTIVI": vale per ogni festivo, anche di sabato
       (15 agosto 2026). Il giorno della settimana non va controllato. */
    if (!festivo) return {ok:false, motivo:"giorno feriale, corsa festiva"};
  } else {
    if (v.t === "F" && festivo) return {ok:false, motivo:"giorno festivo, corsa feriale"};
    if (!v.g.includes(gs(d)))
      return {ok:false, motivo:`di ${GIORNI_LUNGHI[gs(d)]} questa corsa non \u00e8 prevista`};
  }
  if (v.ab && letteraAB(d) !== v.ab)
    return {ok:false, motivo:`settimana ${letteraAB(d)}, corsa di settimana ${v.ab}`};
  return {ok:true, motivo:"in servizio"};
}

function hhmm(m){
  const g = Math.floor(m/1440), r = m % 1440;
  const s = String(Math.floor(r/60)).padStart(2,"0") + ":" + String(r%60).padStart(2,"0");
  return g ? s + '<span class="domani">+1</span>' : s;
}
const dataLunga = d => `${GIORNI_LUNGHI[gs(d)]} ${d.getDate()} ${MESI[d.getMonth()]}`;
const dir = l => l[1] === "A" ? "ascendente" : "discendente";
const min = v => v ? (+v.slice(0,2))*60 + (+v.slice(3,5)) : null;

const perFermata = new Map();
D.corse.forEach((c,ci) => c.t.forEach((t,si) => {
  if (!perFermata.has(t[0])) perFermata.set(t[0], []);
  perFermata.get(t[0]).push([ci,si]);
}));
const perCodice = new Map();
D.corse.forEach((c,ci) => {
  if (!perCodice.has(c.c)) perCodice.set(c.c, []);
  perCodice.get(c.c).push(ci);
});

const etichettaLoc = l => `${l.n} \u00b7 tutte le fermate`;
const perLocalita = new Map();      // etichetta minuscola -> localita
D.localita.forEach(l => {
  perLocalita.set(etichettaLoc(l).toLowerCase(), l);
  perLocalita.set(("*" + l.n).toLowerCase(), l);
});
const localitaDi = new Map();       // indice fermata -> nome localita
D.localita.forEach(l => l.f.forEach(i => localitaDi.set(i, l.n)));

/* Ritorna {ids, et} per una fermata singola o per una localita' aggregata. */
function risolviLuogo(testo){
  const t = testo.trim().toLowerCase();
  if (!t) return {errore:"Scrivi una fermata o una localit\u00e0."};

  const l = perLocalita.get(t);
  if (l) return {ids:l.f, et:etichettaLoc(l), agg:true};

  const esatta = D.fermate.findIndex(n => n.toLowerCase() === t);
  if (esatta >= 0) return {ids:[esatta], et:D.fermate[esatta]};

  const cand = [];
  D.fermate.forEach((n,i) => { if (n.toLowerCase().includes(t)) cand.push(i); });
  if (!cand.length) return {errore:`Nessuna fermata contiene \u201c${testo}\u201d.`};
  if (cand.length > 1){
    // se tutte le candidate stanno nella stessa localita', proponi anche l'aggregato
    const nomi = new Set(cand.map(i => localitaDi.get(i)));
    const agg = (nomi.size === 1 && !nomi.has(undefined))
      ? D.localita.find(x => x.n === [...nomi][0]) : null;
    return {scelte:cand, aggregato:agg};
  }
  return {ids:[cand[0]], et:D.fermate[cand[0]]};
}

const esito = document.getElementById("esito");

const testata = (d, n, unita) => `<div class="intestazione-esito">
  <div class="giorno">${dataLunga(d)}
    <span class="bollo ${eFestivo(d)?"festivo":"feriale"}">${eFestivo(d)?"festivo":"feriale"}</span></div>
  <div class="conteggio">${n} ${unita}</div></div>`;

function riga(ci, mp, ma, tratto, nomeP, nomeA, altre){
  const c = D.corse[ci], l = D.linee[c.l];
  return `<button class="corsa" aria-expanded="false" data-corsa="${ci}" data-t="${tratto}">
    <span>
      <span class="ora">${hhmm(mp)}</span>
      ${nomeP ? `<span class="fermata">${nomeP}</span>` : ""}
    </span>
    <span class="tratta"><span class="durata">${ma-mp} min</span></span>
    <span class="coda">
      <span class="ora">${hhmm(ma)}</span>
      ${nomeA ? `<span class="fermata">${nomeA}</span>` : ""}
      <span class="targhetta">
        <span class="corsa-bollo">${c.c}</span>
        <span class="codice">linea ${l[0]}${l[1]}</span>
      </span>
    </span>
    ${altre && altre.length ? `<span class="altre-salite"><b>Puoi salire anche a:</b> ${
      altre.map(x => `${x[0]} ${hhmm(x[1])}`).join(" \u00b7 ")}</span>` : ""}
    ${c.n ? `<span class="nota-corsa">${c.n}</span>` : ""}
  </button>`;
}

function percorso(ci, d, evid){
  const c = D.corse[ci], l = D.linee[c.l], v = D.validita[c.v];
  const st = attiva(c, d);
  const soste = c.t.map((t,i) => {
    const capo = (i === 0 || i === c.t.length-1) ? " capo" : "";
    const e = evid && evid.includes(i) ? " evid" : "";
    return `<div class="sosta${capo}${e}">
      <div class="t">${hhmm(t[1])}</div><div class="p"></div>
      <div class="n">${D.fermate[t[0]]}</div></div>`;
  }).join("");
  return `<div class="percorso">
    <div class="scheda">
      <div class="titolo">Corsa ${c.c}</div>
      <div class="sotto">Linea ${l[0]} ${dir(l)} &mdash; ${l[2]}</div>
      <div class="stato ${st.ok?"si":"no"}">${st.ok ? "In servizio " + dataLunga(d)
        : "Non effettuata \u2014 " + st.motivo}</div>
      <div class="regola-validita">${v.k} &mdash; ${v.d}</div>
      ${v.ab ? '<div class="avvertenza-ab">Settimana A/B: convenzione non confermata da FSE.</div>' : ""}
    </div>${soste}</div>`;
}

/* ---------- elenco proposte (sostituisce il datalist, inaffidabile su mobile) ---------- */
const senzaAccenti = t => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

function evidenzia(testo, q){
  if (!q) return testo;
  const i = senzaAccenti(testo).indexOf(senzaAccenti(q));
  if (i < 0) return testo;
  return testo.slice(0,i) + "<em>" + testo.slice(i, i+q.length) + "</em>" + testo.slice(i+q.length);
}

/* Localita' sempre in cima, poi le fermate: prima quelle che iniziano con il testo
   digitato, poi quelle che lo contengono. A campo vuoto mostra tutte le localita'. */
function proposteLuogo(q){
  const t = senzaAccenti(q.trim());
  const out = [];

  D.localita.forEach(l => {
    if (!t || senzaAccenti(l.n).includes(t))
      out.push({v:etichettaLoc(l),
                h:evidenzia(l.n, q.trim()) + " \u00b7 tutte le fermate",
                conta:`${l.f.length} fermate`, loc:true});
  });
  if (!t) return out;

  const inizia = [], contiene = [];
  D.fermate.forEach(n => {
    const x = senzaAccenti(n);
    if (x.startsWith(t)) inizia.push(n);
    else if (x.includes(t)) contiene.push(n);
  });
  [...inizia, ...contiene].slice(0, 40).forEach(n =>
    out.push({v:n, h:evidenzia(n, q.trim()), conta:"", loc:false}));
  return out;
}

function proposteCodice(q){
  const t = q.trim().toLowerCase();
  const cod = [...perCodice.keys()].sort();
  return (t ? cod.filter(c => c.toLowerCase().includes(t)) : cod.slice(0, 30))
    .slice(0, 40)
    .map(c => ({v:c, h:evidenzia(c, q.trim()), conta:"", loc:false}));
}

function collegaProposte(idInput, idLista, sorgente, azione){
  const inp = document.getElementById(idInput);
  const box = document.getElementById(idLista);
  let voci = [], sel = -1;

  const chiudi = () => {
    box.hidden = true; sel = -1;
    inp.setAttribute("aria-expanded", "false");
  };
  const disegna = () => {
    voci = sorgente(inp.value);
    box.innerHTML = voci.length
      ? voci.map((v,i) =>
          `<button type="button" class="proposta${v.loc ? " loc" : ""}" role="option" data-i="${i}">
             <span>${v.h}</span>${v.conta ? `<span class="conta">${v.conta}</span>` : ""}
           </button>`).join("")
      : `<div class="vuota">Nessun risultato per \u201c${inp.value.trim()}\u201d</div>`;
    box.hidden = false; sel = -1; box.scrollTop = 0;
    inp.setAttribute("aria-expanded", "true");
  };
  const scegli = i => {
    if (i < 0 || i >= voci.length) return;
    inp.value = voci[i].v;
    chiudi();
    azione();
  };

  inp.addEventListener("focus", disegna);
  inp.addEventListener("input", disegna);
  inp.addEventListener("keydown", e => {
    if (box.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp"){
      e.preventDefault();
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + voci.length) % voci.length;
      box.querySelectorAll(".proposta").forEach((b,i) => b.classList.toggle("attiva", i === sel));
      const att = box.querySelector(".attiva");
      if (att) att.scrollIntoView({block:"nearest"});
    } else if (e.key === "Enter" && sel >= 0){
      e.preventDefault(); scegli(sel);
    } else if (e.key === "Escape"){
      chiudi();
    }
  });
  /* pointerdown e non click: il blur dell'input chiuderebbe la lista prima del click */
  box.addEventListener("pointerdown", e => {
    const b = e.target.closest(".proposta");
    if (!b) return;
    e.preventDefault();
    scegli(+b.dataset.i);
  });
  document.addEventListener("pointerdown", e => {
    if (!box.contains(e.target) && e.target !== inp) chiudi();
  });
}

function cercaTratta(){
  const d = daIso(document.getElementById("data").value);
  const rp = risolviLuogo(document.getElementById("da").value);
  const ra = risolviLuogo(document.getElementById("a").value);
  for (const [r, campo] of [[rp,"da"],[ra,"a"]]){
    if (r.errore) return esito.innerHTML = `<div class="messaggio errore">${r.errore}</div>`;
    if (r.scelte) return scegli(r.scelte, campo, r.aggregato);
  }
  const dalle = min(document.getElementById("dalle").value);
  const alle  = min(document.getElementById("alle").value);
  const setP = new Set(rp.ids), setA = new Set(ra.ids);

  /* Con una localita' una corsa puo' offrire piu' fermate di salita: una riga
     per corsa, con la salita utile piu' precoce fra quelle nella fascia oraria.
     Le altre restano elencate sotto. */
  const candidate = new Map();                  // corsa -> lista di coppie
  for (const idp of rp.ids)
    for (const [ci, si] of (perFermata.get(idp) || [])){
      const c = D.corse[ci];
      const mp = c.t[si][1];
      if (dalle !== null && mp < dalle) continue;
      if (alle  !== null && mp > alle)  continue;
      for (let sj = si+1; sj < c.t.length; sj++){
        if (!setA.has(c.t[sj][0])) continue;
        if (!candidate.has(ci)) candidate.set(ci, []);
        candidate.get(ci).push({si, sj, mp, ma:c.t[sj][1]});
        break;
      }
    }

  const ris = [];
  for (const [ci, coppie] of candidate){
    if (!attiva(D.corse[ci], d).ok) continue;
    coppie.sort((x,y) => x.mp - y.mp || (x.ma-x.mp) - (y.ma-y.mp));
    const b = coppie[0], c = D.corse[ci];
    ris.push({
      ci, si:b.si, sj:b.sj, mp:b.mp, ma:b.ma,
      nomeP: D.fermate[c.t[b.si][0]], nomeA: D.fermate[c.t[b.sj][0]],
      altre: coppie.slice(1).map(x => [D.fermate[c.t[x.si][0]], x.mp]),
    });
  }
  ris.sort((x,y) => x.mp - y.mp || (x.ma-x.mp) - (y.ma-y.mp));

  if (!ris.length){
    esito.innerHTML = testata(d, 0, "corse") +
      `<div class="messaggio"><b>Nessuna corsa diretta</b><br>
       Da ${rp.et} a ${ra.et}, ${dataLunga(d)}${eFestivo(d) ? " (festivo)" : ""}.
       ${!rp.agg || !ra.agg ? "Prova con la localit\u00e0 intera (le voci \u201ctutte le fermate\u201d in cima all\u2019elenco), " : "Prova "}
       un altro giorno, togli la fascia oraria, oppure spezza il viaggio su un nodo.</div>`;
    return;
  }
  esito.innerHTML = testata(d, ris.length, ris.length === 1 ? "corsa diretta" : "corse dirette") +
    ris.map(r => riga(r.ci, r.mp, r.ma, `${r.si}-${r.sj}`, r.nomeP, r.nomeA, r.altre)).join("");
}

function scegli(cand, campo, aggregato){
  const tutte = aggregato
    ? `<li><button class="agg" data-agg="${etichettaLoc(aggregato)}" data-campo="${campo}">
         \u2605 ${etichettaLoc(aggregato)}</button></li>` : "";
  esito.innerHTML = `<div class="messaggio">
    <b>Quale fermata?</b> Il nome corrisponde a ${cand.length} fermate.
    ${aggregato ? "Puoi anche cercarle tutte insieme." : ""}
    <ul class="scelte">${tutte}${cand.slice(0,40).map(i =>
      `<li><button data-scelta="${i}" data-campo="${campo}">${D.fermate[i]}</button></li>`).join("")}
    </ul></div>`;
}

function cercaLinea(){
  const li = +document.getElementById("linea").value;
  const d = daIso(document.getElementById("data2").value);
  const att = [];
  D.corse.forEach((c,ci) => { if (c.l === li && attiva(c,d).ok) att.push(ci); });
  att.sort((a,b) => D.corse[a].t[0][1] - D.corse[b].t[0][1]);
  const l = D.linee[li];
  if (!att.length){
    esito.innerHTML = testata(d, 0, "corse") +
      `<div class="messaggio"><b>Nessuna corsa</b><br>La linea ${l[0]} ${dir(l)}
       non &egrave; in servizio ${dataLunga(d)}.</div>`;
    return;
  }
  esito.innerHTML = testata(d, att.length, "corse in servizio") +
    att.map(ci => {
      const t = D.corse[ci].t;
      return riga(ci, t[0][1], t[t.length-1][1], "0-" + (t.length-1),
                  D.fermate[t[0][0]], D.fermate[t[t.length-1][0]], null);
    }).join("");
}

function cercaCorsa(){
  const cod = document.getElementById("codice").value.trim();
  const d = daIso(document.getElementById("data3").value);
  const cc = perCodice.get(cod);
  if (!cc) return esito.innerHTML =
    `<div class="messaggio errore">Nessuna corsa con codice \u201c${cod}\u201d.</div>`;
  esito.innerHTML = testata(d, cc.length, cc.length === 1 ? "corsa" : "corse con questo codice") +
    cc.map(ci => percorso(ci, d)).join("");
}

esito.addEventListener("click", e => {
  const ag = e.target.closest("[data-agg]");
  if (ag){
    document.getElementById(ag.dataset.campo).value = ag.dataset.agg;
    return cercaTratta();
  }
  const sc = e.target.closest("[data-scelta]");
  if (sc){
    document.getElementById(sc.dataset.campo).value = D.fermate[+sc.dataset.scelta];
    return cercaTratta();
  }
  const f = e.target.closest(".corsa");
  if (!f) return;
  const aperto = f.getAttribute("aria-expanded") === "true";
  document.querySelectorAll(".percorso").forEach(p => p.remove());
  document.querySelectorAll(".corsa").forEach(b => b.setAttribute("aria-expanded","false"));
  if (aperto) return;
  f.setAttribute("aria-expanded","true");
  const [si,sj] = f.dataset.t.split("-").map(Number);
  const idData = document.querySelector("nav [aria-selected='true']").id === "tab-linea" ? "data2" : "data";
  f.insertAdjacentHTML("afterend",
    percorso(+f.dataset.corsa, daIso(document.getElementById(idData).value), [si,sj]));
});

const moduli = {"tab-tratta":"f-tratta","tab-linea":"f-linea","tab-corsa":"f-corsa"};
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x => x.setAttribute("aria-selected", x === b));
  for (const [t,f] of Object.entries(moduli)) document.getElementById(f).hidden = (t !== b.id);
  esito.innerHTML = "";
});
document.getElementById("cerca").onclick  = cercaTratta;
document.getElementById("cerca2").onclick = cercaLinea;
document.getElementById("cerca3").onclick = cercaCorsa;
document.getElementById("inverti").onclick = () => {
  const a = document.getElementById("da"), b = document.getElementById("a");
  [a.value, b.value] = [b.value, a.value];
  if (a.value && b.value) cercaTratta();
};
["da","a","codice"].forEach(id => document.getElementById(id).addEventListener("keydown", e => {
  if (e.key === "Enter" && document.getElementById("p-" + id).hidden){
    e.preventDefault();
    (id === "codice" ? cercaCorsa : cercaTratta)();
  }
}));

(function(){
  collegaProposte("da", "p-da", proposteLuogo, cercaTratta);
  collegaProposte("a", "p-a", proposteLuogo, cercaTratta);
  collegaProposte("codice", "p-codice", proposteCodice, cercaCorsa);
  document.getElementById("linea").innerHTML = D.linee
    .map((l,i) => ({l,i}))
    .sort((x,y) => x.l[0].localeCompare(y.l[0],"it",{numeric:true}) || x.l[1].localeCompare(y.l[1]))
    .map(({l,i}) => `<option value="${i}">${l[0]} &middot; ${dir(l)} \u2014 ${l[2]}</option>`).join("");

  const oggi = iso(new Date());
  const g = (oggi >= D.dal && oggi <= D.al) ? oggi : D.dal;
  ["data","data2","data3"].forEach(id => {
    const el = document.getElementById(id);
    el.value = g; el.min = D.dal; el.max = D.al;
  });

  const f = daIso(D.dal), t = daIso(D.al);
  document.getElementById("vigenza").textContent =
    `In vigore dal ${f.getDate()} ${MESI[f.getMonth()]} al ${t.getDate()} ${MESI[t.getMonth()]} ${t.getFullYear()}`;
  document.getElementById("cifre").textContent =
    `${D.linee.length} linee \u00b7 ${D.corse.length} corse \u00b7 ${D.fermate.length} fermate ` +
    `(${D.localita.length} localit\u00e0 aggregate) \u00b7 ${D.corse.reduce((s,c) => s + c.t.length, 0)} transiti.`;
  document.getElementById("nab").textContent = D.corse.filter(c => D.validita[c.v].ab).length;

  if (oggi < D.dal || oggi > D.al){
    esito.innerHTML = `<div class="messaggio errore">Oggi &egrave; fuori dal periodo di questo
      orario (${D.dal} \u2192 ${D.al}). Il giorno &egrave; stato impostato al primo giorno utile.</div>`;
  }

  /* Service worker: rende la pagina installabile e disponibile offline.
     Se il file e' aperto da disco (file://) non serve e non viene registrato. */
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")){
    navigator.serviceWorker.register("sw.js").then(reg => {

      /* Un nuovo sw installato mentre uno vecchio ha ancora il controllo
         significa che su GitHub c'e' una versione piu' recente. */
      const proponi = sw => sw.addEventListener("statechange", () => {
        if (sw.state === "installed" && navigator.serviceWorker.controller)
          document.getElementById("banner").hidden = false;
      });
      if (reg.waiting && navigator.serviceWorker.controller)
        document.getElementById("banner").hidden = false;
      reg.addEventListener("updatefound", () => reg.installing && proponi(reg.installing));

      document.getElementById("aggiorna").onclick = () => {
        const sw = reg.waiting || reg.installing;
        if (sw) sw.postMessage("aggiorna"); else location.reload();
      };

      /* quando il nuovo sw prende il controllo, ricarica una volta sola */
      let ricaricato = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (ricaricato) return;
        ricaricato = true;
        location.reload();
      });

      reg.update().catch(() => {});
    }).catch(() => {});
  }
})();
</script>
</body>
</html>
"""


SW = r"""/* Service worker degli orari FSE.
   GENERATO da gen_html.py: non modificarlo a mano, verrebbe sovrascritto.
   La versione e' agganciata al momento della generazione, quindi ogni rigenerazione
   invalida da sola la cache dei telefoni: non c'e' niente da ricordarsi di cambiare. */
const VERSIONE = "__VERSIONE_ID__";
const RISORSE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icona-192.png",
  "./icona-512.png",
  "./icona-180.png",
];

self.addEventListener("install", e => {
  /* niente skipWaiting: il nuovo sw resta in attesa e la pagina mostra il banner
     "Aggiorna". Cosi' l'utente non si vede ricaricare l'app sotto le mani. */
  e.waitUntil(caches.open(VERSIONE).then(c => c.addAll(RISORSE)));
});

self.addEventListener("message", e => {
  if (e.data === "aggiorna") self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(k => Promise.all(k.filter(x => x !== VERSIONE).map(x => caches.delete(x))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(hit => hit || fetch(e.request).then(r => {
      const copia = r.clone();
      caches.open(VERSIONE).then(c => c.put(e.request, copia)).catch(() => {});
      return r;
    }).catch(() => caches.match("./index.html")))
  );
});
"""


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    db, out = sys.argv[1], sys.argv[2]
    cartella = sys.argv[3] if len(sys.argv) > 3 else \
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    adesso = dt.datetime.now()
    versione = adesso.strftime("%Y-%m-%d %H:%M")
    versione_id = "orari-fse-" + adesso.strftime("%Y%m%d-%H%M")

    dati = costruisci_dati(db)
    html = HTML.replace("__FONTS__", css_fonts(cartella))
    html = html.replace("__VERSIONE__", versione)
    html = html.replace("__DATI__", json.dumps(dati, ensure_ascii=False, separators=(",", ":")))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("scritto %s (%.0f KB)" % (out, len(html.encode("utf-8")) / 1024))

    # il service worker va rigenerato insieme, con la stessa versione:
    # e' quello che fa arrivare l'aggiornamento sui telefoni gia' installati
    sw_path = os.path.join(os.path.dirname(os.path.abspath(out)), "sw.js")
    with open(sw_path, "w", encoding="utf-8") as fh:
        fh.write(SW.replace("__VERSIONE_ID__", versione_id))
    print("scritto %s (cache: %s)" % (sw_path, versione_id))
    print("versione   : %s" % versione)


if __name__ == "__main__":
    main()
