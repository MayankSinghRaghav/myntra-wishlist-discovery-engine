/* app.js — renders data.json and runs a keyless, client-side lexical RAG that
   REFUSES when evidence is thin. No framework, no build, no runtime API key. */
"use strict";

const HYPS = ["h1", "h2", "h3"];
const HCOLOR = { h1: "var(--h1)", h2: "var(--h2)", h3: "var(--h3)" };
const HNAME = { h1: "H1 uncertainty", h2: "H2 decay", h3: "H3 not-intent" };
const STOP = new Set("the a an and or of to for in on is it my me you we they this that with was but not are be at as if so".split(" "));
const pct = x => (x * 100).toFixed(0) + "%";
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let DATA = null;

fetch("data.json").then(r => r.json()).then(d => { DATA = d; render(d); })
  .catch(() => document.getElementById("headline").textContent = "Could not load data.json — run analyze.py.");

function render(d) {
  if (d._sample) document.getElementById("sampleTag").hidden = false;
  document.getElementById("headline").textContent = d.headline;

  const c = d.corpus;
  document.getElementById("stats").innerHTML = [
    ["Texts", c.n_total.toLocaleString()],
    ["Relevant", c.n_relevant.toLocaleString()],
    ["Sources", c.n_sources],
    ["AI-labelled", pct(d.model_mix.ai_share)],
    ["“None” share", pct(d.none_share)],
  ].map(([l, v]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");

  // hypotheses overall
  let rows = `<tr><th>Hypothesis</th><th>Docs</th><th>Overall share</th><th>Sources</th><th>≥2 src</th><th>Decision</th></tr>`;
  for (const h of HYPS) {
    const H = d.hypotheses[h];
    rows += `<tr><td><b style="color:${HCOLOR[h]}">${esc(H.name)}</b></td><td>${H.docs}</td>
      <td>${barCell(H.overall_share, HCOLOR[h])}</td><td>${H.n_sources}</td>
      <td>${H.cross_source_ok ? "✓" : "<span style='color:var(--bad)'>✗</span>"}</td>
      <td><span class="badge ${H.decision}">${H.decision}</span></td></tr>`;
  }
  document.getElementById("hypTable").innerHTML = rows;
  document.getElementById("noneLine").innerHTML =
    `<b>“None” (supports no hypothesis): ${pct(d.none_share)}</b> (${d.none_docs} docs) — tracked, not hidden.`;
  document.getElementById("mixLine").textContent =
    `Model mix: ${JSON.stringify(d.model_mix.counts)} · price sanity (not the headline): ${pct(d.price_sanity.price_share)} price / ${pct(d.price_sanity.non_price_share)} non-price.`;

  // per-segment matrix
  let m = `<tr><th>Intent segment</th><th>n</th><th>H1</th><th>H2</th><th>H3</th><th>leads</th></tr>`;
  for (const [seg, n] of Object.entries(d.segments)) {
    m += `<tr><td><b>${esc(seg)}</b></td><td>${n}</td>`;
    for (const h of HYPS) {
      const cell = d.hypotheses[h].by_segment[seg];
      m += `<td class="${cell.leads ? "lead" : ""}">${barCell(cell.share, HCOLOR[h])}<span class="small muted"> ${cell.docs}</span></td>`;
    }
    m += `<td>${d.seg_leader[seg] ? HNAME[d.seg_leader[seg]] : "—"}</td></tr>`;
  }
  document.getElementById("matrix").innerHTML = m;

  // audit table
  let a = `<tr><th>Claim</th><th>Sources</th><th>Docs</th><th>Sample verbatim quotes</th><th>Verdict</th></tr>`;
  for (const r of d.audit_table) {
    const qs = ["quote_1", "quote_2", "quote_3"].filter(k => r[k]).map(k => `<div class="q">“${esc(r[k])}”</div>`).join("");
    a += `<tr><td>${esc(r.claim)}</td><td>${esc(r.sources)}</td><td>${r.doc_count}</td><td>${qs}</td>
      <td><span class="muted">pending</span></td></tr>`;
  }
  document.getElementById("audit").innerHTML = a;

  // discard pile
  const dp = d.discard_pile;
  document.getElementById("discard").innerHTML =
    `<p>Not relevant: <b>${dp.not_relevant.count}</b> · Supports no hypothesis: <b>${dp.none_hypothesis.count}</b>
      · Weak/single-source cells not promoted: <b>${dp.weak_cells.length}</b></p>` +
    (dp.none_hypothesis.samples.length
      ? `<details><summary class="muted">sample “none” texts</summary>${dp.none_hypothesis.samples.map(s => `<div class="q">${esc(s)}</div>`).join("")}</details>` : "");
}

function barCell(share, color) {
  return `<div class="bar"><i style="width:${Math.max(2, share * 100)}%;background:${color}"></i></div><span class="small muted">${pct(share)}</span>`;
}

// ---- keyless lexical RAG with refusal --------------------------------------
function tokens(s) {
  return [...new Set((s.toLowerCase().match(/[a-z0-9]+/g) || []).filter(t => t.length >= 3 && !STOP.has(t)))];
}

function ask() {
  const q = document.getElementById("q").value.trim();
  const out = document.getElementById("ans");
  const qt = tokens(q);
  if (!qt.length) { out.innerHTML = `<div class="refuse">Type a question with a few real words.</div>`; return; }

  const MIN_DOCS = 3;                              // fewer than this mention the terms => thin
  const scored = DATA.index.map(doc => {
    const hay = (doc.text + " " + doc.quote + " " + doc.segment).toLowerCase();
    return { doc, score: qt.filter(t => hay.includes(t)).length };
  }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);

  const srcs = new Set(scored.map(x => x.doc.source));

  if (scored.length < MIN_DOCS) {
    out.innerHTML = `<div class="refuse"><b>Refused — thin evidence.</b> Only ${scored.length} document(s) in the
      corpus mention that (need ≥${MIN_DOCS}), so there is nothing verbatim to ground an answer on.</div>`;
    return;
  }
  if (srcs.size < 2) {
    out.innerHTML = `<div class="refuse"><b>Refused — cross-source rule.</b> The matching evidence comes from only
      ${srcs.size} source(s). A claim needs ≥2 independent sources; I won't answer from one.</div>`;
    return;
  }

  const seen = new Set();
  const strong = scored.filter(x => !seen.has(x.doc.quote) && seen.add(x.doc.quote));  // dedupe quotes
  const top = strong.slice(0, 5).map(x => {
    const tags = x.doc.hyps.map(h => `<span class="htag" style="background:${HCOLOR[h]}">${h.toUpperCase()}</span>`).join("");
    const link = x.doc.url ? ` <a href="${esc(x.doc.url)}" target="_blank" rel="noopener">[${esc(x.doc.source)}]</a>` : ` [${esc(x.doc.source)}]`;
    return `<div class="q">${tags}“${esc(x.doc.quote)}” <span class="src">${link} · ${x.doc.segment}</span></div>`;
  }).join("");
  out.innerHTML = `<div class="answer"><b>${strong.length} grounded quote(s)</b> from
    ${srcs.size} sources (${[...srcs].join(", ")}). Verbatim only — no generation:${top}</div>`;
}
