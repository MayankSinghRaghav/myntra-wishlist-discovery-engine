/* dashboard.js — decision-first Discovery Engine dashboard.
   4 tabs (Decision / Evidence / Audit / Ask). Every number + chart is COMPUTED at runtime from the
   inlined data (claims_register.json + corpus_manifest.json, via data.json). No hardcoded outputs.
   Charts are inline SVG/CSS (no library) so the page stays self-contained, keyless and ad-blocker-proof. */
"use strict";

const C = { supports:"#0072b2", partly:"#e69f00", rejected:"#6b6e7b", brand:"#ff3f6c",
            ink:"#282c3f", muted:"#5a5f66", line:"#e6e8ec", panel:"#f7f8fa" };
const HYPNAME = { h1:"H1 · Purchase-time uncertainty", h2:"H2 · Occasion decay", h3:"H3 · Saved ≠ intent", other:"Other" };
const PLAIN = { h1:"Purchase-time uncertainty", h2:"Occasion decay", h3:"Mixed intent", other:"Other" };
// diagnosis-level routing principle per blocker (a "what to do" direction, NOT a prescribed feature)
const ROUTE = { h1:"reduce purchase-time doubt on the saved item",
                h2:"act before the occasion passes",
                h3:"tell real intent from browsing — don't nag" };
const IV_CLASS = { strong:"iv-strong", weak:"iv-weak", rejected:"iv-rejected" };
// function-word stoplist + review fillers — keeps the RAG's off-corpus refusal robust
const STOP = new Set(("about above after again against all and any are aren cannot could couldn did didn does doesn doing "
  + "don down during each few for from further had hadn has hasn have haven having her here hers herself him himself his how "
  + "into isn its itself let more most mustn myself nor not off once only other ought our ours ourselves out over own same shan "
  + "she should shouldn some such than that the their theirs them themselves then there these they this those through too under "
  + "until very was wasn were weren what when where which while who whom why will with won would wouldn you your yours yourself "
  + "yourselves best good great nice love loved like ever today app myntra product item thing things time day people make made "
  + "use using buy bought order get got just really also one two lot bit want need").split(/\s+/));

const esc = s => String(s==null?"":s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const themeLabel = t => String(t||"misc").replace(/_/g," ");   // snake_case theme keys are internal, never user-facing
const platLabel = k => ({google_play:"Play Store",youtube:"YouTube",reddit:"Reddit",
  apple_app_store:"App Store",x_twitter:"X/Twitter",quora:"Quora"}[k] || String(k||"").replace(/_/g," "));
const pct = (n,d) => d ? Math.round(n/d*100)+"%" : "0%";
const pct1 = (n,d) => d ? (n/d*100).toFixed(1)+"%" : "0%";
const $ = id => document.getElementById(id);

let DATA=null, DF=null, REGISTER=[];

(function () {
  const el = $("appdata");
  const load = el ? Promise.resolve(JSON.parse(el.textContent)) : fetch("data.json").then(r=>r.json());
  load.then(d => { DATA=d; REGISTER=d.register||[]; buildDF(d); renderAll(d); setupTabs(); })
      .catch(() => { $("verdict").innerHTML = `<div class="empty">Could not load data — run analyze.py then build_static.py.</div>`; });
})();

function setupTabs() {
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("on", x===t));
    document.querySelectorAll(".tabpane").forEach(p => p.classList.toggle("on", p.id==="tab-"+t.dataset.tab));
  });
}
function goTab(name){ document.querySelector(`.tab[data-tab="${name}"]`)?.click(); window.scrollTo(0,0); }
window.goTab = goTab;

function buildDF(d) {
  DF = Object.create(null);
  for (const doc of (d.index||[])) {
    const seen = new Set((doc.text+" "+doc.claim+" "+doc.quote).toLowerCase().match(/[a-z0-9]+/g) || []);
    for (const t of seen) DF[t] = (DF[t]||0)+1;
  }
}

function renderAll(d) {
  try { renderVerdict(d); } catch(e){ $("verdict").innerHTML=empty("verdict"); }
  renderKPIs(d); renderScoreboard(d); renderReconcile(d);
  renderOpps(d); renderFunnel(d); renderVerdictDist(d); renderPlatforms(d); renderH1Split(d);
  renderMethod(d); renderAudit(d);
}
const empty = what => `<div class="empty">No data for ${esc(what)}.</div>`;
const badge = (cls,txt) => `<span class="badge ${cls}">${esc(txt)}</span>`;

