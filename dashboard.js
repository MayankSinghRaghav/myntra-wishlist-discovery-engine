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
// data is inlined into the page (id="appdata") so the deployed site makes NO external requests
// — ad-blockers block generic root-level files like /app.js. Fall back to fetch for local dev.
(function () {
  const el = document.getElementById("appdata");
  const load = el ? Promise.resolve(JSON.parse(el.textContent))
                  : fetch("data.json").then((r) => r.json());
  load.then((d) => { DATA = d; buildDF(d); render(d); })
      .catch(() => { document.getElementById("stats").textContent =
        "Could not load data — run analyze.py then build_static.py."; });
})();

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

  // reconciliation panel — corpus proposes, interviews decide
  document.getElementById("reconcile").innerHTML = renderReconcile(d);

  // hypothesis lean — corpus signal AND interview verdict on the same row
  const iv = d.interview || {};
  let L = `<tr><th>Hypothesis</th><th>supports</th><th>contradicts</th><th>net</th><th>Interview verdict</th></tr>`;
  const maxv = Math.max(1, ...HYP.flatMap(h => [d.lean[h].supports, d.lean[h].contradicts]));
  for (const h of HYP) {
    const x = d.lean[h];
    const v = iv[h];
    const vcell = v
      ? `<span class="iv iv-${v.strength}">${esc(v.verdict)}</span><div class="iv-detail">${esc(v.detail)}</div>`
      : `<span class="muted">— not a primary hypothesis</span>`;
    L += `<tr><td>${badge("b-" + h, HYPNAME[h])}</td>
      <td>${lbar(x.supports, maxv, "var(--support)")}</td>
      <td>${lbar(x.contradicts, maxv, "var(--contra)")}</td>
      <td><b>${x.net >= 0 ? "+" : ""}${x.net}</b></td>
      <td>${vcell}</td></tr>`;
  }
  document.getElementById("lean").innerHTML = L;

  // H1 pre-purchase vs post-purchase grievance split
  document.getElementById("h1split").innerHTML = renderH1Split(d.h1_split);

  // audit coverage — honest, computed from how many register entries carry a verdict
  const a = d.audit || { n_audited: 0, n_total: (d.register || []).length, distribution: {}, n_interviews: 0 };
  const distTxt = Object.entries(a.distribution || {}).map(([k, n]) => `${n} ${k}`).join(" · ") || "none yet";
  document.getElementById("auditCoverage").innerHTML =
    `<b>${a.n_audited} of ${a.n_total} claims</b> carry an interview verdict (${a.n_interviews} interviews) — ${distTxt}. `
    + `The rest are <span class="muted">pending</span>: 6 interviews adjudicate the highest-signal claims, not the long tail.`;

  // register
  let R = `<tr><th>#</th><th>Claim</th><th>H</th><th>Stance</th><th>Theme</th><th>Src</th><th>Conf</th><th>Quotes</th><th>Interview verdict</th></tr>`;
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
      <td>${verdictCell(e)}</td></tr>`;
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

// "Corpus proposes → interviews decide" — reconcile the H1 inversion honestly
function renderReconcile(d) {
  const h1 = d.lean.h1, iv = (d.interview || {}).h1 || {}, sp = d.h1_split || {};
  // surface a real contradicting H1 claim (returns remove hesitation) straight from the register
  const contra = (d.register || []).find(e => e.hypothesis_map === "H1" && e.stance === "contradicts"
    && (e.source_quotes || []).length);
  const cq = contra ? `“${esc(contra.source_quotes[0].verbatim)}” <span class="src">[${esc(contra.source_quotes[0].platform)}]</span>` : "";
  return `<div class="reconcile">
    <div class="rec-tag">Corpus proposes → interviews decide</div>
    <p>The corpus's loudest signal is <b class="b-h1-t">H1 (uncertainty), net +${h1.net}</b> — yet the interviews
      <b class="iv-rejected-t">rejected H1 as the primary blocker</b> (${iv.detail || ""}). That is not a contradiction to hide; it's the point of the method:</p>
    <ul>
      <li>H1's lean is <b>inflated by post-purchase return grievances</b> — of its ${sp.total || 0} supporting claims, only
        <b>${sp.pre_purchase || 0}</b> read as pre-purchase uncertainty vs <b>${sp.post_purchase || 0}</b> post-purchase grievance
        (${sp.ambiguous || 0} ambiguous). Complaint-skewed reviews shout about returns, not about the save→buy decision.</li>
      <li>And it <b>cuts both ways</b> — the corpus also carries claims that argue <i>against</i> H1${cq ? `, e.g. ${cq}` : ""}.</li>
      <li>Public text can only <b>propose</b> hypotheses. Only <b>primary research on users' own saved items</b> can settle which
        blocker actually decides a non-purchase — and it did: H3 strong, H2 weak, <b>H1 rejected</b>.</li>
    </ul>
  </div>`;
}

function renderH1Split(s) {
  if (!s || !s.total) return `<p class="muted">No H1 supporting claims to split.</p>`;
  const max = Math.max(s.pre_purchase, s.post_purchase, s.ambiguous, 1);
  const row = (lab, v, cls) =>
    `<div class="bar-row"><div class="bar-lab">${lab}<em>n=${v}</em></div>
     <div class="bar-track"><div class="bar-fill ${cls}" style="width:${Math.max(3, v / max * 100)}%"></div></div>
     <div class="bar-val">${pct(v, s.total)}</div></div>`;
  return `<div class="bars">
      ${row("Pre-purchase uncertainty", s.pre_purchase, "elig")}
      ${row("Post-purchase grievance", s.post_purchase, "inelig")}
      ${row("Ambiguous", s.ambiguous, "amb")}
    </div>
    <p class="small muted" style="margin-top:8px">${esc(s.method)}</p>`;
}

function verdictCell(e) {
  if (!e.audit_verdict) return `<span class="muted small">pending</span>`;
  const cls = e.audit_verdict.replace(/\s+/g, "-");
  return `<span class="verdict-b v-${cls}">${esc(e.audit_verdict)}</span>`
    + (e.audit_note ? `<details><summary class="small muted">why</summary><span class="small">${esc(e.audit_note)}</span></details>` : "");
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
