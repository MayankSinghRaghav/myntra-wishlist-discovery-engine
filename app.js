/* app.js — renders the claim register / manifest / hypothesis lean, and runs a keyless,
   client-side lexical RAG that REFUSES on thin or single-platform evidence. Diagnosis only. */
"use strict";

const HYP = ["h1", "h2", "h3", "other"];
const HYPNAME = {h1: "H1 uncertainty", h2: "H2 decay", h3: "H3 ≠ intent", other: "other"};
// A proper English function-word stoplist (interrogatives/pronouns/prepositions/auxiliaries) plus
// generic review fillers. The corpus is domain-specific (all Myntra fashion), so an off-topic query
// ("how to cook pasta", "best football player ever") reduces to nothing once function words are
// stripped and remaining terms are checked against the corpus. (IDF/rarity fails here — domain words
// like "size"/"return" are the MOST common — so function-word stripping is the robust signal.)
const STOP = new Set((
  "about above after again against all and any are aren cannot could couldn did didn does doesn doing "
  + "don down during each few for from further had hadn has hasn have haven having her here hers herself "
  + "him himself his how into isn its itself let more most mustn myself nor not off once only other ought "
  + "our ours ourselves out over own same shan she should shouldn some such than that the their theirs "
  + "them themselves then there these they this those through too under until very was wasn were weren "
  + "what when where which while who whom why will with won would wouldn you your yours yourself yourselves "
  + "best good great nice love loved like ever today app myntra product item thing things time day people "
  + "make made use using buy bought order get got just really also one two lot bit want need got"
).split(/\s+/));
const pct = (n, d) => d ? Math.round(n / d * 100) + "%" : "0%";
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

let DATA = null, DF = null;   // DF: term -> number of index docs containing it
fetch("data.json").then(r => r.json()).then(d => { DATA = d; buildDF(d); render(d); })
  .catch(() => document.getElementById("stats").textContent = "Could not load data.json — run analyze.py.");

function buildDF(d) {
  DF = Object.create(null);
  for (const doc of (d.index || [])) {
    const seen = new Set((doc.text + " " + doc.claim + " " + doc.quote).toLowerCase().match(/[a-z0-9]+/g) || []);
    for (const t of seen) DF[t] = (DF[t] || 0) + 1;
  }
}

function badge(cls, txt) { return `<span class="badge ${cls}">${esc(txt)}</span>`; }