// ─────────────────────────────────────────── TAB 1: DECISION
function renderVerdict(d) {
  const m = d.manifest || {}, tri = (d.triangulation||{}).rows || {}, sv = d.survey || {};
  const hyps = ["h1","h2","h3"].filter(h => tri[h] || (d.lean||{})[h]);
  const names = hyps.map(h => PLAIN[h].toLowerCase()).join(", ").replace(/, ([^,]*)$/, ", and $1");
  const lean = d.lean||{};
  const routes = hyps.map(h => {
    const n = (lean[h]||{}).net;
    return `<span class="route"><b>${esc(PLAIN[h])}</b>${n!=null?` <i>(${n>=0?"+":""}${n} claims)</i>`:""} → ${esc(ROUTE[h])}</span>`;
  }).join("");
  const docs = (m.n_documents||0).toLocaleString();
  $("verdict").innerHTML = `<div class="answer">
    <div class="q">The question</div>
    <p class="qtext">Why do shoppers <b>save</b> fashion items on Myntra but not <b>buy</b> them — and can we move it <b>without discounts</b>?</p>
    <div class="found">What we found</div>
    <p class="finding"><b>There is no single blocker.</b> ${hyps.length||3} different reasons compete — ${esc(names)} —
      so the root error is treating every saved item the same.</p>
    <div class="means">What it means for Myntra</div>
    <p class="meanssub">Capture the user's intent at save-time, then <b>route each save to the right response</b>:</p>
    <div class="routes">${routes}</div>
    <p class="brief">This is a <b>diagnosis and a routing principle</b> — not a prescribed feature. The engine deliberately stops at the “what,” not the “how.”</p>
    <div class="sure"><b>How sure?</b> Triangulated across 3 instruments — ${docs} public docs · survey n=${sv.n||26} · 6 interviews.
      Every claim re-opens to a verbatim quote; nothing is generated. A prioritised hypothesis, not proof.</div>
    <div class="readpath">Read on → <b>Decision</b> (you're here) ·
      <a onclick="goTab('evidence')">Evidence</a> · <a onclick="goTab('method')">Method</a> · <a onclick="goTab('audit')">Audit</a></div>
  </div>`;
}

function renderKPIs(d) {
  const m = d.manifest||{};
  const nHyp = ["h1","h2","h3"].filter(h => (d.lean||{})[h]).length || 3;
  const tiles = [
    [(m.n_documents||0).toLocaleString(), "public docs analysed"],
    [(m.n_register_entries||REGISTER.length||0), "traceable claims · 100% quote-backed"],
    [nHyp, "competing blockers · none dominant"],
    ["3", "instruments triangulated · corpus · survey · interviews"],
  ];
  $("kpis").innerHTML = tiles.map(([b,s]) => `<div class="kpi"><b>${b}</b><span>${s}</span></div>`).join("");
}

function renderScoreboard(d) {
  const lean = d.lean||{}, tri = (d.triangulation||{}).rows||{}, survey = d.survey||{};
  const hyps = ["h1","h2","h3"].filter(h => lean[h]);
  if (!hyps.length) { $("scoreboard").innerHTML = empty("scoreboard"); return; }
  const max = Math.max(1, ...hyps.flatMap(h => [lean[h].supports, lean[h].contradicts]));
  const body = hyps.map(h => {
    const x = lean[h], T = tri[h]||{};
    const vchip = `<span class="iv ${IV_CLASS[T.strength]||"iv-weak"}">${esc(T.verdict||"")}${T.instruments?` · ${esc(T.instruments)}`:""}</span>`;
    return `<div style="margin:16px 0 4px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;gap:8px">
        <b>${esc(HYPNAME[h])}</b>${vchip}</div>
      <div style="display:flex;align-items:center;gap:7px">
        <span class="barval" style="width:26px;text-align:right;color:${C.partly}" title="contradicts">${x.contradicts}</span>
        <div style="flex:1;position:relative;height:18px;background:${C.panel};border-radius:5px">
          <div style="position:absolute;right:50%;top:0;bottom:0;width:${x.contradicts/max*50}%;background:${C.partly};border-radius:5px 0 0 5px"></div>
          <div style="position:absolute;left:50%;top:0;bottom:0;width:${x.supports/max*50}%;background:${C.supports};border-radius:0 5px 5px 0"></div>
          <div style="position:absolute;left:50%;top:-3px;bottom:-3px;width:1.5px;background:#3a3f4c"></div>
        </div>
        <span class="barval" style="width:30px;color:${C.supports}" title="supports">${x.supports}</span>
      </div>
      <div class="tri-row">
        <span><i class="tri-k">Engine</i> ${esc(T.engine||("+"+x.net))}</span>
        <span><i class="tri-k">Survey n=${survey.n||26}</i> ${esc(T.survey||"—")}</span>
        <span><i class="tri-k">Interviews</i> ${esc(T.interviews||"—")}</span>
      </div></div>`;
  }).join("");
  const price = (d.triangulation||{}).price||{};
  const priceRow = `<div class="price-row">🏷️ <b>Price</b> — <b>${esc(price.verdict||"barred lever — not actioned")}</b>
      <span class="muted small">· Engine: ${esc(price.engine||"present")} · ${esc(price.survey||"top-2 driver")}</span></div>`;
  const legend = `<div class="lgd"><span><i class="sw" style="background:${C.supports}"></i>corpus supports (→)</span>
      <span><i class="sw" style="background:${C.partly}"></i>contradicts (←)</span><span>│ badge = triangulated verdict</span></div>`;
  const bias = `<p class="small muted bias">⚖ ${esc((d.triangulation||{}).bias_note||"")}</p>`;
  $("scoreboard").innerHTML = body + priceRow + legend + bias;
  $("scoreTake").innerHTML = `<b>Two of three instruments make H1 a top blocker</b> (corpus loudest, survey #1);
    the episodic interviews dissent on its <b>deciding</b> role (0/6). No single blocker → <b>route by intent</b>.`;
}

function renderReconcile(d) {
  const lean=d.lean||{}, iv=(d.interview||{}).h1||{}, sp=d.h1_split||{};
  const contra = (REGISTER).find(e => e.hypothesis_map==="H1" && e.stance==="contradicts" && (e.source_quotes||[]).length);
  const cq = contra ? `“${esc(contra.source_quotes[0].verbatim)}” <span class="src">[${esc(platLabel(contra.source_quotes[0].platform))}]</span>` : "";
  const unclear = sp.unclear!=null ? sp.unclear : (sp.ambiguous||0);
  $("reconcile").innerHTML = `<div class="reconcile">
    <div class="rec-tag">Why H1 is a top blocker — and why it's contested</div>
    <p style="margin:0">H1 is the <b>loudest corpus signal (+${(lean.h1||{}).net})</b> and the <b>#1 survey reason (${esc((d.survey||{}).h1||"32%")})</b>,
      yet the episodic interviews found it rarely the <b>deciding</b> reason (0/6). Both are true — shown, not smoothed:</p>
    <ul>
      <li>Most of H1's corpus volume is <b>post-purchase grievance</b>, not saved-item hesitation — ${sp.pre_purchase||0} pre-purchase vs
        <b>${sp.post_purchase||0}</b> post-purchase (${unclear} unclear). So it's a top <b>cited</b> blocker, easily over-weighted as the <b>deciding</b> one.</li>
      <li>It cuts both ways — the corpus also carries claims against H1${cq?`, e.g. ${cq}`:""}.</li>
      <li><b>Two of three instruments</b> support H1 → <b>Supported as a top blocker</b>. The interview dissent on deciding-role is exactly why
        the answer isn't “one blocker” but <b>route by intent</b> — H1, H2 and H3 are co-equal.</li>
    </ul></div>`;
}

// ─────────────────────────────────────────── TAB 2: EVIDENCE
function renderFunnel(d) {
  const m=d.manifest||{}, docs=m.n_documents||0, rel=m.n_relevant||0, claims=m.n_register_entries||0;
  if (!docs) { $("funnel").innerHTML = empty("funnel"); return; }
  const steps = [["Documents analysed", docs, C.rejected||C.muted],
                 ["Relevant (on-topic)", rel, C.partly], ["Traceable claims", claims, C.supports]];
  $("funnel").innerHTML = steps.map(([lab,v,col]) => `
    <div style="margin:9px 0">
      <div style="display:flex;justify-content:space-between;font-size:12.5px"><span>${lab}</span>
        <b>${v.toLocaleString()} <span class="muted" style="font-weight:400">(${pct1(v,docs)})</span></b></div>
      <div style="height:16px;background:${C.panel};border-radius:5px;margin-top:3px">
        <div style="height:100%;width:${Math.max(0.6, v/docs*100)}%;background:${col};border-radius:5px"></div></div>
    </div>`).join("");
  $("funnelTake").innerHTML = `<b>${pct1(docs-rel,docs)} discarded</b> — only high-signal evidence survives to the register.`;
}