function render(d) {
  if (d._sample) document.getElementById("sampleTag").hidden = false;
  const m = d.manifest;

  document.getElementById("stats").innerHTML = [
    ["Documents", (m.n_documents || 0).toLocaleString()],
    ["Relevant", (m.n_relevant || 0).toLocaleString()],
    ["Platforms", m.n_independent_platforms || 0],
    ["Register claims", m.n_register_entries || 0],
    ["Contradicting", HYP.reduce((a, h) => a + (d.lean[h] ? d.lean[h].contradicts : 0), 0)],
  ].map(([l, v]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");

  const mix = m.model_mix || {};
  const ai = mix.gemini || 0, tot = Object.values(mix).reduce((a, b) => a + b, 0) || 1;
  document.getElementById("manifestLine").innerHTML =
    `By platform: ${JSON.stringify(m.counts_by_platform)} · dates ${esc(m.date_range && m.date_range.earliest || "?")}–${esc(m.date_range && m.date_range.latest || "?")} · `
    + `${pct(ai, tot)} AI-labelled (rest rule-fallback, logged) · not yet ingested: ${(m.not_ingested || []).join(", ")}.`;

  // hypothesis lean
  let L = `<tr><th>Hypothesis</th><th>supports</th><th>contradicts</th><th>neutral</th><th>net</th></tr>`;
  const maxv = Math.max(1, ...HYP.flatMap(h => [d.lean[h].supports, d.lean[h].contradicts]));
  for (const h of HYP) {
    const x = d.lean[h];
    L += `<tr><td>${badge("b-" + h, HYPNAME[h])}</td>
      <td>${lbar(x.supports, maxv, "var(--support)")}</td>
      <td>${lbar(x.contradicts, maxv, "var(--contra)")}</td>
      <td class="muted">${x.neutral}</td>
      <td><b>${x.net >= 0 ? "+" : ""}${x.net}</b></td></tr>`;
  }
  document.getElementById("lean").innerHTML = L;

  // register
  let R = `<tr><th>#</th><th>Claim</th><th>H</th><th>Stance</th><th>Theme</th><th>Src</th><th>Conf</th><th>Quotes</th><th>Verdict</th></tr>`;
  for (const e of d.register) {
    const qs = (e.source_quotes || []).map(q =>
      `<div class="q">“${esc(q.verbatim)}” <span class="src">[${esc(q.platform)}]${q.date ? " · " + esc(q.date) : ""}</span></div>`).join("");
    const thin = e.thin_evidence ? ` <span class="badge s-contradicts" title="single platform">thin</span>` : "";
    R += `<tr>
      <td class="muted">${esc(e.claim_id)}</td>
      <td>${esc(e.claim_text)}${e.inferred_segment ? ` <span class="tag">${esc(e.inferred_segment.category)}</span>` : ""}</td>
      <td>${badge("b-" + e.hypothesis_map.toLowerCase(), e.hypothesis_map)}</td>
      <td>${badge("s-" + e.stance, e.stance)}</td>
      <td class="small muted">${esc(e.theme)}</td>
      <td>${e.n_independent_srcs}${thin}</td>
      <td class="conf-${e.engine_confidence}">${e.engine_confidence}</td>
      <td><details><summary class="small muted">${(e.source_quotes || []).length} quote(s)</summary>${qs}</details></td>
      <td class="muted small">pending</td></tr>`;
  }
  document.getElementById("register").innerHTML = R;

  // segment
  const cats = d.categories || {};
  const catList = Object.entries(cats).slice(0, 8).map(([c, n]) => `<b>${esc(c)}</b> (${n})`).join(" · ");
  const top = Object.keys(cats)[0];
  document.getElementById("segment").innerHTML = catList
    ? `<p>Category concentration: ${catList}</p><p class="muted">Screener rec (pre-interview): over-sample recent wishlist users in <b>${esc(top)}</b>; age/geo not inferable from public text — recruit open.</p>`
    : `<p class="muted">No reliable category concentration yet — recruit category-open.</p>`;

  // discard
  const dp = d.discard_pile || {};
  document.getElementById("discard").innerHTML =
    `<p>Not relevant: <b>${dp.not_relevant ? dp.not_relevant.count : 0}</b> · Claims with no traceable quote (dropped): <b>${dp.unverified_claims ? dp.unverified_claims.count : 0}</b> · Thin single-platform claims: <b>${dp.thin_single_source_claims ? dp.thin_single_source_claims.count : 0}</b></p>`
    + (dp.unverified_claims && dp.unverified_claims.samples.length
      ? `<details><summary class="muted">sample dropped (untraceable) claims</summary>${dp.unverified_claims.samples.map(s => `<div class="q">${esc(s)}</div>`).join("")}</details>` : "");
}

function lbar(v, max, color) {
  return `<div class="bar"><i style="width:${Math.max(3, v / max * 100)}%;background:${color}"></i></div><span class="small muted"> ${v}</span>`;
}

// ---- keyless lexical RAG with refusal --------------------------------------
function tokens(s) {
  return [...new Set((s.toLowerCase().match(/[a-z0-9]+/g) || []).filter(t => t.length >= 3 && !STOP.has(t)))];
}
function ask() {
  const q = document.getElementById("q").value.trim();
  const out = document.getElementById("ans");
  const raw = tokens(q);
  // keep only query terms that actually exist in the corpus (df >= 2) -- an off-topic query's
  // topic words ("weather", "football") are absent, so nothing meaningful survives -> refuse.
  const qt = raw.filter(t => (DF[t] || 0) >= 2);
  if (!qt.length) {
    out.innerHTML = `<div class="refuse"><b>Refused — off-corpus.</b> None of those words carry a topic this corpus of Myntra wishlist evidence can speak to.</div>`; return;
  }
  const MIN_DOCS = 3;
  // query terms are already filtered to real in-corpus domain words, so a single-term match is
  // meaningful; rank by how many query terms a doc matches. Corroboration guard is MIN_DOCS + >=2 platforms.
  const scored = (DATA.index || []).map(doc => {
    const hay = (doc.text + " " + doc.claim + " " + doc.quote).toLowerCase();
    return {doc, score: qt.filter(t => hay.includes(t)).length};
  }).filter(x => x.score >= 1).sort((a, b) => b.score - a.score);
  const plats = new Set(scored.map(x => x.doc.platform));
  if (scored.length < MIN_DOCS) {
    out.innerHTML = `<div class="refuse"><b>Refused — thin evidence.</b> Only ${scored.length} document(s) meaningfully match that (need ≥${MIN_DOCS}); nothing verbatim to ground an answer on.</div>`; return;
  }
  if (plats.size < 2) {
    out.innerHTML = `<div class="refuse"><b>Refused — cross-source rule.</b> Matching evidence is from only ${plats.size} platform(s). A claim needs ≥2 independent platforms.</div>`; return;
  }
  const seen = new Set();
  const top = scored.filter(x => !seen.has(x.doc.quote) && seen.add(x.doc.quote)).slice(0, 5).map(x =>
    `<div class="q">${badge("b-" + x.doc.hypothesis.toLowerCase(), x.doc.hypothesis)} ${badge("s-" + x.doc.stance, x.doc.stance)} “${esc(x.doc.quote)}” <span class="src">[${esc(x.doc.platform)}]</span></div>`).join("");
  out.innerHTML = `<div class="answer"><b>Grounded evidence</b> from ${plats.size} platforms (${[...plats].join(", ")}) — verbatim only, no generation:${top}</div>`;
}