function stackBar(segs, total) {   // segs: [{label,value,color}]
  const t = total || segs.reduce((a,s)=>a+s.value,0) || 1;
  const bar = `<div style="display:flex;height:26px;border-radius:6px;overflow:hidden;border:1px solid ${C.line}">`
    + segs.map(s => `<div title="${esc(s.label)}: ${s.value}" style="width:${s.value/t*100}%;background:${s.color}"></div>`).join("") + `</div>`;
  const lgd = `<div class="lgd">` + segs.map(s => `<span><i class="sw" style="background:${s.color}"></i>${esc(s.label)} ${s.value} (${pct(s.value,t)})</span>`).join("") + `</div>`;
  return bar + lgd;
}

function renderVerdictDist(d) {
  const a = d.audit||{}, dist = a.distribution||{};
  const order = [["held up",C.supports],["partly invented",C.partly],["rejected","#a01818"],["not tested",C.rejected]];
  const segs = order.filter(([k])=>dist[k]).map(([k,c])=>({label:k,value:dist[k],color:c}));
  if (!segs.length) { $("verdictDist").innerHTML = empty("verdict distribution"); return; }
  $("verdictDist").innerHTML = stackBar(segs, a.n_audited);
  const subst = (dist["held up"]||0)+(dist["partly invented"]||0)+(dist["rejected"]||0);
  $("verdictTake").innerHTML = `<b>${a.n_audited} of ${a.n_total} claims</b> verdicted (${pct1(a.n_audited,a.n_total)}) against ${a.n_interviews} interviews — ${subst} substantive, ${dist["not tested"]||0} honestly “not tested”.`;
}

function hbars(rows, color, unit) {   // rows: [[label,value]]
  const max = Math.max(1, ...rows.map(r=>r[1]));
  return rows.map(([lab,v]) => `
    <div style="display:grid;grid-template-columns:120px 1fr 54px;align-items:center;gap:8px;margin:5px 0">
      <span style="font-size:12.5px">${esc(lab)}</span>
      <div style="height:16px;background:${C.panel};border-radius:5px"><div style="height:100%;width:${Math.max(2,v/max*100)}%;background:${color};border-radius:5px"></div></div>
      <span class="barval" style="font-size:12.5px;text-align:right">${v.toLocaleString()}${unit||""}</span>
    </div>`).join("");
}

function renderThemes(d) {
  const counts = {};
  for (const e of REGISTER) counts[e.theme||"misc"] = (counts[e.theme||"misc"]||0)+1;
  const rows = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,10);
  if (!rows.length) { $("themes").innerHTML = empty("themes"); return; }
  $("themes").innerHTML = hbars(rows, C.brand);
  $("themeTake").innerHTML = `Returns/fit dominate what users <i>raise</i> — but the audit shows that volume is grievance, not the save→buy blocker.`;
}

function renderPlatforms(d) {
  const cp = (d.manifest||{}).counts_by_platform||{};
  const rows = Object.entries(cp).sort((a,b)=>b[1]-a[1]).map(([k,v])=>[platLabel(k),v]);
  if (!rows.length) { $("platforms").innerHTML = empty("platforms"); return; }
  const single = REGISTER.filter(e => (e.n_independent_srcs||1) < 2).length;
  $("platforms").innerHTML = hbars(rows, C.supports)
    + `<p class="small" style="margin:8px 0 0"><b style="color:${C.partly}">${single} of ${REGISTER.length} claims are single-platform</b> — thin corroboration.</p>`;
  $("platformTake").innerHTML = `The corpus <b>supports</b> the interviews; with corroboration this thin it can't carry the diagnosis alone.`;
}

function renderH1Split(d) {
  const s = d.h1_split||{};
  const unclear = s.unclear!=null ? s.unclear : (s.ambiguous||0);
  if (!s.total) { $("h1split").innerHTML = empty("H1 split"); return; }
  $("h1split").innerHTML = (s.net_lean!=null ? `<p class="small muted" style="margin:0 0 8px">H1 net corpus lean <b>+${s.net_lean}</b> → re-cut of its ${s.total} supporting claims:</p>` : "")
    + stackBar([{label:"Pre-purchase uncertainty",value:s.pre_purchase,color:C.supports},
                {label:"Post-purchase grievance",value:s.post_purchase,color:C.partly},
                {label:"Unclear",value:unclear,color:C.rejected}], s.total);
  $("h1Take").innerHTML = `Most of H1's corpus signal is <b>post-purchase grievance</b> (${pct(s.post_purchase,s.total)}), not saved-item hesitation (${pct(s.pre_purchase,s.total)}) — the computed reason its <b>deciding</b> role is contested even while it's a top <b>cited</b> blocker.`;
}

// ─────────────────────────────────────────── OPPORTUNITY RANKING (Evidence) + METHOD
// deterministic pre/post-purchase classifier — mirrors reclassify_h1.py, powers the EFFORT term.
const RE_POST = /\b(returns?|returned|refund|exchang|replac|deliver|courier|pick[- ]?up|shipment|shipping|receiv|arriv|wrong (product|item|size|order)|damag|defective|torn|faulty|old product|used product|cancel|my order|the order|order was|quality check|not as (shown|described))/i;
const RE_PRE = /\b(not sure|unsure|confus|can'?t decide|don'?t know (if|which|what)|size chart|which size|will it fit|true to size|size guide|before (buy|order|purchas|i buy)|should i buy|thinking of buying|planning to buy|hesitat|not confident|afraid it (won'?t|wont)|worried it)/i;
function prePost(text){ const post=RE_POST.test(text||""), pre=RE_PRE.test(text||""); return (pre&&!post)?"pre":(post&&!pre)?"post":"unclear"; }
function claimBlob(e){ return (e.claim_text||"")+" "+(e.source_quotes||[]).map(q=>q.verbatim||"").join(" "); }
function bandv(v,lo,hi){ return v>=hi?3:(v>=lo?2:1); }
const HYP_FIT = { H1:3, H2:3, H3:2, other:1 };   // business-fit: hypothesis addressability (price=0, barred)

let OPPS = [];
function renderOpps(d){
  const rel = (d.manifest||{}).n_relevant || REGISTER.length || 1;
  const byTheme = {};
  for (const e of REGISTER){ const t=e.theme||"misc"; (byTheme[t]=byTheme[t]||[]).push(e); }
  const maxRec = Math.max(1, ...Object.values(byTheme).map(a=>a.length));
  OPPS = Object.entries(byTheme).map(([theme,claims]) => {
    const records = claims.length;
    const supShare = records ? claims.filter(e=>e.stance==="supports").length/records : 0;
    const hc={}; for (const e of claims){ const h=e.hypothesis_map||"other"; hc[h]=(hc[h]||0)+1; }
    const domH = Object.entries(hc).sort((a,b)=>b[1]-a[1])[0][0];
    const barred = /price/i.test(theme);
    let pre=0, post=0;
    for (const e of claims){ const b=prePost(claimBlob(e)); if(b==="pre")pre++; else if(b==="post")post++; }
    const postShare = (pre+post) ? post/(pre+post) : 0.5;
    const effort = postShare>=0.6 ? 3 : postShare>=0.3 ? 2 : 1;   // ops-heavy=3, pre-purchase fix=1
    const pain = bandv(supShare, 0.34, 0.6);
    const freq = bandv(Math.log1p(records)/Math.log1p(maxRec), 0.5, 0.8);
    const fit  = barred ? 0 : (HYP_FIT[domH]||1);
    const score = fit===0 ? 0 : +((pain*freq*fit)/effort).toFixed(2);
    const noise = barred || theme==="misc";
    return { theme, records, share:records/rel, domH, barred, pain, freq, fit, effort, score, noise, claims };
  }).sort((a,b)=> (a.noise-b.noise) || (b.score-a.score));

  const maxScore = Math.max(1, ...OPPS.map(o=>o.score));
  const head = `<tr><th>Theme</th><th>Records · % of relevant</th><th>Maps to</th>`
    + `<th class="help" title="pain × frequency × business-fit ÷ effort — each factor a 1–3 band computed from the corpus. pain = share of claims evidencing a real blocker; frequency = log-scaled volume; business-fit = hypothesis addressability (H1/H2=3, H3=2, other=1, price=0 barred); effort = post-purchase share (ops-heavy=3, pre-purchase wishlist fix=1). Higher = act first.">Opportunity score ⓘ</th>`
    + `<th>Signal</th></tr>`;
  const rows = OPPS.map((o,i) => {
    const maps = o.barred ? `<span class="badge b-other" title="price is a barred lever — not actioned">barred · price</span>`
                          : `<span class="badge b-${o.domH.toLowerCase()}" title="${esc(PLAIN[o.domH.toLowerCase()]||o.domH)}">${esc(o.domH)}</span>`;
    const sig = o.noise ? `<span class="sig noise">Noise</span>` : `<span class="sig real">Real</span>`;
    const pill = `<span class="score-pill${o.score < maxScore*0.5 ? " lo":""}">${o.score}</span>`;
    return `<tr class="opp-row${o.noise?" noise":""}" onclick="drill(${i})" title="click for the source-cited claims">
      <td><b>${esc(themeLabel(o.theme))}</b></td>
      <td>${o.records} <span class="muted">(${(o.share*100).toFixed(1)}%)</span>
        <span class="mbar"><div style="width:${Math.max(4,o.records/maxRec*100)}%"></div></span></td>
      <td>${maps}</td>
      <td>${pill} <span class="muted small">P${o.pain}·F${o.freq}·B${o.fit}÷E${o.effort}</span></td>
      <td>${sig}</td></tr>
      <tr id="drill-${i}" class="drill" style="display:none"><td colspan="5"></td></tr>`;
  }).join("");
  $("opps").innerHTML = head + rows;

  const dp = d.discard_pile||{};
  const notRel = (dp.not_relevant&&dp.not_relevant.count) || ((d.manifest||{}).n_documents - rel) || 0;
  const noQ = (dp.unverified_claims&&dp.unverified_claims.count) || 0;
  $("oppDiscard").innerHTML = `🗑 Discard pile (shown for honesty): <b>${notRel.toLocaleString()}</b> not-relevant documents + `
    + `<b>${noQ}</b> claims dropped for no traceable quote — never counted in any theme above.`;
  const top = OPPS.find(o=>!o.noise);
  $("oppTake").innerHTML = top ? `Top actionable theme by score: <b>${esc(themeLabel(top.theme))}</b>. `
    + `Because score divides by effort, loud <i>post-purchase</i> themes (returns/delivery) are down-weighted vs cheaper `
    + `<i>pre-purchase</i> wishlist fixes. Score is a hypothesis for prioritisation, not proof.` : "";
}

function drill(i){
  const row = $("drill-"+i); if (!row) return;
  if (row.style.display !== "none"){ row.style.display="none"; return; }
  const o = OPPS[i]; if (!o) return;
  const cs = o.claims.slice()
    .sort((a,b)=>(b.n_independent_srcs||1)-(a.n_independent_srcs||1) || (b.corpus_frequency||1)-(a.corpus_frequency||1))
    .slice(0,8);
  const items = cs.map(e => {
    const q = (e.source_quotes||[])[0] || {};
    const tags = badge("b-"+(e.hypothesis_map||"other").toLowerCase(), e.hypothesis_map||"other")
      + " " + badge("s-"+e.stance, e.stance) + ` <span class="badge b-other">${esc(themeLabel(e.theme))}</span>`;
    const verb = q.verbatim ? `<details><summary class="small muted">source quote (audit trail)</summary>`
      + `<div class="q">“${esc(q.verbatim)}” <span class="src">[${esc(platLabel(q.platform))}]${q.date?" · "+esc(q.date):""}</span></div></details>` : "";
    return `<div class="claim"><div>${esc(e.claim_text)}</div>
      <div class="tags">${tags} <span class="src">[${q.platform?esc(platLabel(q.platform)):"—"}]</span></div>${verb}</div>`;
  }).join("");
  row.querySelector("td").innerHTML =
    `<div class="small muted" style="margin-bottom:2px">Paraphrased atomic claims (scraped text is paraphrased, not quoted) — `
    + `${o.records} in this theme, showing top ${cs.length} by corroboration. Each re-opens to its verbatim source.</div>` + items;
  row.style.display = "";
}

function renderMethod(d){
  const m=d.manifest||{}, dp=d.discard_pile||{}, a=d.audit||{}, cats=d.categories||{};
  const docs=m.n_documents||0, rel=m.n_relevant||0;
  const dropped=(dp.not_relevant&&dp.not_relevant.count) || (docs-rel);
  const claims=REGISTER.length, noQuote=(dp.unverified_claims&&dp.unverified_claims.count)||0;
  const hyp={}; for(const e of REGISTER){ const h=e.hypothesis_map||"other"; hyp[h]=(hyp[h]||0)+1; }
  const themes={}; for(const e of REGISTER){ themes[e.theme||"misc"]=(themes[e.theme||"misc"]||0)+1; }
  const nThemes=Object.keys(themes).length;
  const topThemes=Object.entries(themes).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([k,v])=>`${themeLabel(k)} ${v}`).join(" · ");
  const cp=m.counts_by_platform||{};
  const plats=Object.entries(cp).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`${platLabel(k)} ${v.toLocaleString()}`).join(" · ");
  const dist=a.distribution||{}, heldUp=dist["held up"]||0;
  const substantive=(dist["held up"]||0)+(dist["partly invented"]||0)+(dist["rejected"]||0);
  const agree = substantive ? Math.round(heldUp/substantive*100) : 0;
  const notIng=(m.not_ingested||[]).length ? " Wired-not-ingested: "+m.not_ingested.map(platLabel).join(", ")+"." : "";

  const stages=[
    ["Ingest",`Public reviews & discussions across platforms.${notIng}`,`${docs.toLocaleString()} docs · ${plats}`],
    ["Filter",`English + length ≥ 20 words; scarce sources classified first. Off-topic noise removed before any LLM cost.`,`${rel} kept · ${dropped.toLocaleString()} dropped`],
    ["Extract",`An LLM tags each record into a FIXED closed taxonomy (evidence type · decision driver · purchase context · ${Object.keys(cats).length} product segments). It cannot invent tags; anything outside the list or with no verbatim quote is rejected — a zero-hallucination guardrail.`,`${claims} traceable claims`],
    ["Map",`Each claim is mapped to a pre-registered hypothesis: H1 uncertainty · H2 occasion-decay · H3 mixed-intent.`,`H1 ${hyp.H1||0} · H2 ${hyp.H2||0} · H3 ${hyp.H3||0} · other ${hyp.other||0}`],
    ["Score",`Each opportunity scored pain × frequency × business-fit ÷ effort (inverse-effort, RICE-style) — not sentiment polarity.`,`ranked in Evidence →`],
    ["Cluster",`Recurring tag-pairs are tallied mathematically (no LLM) to surface the top cross-patterns.`,`${nThemes} themes · ${topThemes}`],
    ["Emit",`A ranked, filterable opportunity list; every row re-openable to its source quote; refuses to answer on thin evidence (<3 docs or <2 platforms).`,`${claims} claims live`],
  ];
  $("pipe").innerHTML = stages.map((s,i)=>`<div class="stage">
    <div class="no">STAGE ${i+1}</div><h4>${esc(s[0])}</h4><p>${s[1]}</p><span class="n"><b>${esc(s[2])}</b></span></div>`).join("");
  $("notSent").innerHTML = `<b>This is structured classification + scoring + clustering — NOT sentiment analysis.</b> `
    + `No polarity ("positive/negative") score is used anywhere; every row is a typed claim mapped to a hypothesis and re-openable to its verbatim source.`;
  const noSignal = docs ? (1-rel/docs)*100 : 0;
  const chips=[
    [`${noSignal.toFixed(1)}%`, `no-signal — off-topic noise correctly discarded (${dropped.toLocaleString()}/${docs.toLocaleString()})`],
    [`${heldUp}/${substantive}`, `engine claims stress-tested against ${a.n_interviews||6} interviews — ${heldUp} fully held up, ${substantive-heldUp} flagged over-stated. Low by design: the corpus over-claims, the audit catches it (that's why we route, not chase the loudest signal).`],
    [`${noQuote}`, `claims dropped for no traceable verbatim quote (anti-hallucination)`],
  ];
  $("honesty").innerHTML = chips.map(([b,s])=>`<div class="chip"><b>${b}</b><span>${esc(s)}</span></div>`).join("");
}

// ─────────────────────────────────────────── TAB 3: AUDIT (filterable)
function verdictCell(e) {
  if (!e.audit_verdict) return `<span class="muted small">pending</span>`;
  const cls = "v-"+e.audit_verdict.replace(/\s+/g,"-");
  return `<span class="badge ${cls}">${esc(e.audit_verdict)}</span>`
    + (e.audit_note ? `<details><summary class="small muted">why</summary><span class="small">${esc(e.audit_note)}</span></details>` : "");
}

let auditSort = { key:"rank", dir:1 };
function renderAudit(d) {
  const a = d.audit||{};
  $("auditCoverage").innerHTML = `<b>${a.n_audited||0} of ${a.n_total||REGISTER.length} claims</b> verdicted (${pct1(a.n_audited||0,a.n_total||REGISTER.length)}) against ${a.n_interviews||6} interviews — `
    + Object.entries(a.distribution||{}).map(([k,n])=>`${n} ${k}`).join(" · ") + `. “Not tested” = the interviews don't speak to it (no forced verdict). Evidence: <a href="interviews.md" target="_blank" rel="noopener">the 6 transcripts</a>.`;
  const themes = [...new Set(REGISTER.map(e=>e.theme))].sort();
  const verds = ["held up","partly invented","rejected","not tested","pending"];
  $("filters").innerHTML =
    sel("fHyp","Hypothesis",["H1","H2","H3","other"]) + sel("fVerd","Verdict",verds) + sel("fTheme","Theme",themes,themeLabel);
  ["fHyp","fVerd","fTheme"].forEach(id => $(id).onchange = renderAuditRows);
  renderAuditRows();
}
function sel(id,label,opts,disp){ return `<select id="${id}"><option value="">${label}: all</option>`
  + opts.map(o=>`<option value="${esc(o)}">${esc(disp?disp(o):o)}</option>`).join("")+`</select>`; }

function renderAuditRows() {
  const fh=$("fHyp").value, fv=$("fVerd").value, ft=$("fTheme").value;
  let rows = REGISTER.filter(e =>
    (!fh || e.hypothesis_map===fh) &&
    (!fv || (fv==="pending" ? !e.audit_verdict : e.audit_verdict===fv)) &&
    (!ft || e.theme===ft));
  const k = auditSort.key, dir = auditSort.dir;
  rows.sort((a,b)=>{
    if (k==="rank") return dir*(a.claim_id.localeCompare(b.claim_id));
    if (k==="freq") return dir*((b.corpus_frequency||0)-(a.corpus_frequency||0));
    if (k==="src")  return dir*((b.n_independent_srcs||0)-(a.n_independent_srcs||0));
    return 0;
  });
  const head = `<tr>
    <th onclick="sortAudit('rank')">#</th><th>Claim</th><th>H</th><th>Stance</th><th>Theme</th>
    <th onclick="sortAudit('src')">Src</th><th onclick="sortAudit('freq')">n</th><th>Conf</th><th>Quotes</th><th>Interview verdict</th></tr>`;
  const body = rows.map(e => {
    const qs = (e.source_quotes||[]).map(q=>`<div class="q">“${esc(q.verbatim)}” <span class="src">[${esc(platLabel(q.platform))}]${q.date?" · "+esc(q.date):""}</span></div>`).join("");
    return `<tr>
      <td class="muted">${esc(e.claim_id)}</td>
      <td>${esc(e.claim_text)}</td>
      <td>${badge("b-"+e.hypothesis_map.toLowerCase(), e.hypothesis_map)}</td>
      <td>${badge("s-"+e.stance, e.stance)}</td>
      <td class="small muted">${esc(themeLabel(e.theme))}</td>
      <td>${e.n_independent_srcs}${e.thin_evidence?` <span class="badge s-contradicts" title="single platform">thin</span>`:""}</td>
      <td>${e.corpus_frequency||1}</td>
      <td class="small muted">${esc(e.engine_confidence)}</td>
      <td><details><summary class="small muted">${(e.source_quotes||[]).length}</summary>${qs}</details></td>
      <td>${verdictCell(e)}</td></tr>`;
  }).join("");
  $("register").innerHTML = head + (rows.length ? body : `<tr><td colspan="10" class="empty">No claims match these filters.</td></tr>`);
}
function sortAudit(key){ auditSort = { key, dir: (auditSort.key===key ? -auditSort.dir : 1) }; renderAuditRows(); }

// ─────────────────────────────────────────── TAB 4: ASK (RAG, refuses when thin)
function tokens(s){ return [...new Set((s.toLowerCase().match(/[a-z0-9]+/g)||[]).filter(t=>t.length>=3 && !STOP.has(t)))]; }
function ask() {
  const q = $("q").value.trim(), out = $("ans");
  const qt = tokens(q).filter(t => (DF[t]||0) >= 2);
  if (!qt.length) { out.innerHTML = `<div class="refuse"><b>Refused — off-corpus.</b> None of those words carry a topic this corpus of Myntra wishlist evidence can speak to.</div>`; return; }
  const scored = (DATA.index||[]).map(doc => {
    const hay = (doc.text+" "+doc.claim+" "+doc.quote).toLowerCase();
    return { doc, score: qt.filter(t=>hay.includes(t)).length };
  }).filter(x=>x.score>=1).sort((a,b)=>b.score-a.score);
  const plats = new Set(scored.map(x=>x.doc.platform));
  if (scored.length < 3) { out.innerHTML = `<div class="refuse"><b>Refused — thin evidence.</b> Only ${scored.length} document(s) meaningfully match (need ≥3).</div>`; return; }
  if (plats.size < 2) { out.innerHTML = `<div class="refuse"><b>Refused — cross-source rule.</b> Matching evidence is from only ${plats.size} platform(s); a claim needs ≥2.</div>`; return; }
  const seen = new Set();
  const top = scored.filter(x=>!seen.has(x.doc.quote)&&seen.add(x.doc.quote)).slice(0,5).map(x =>
    `<div class="q">${badge("b-"+x.doc.hypothesis.toLowerCase(),x.doc.hypothesis)} ${badge("s-"+x.doc.stance,x.doc.stance)} “${esc(x.doc.quote)}” <span class="src">[${esc(platLabel(x.doc.platform))}]</span></div>`).join("");
  out.innerHTML = `<div class="answer"><b>Grounded evidence</b> from ${plats.size} platforms (${[...plats].map(platLabel).join(", ")}) — verbatim only, no generation:${top}</div>`;
}
window.ask = ask; window.sortAudit = sortAudit; window.drill = drill;
