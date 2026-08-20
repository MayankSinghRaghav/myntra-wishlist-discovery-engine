"""
analyze.py — Step 3. Turn dual-hypothesis labels into a per-hypothesis, per-segment
report that can REJECT a hypothesis — not a single ranked winner.

Emits (all deck- and app-ready):
  data.json        frontend artifact: corpus/source stats, model-mix, the H1/H2/H3 x segment
                   matrix, "none" share, decisions, audit table, discard pile, retrieval index
  audit_table.csv  Claim | Sources | Doc count | 3 verbatim quotes | Verdict(blank)
  audit_table.md   same, screenshot-ready for the deck
  holdout_sample.csv + holdout_rubric.md   blind hold-out template (hand-coded later)
  findings.md      honest narrative (the split, decisions, discard pile, limits)

Thresholds are pre-registered in hypotheses.md and imported here, not tuned to the result.

Run:  python analyze.py -i classified_data.csv
      python analyze.py --selftest        # offline logic checks
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

import pandas as pd

from classify import HYPS, INTENT_SEGMENTS, TOPICS  # closed taxonomies — single source of truth

# ---- pre-registered decision rules (see hypotheses.md) ----------------------
SUPPORT_MIN = 0.15      # >= => supported overall (with >=2 sources)
REJECT_MAX = 0.08       # <  => rejected IF it also leads no segment
MIN_SOURCES = 2         # cross-source rule: a reported claim needs >=2 distinct sources
MIN_CLAIM_DOCS = 5      # a claim row needs at least this many documents
HEADLINE_TIE = 0.05     # overall shares within this band + no segment split => "no dominant mechanism"

HYP_NAME = {
    "h1": "H1 — uncertainty blocks conversion",
    "h2": "H2 — relevance decays",
    "h3": "H3 — wishlist ≠ purchase intent",
}
BOOL_COLS = ["is_relevant", "is_myntra_specific"] + [f"{h}_present" for h in HYPS]


# ---------------------------------------------------------------- io
def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in BOOL_COLS:
        df[c] = df[c].str.lower().isin({"true", "1", "yes"})
    for h in HYPS:
        df[f"{h}_conf"] = pd.to_numeric(df[f"{h}_conf"], errors="coerce").fillna(0.0)
    if "method" not in df:
        df["method"] = "gemini"
    return df


def _quotes(sub: pd.DataFrame, h: str, k: int = 3) -> list[dict]:
    """Up to k distinct verified spans for hypothesis h, preferring distinct sources."""
    out, seen_txt, seen_src = [], set(), set()
    pool = sub[sub[f"{h}_span"].str.len() > 0]
    for prefer_new_src in (True, False):        # first pass: spread across sources
        for _, r in pool.iterrows():
            q = r[f"{h}_span"].strip()
            if q in seen_txt:
                continue
            if prefer_new_src and r["source"] in seen_src:
                continue
            out.append({"quote": q, "source": r["source"], "url": r["url"], "doc_id": r["doc_id"]})
            seen_txt.add(q)
            seen_src.add(r["source"])
            if len(out) >= k:
                return out
    return out


def _decide(overall: float, leads_any_segment: bool) -> str:
    if overall >= SUPPORT_MIN:
        return "supported"
    if overall < REJECT_MAX and not leads_any_segment:
        return "rejected"
    return "partial"


# ---------------------------------------------------------------- core
def analyze(df: pd.DataFrame) -> dict:
    rel = df[df["is_relevant"]].copy()
    n_rel = len(rel)
    segs = sorted(INTENT_SEGMENTS)

    seg_totals = {s: int((rel["intent_segment"] == s).sum()) for s in segs}

    # which hypothesis leads each segment (by within-segment evidence share)
    seg_leader: dict[str, str] = {}
    for s in segs:
        sub = rel[rel["intent_segment"] == s]
        if len(sub):
            shares = {h: float(sub[f"{h}_present"].mean()) for h in HYPS}
            top = max(shares, key=shares.get)
            seg_leader[s] = top if shares[top] > 0 else ""
        else:
            seg_leader[s] = ""

    hyps: dict[str, dict] = {}
    for h in HYPS:
        ev = rel[rel[f"{h}_present"]]
        overall = float(len(ev) / n_rel) if n_rel else 0.0
        by_seg = {}
        for s in segs:
            seg_sub = rel[rel["intent_segment"] == s]
            seg_ev = seg_sub[seg_sub[f"{h}_present"]]
            by_seg[s] = {
                "docs": int(len(seg_ev)),
                "share": round(float(len(seg_ev) / len(seg_sub)), 4) if len(seg_sub) else 0.0,
                "sources": sorted(seg_ev["source"].unique().tolist()),
                "leads": seg_leader.get(s) == h,
            }
        leads_any = any(v["leads"] and v["docs"] >= MIN_CLAIM_DOCS for v in by_seg.values())
        srcs = sorted(ev["source"].unique().tolist())
        hyps[h] = {
            "name": HYP_NAME[h],
            "docs": int(len(ev)),
            "overall_share": round(overall, 4),
            "sources": srcs,
            "n_sources": len(srcs),
            "mean_conf": round(float(ev[f"{h}_conf"].mean()), 3) if len(ev) else 0.0,
            "by_segment": by_seg,
            "decision": _decide(overall, leads_any),
            "cross_source_ok": len(srcs) >= MIN_SOURCES,
            "quotes": _quotes(ev, h),
        }

    none_mask = ~(rel["h1_present"] | rel["h2_present"] | rel["h3_present"])
    none_share = float(none_mask.mean()) if n_rel else 0.0

    price_mask = (rel["intent_segment"] == "price_watch") | (rel["topic"] == "price_value")
    price_share = float(price_mask.mean()) if n_rel else 0.0

    method_mix = df["method"].value_counts().to_dict()
    ai_share = float((df["method"] == "gemini").mean()) if len(df) else 0.0

    # headline: is there a dominant mechanism, or a genuine split?
    shares = {h: hyps[h]["overall_share"] for h in HYPS}
    spread = max(shares.values()) - min(shares.values()) if shares else 0.0
    split = {s: seg_leader[s] for s in segs if seg_leader[s] and seg_totals[s] >= MIN_CLAIM_DOCS}
    distinct_leaders = len(set(split.values()))
    if spread < HEADLINE_TIE and distinct_leaders <= 1:
        headline = "No dominant mechanism — H1/H2/H3 shares are within the pre-registered tie band."
    else:
        parts = [f"{seg_leader[s].upper()} leads {s}" for s in split]
        headline = "Split result — " + "; ".join(parts) if parts else "See per-segment matrix."

    return {
        "corpus": {
            "n_total": int(len(df)),
            "n_relevant": n_rel,
            "n_myntra_specific": int(rel["is_myntra_specific"].sum()),
            "sources": {s: int(c) for s, c in df["source"].value_counts().items()},
            "n_sources": int(df["source"].nunique()),
        },
        "model_mix": {"counts": method_mix, "ai_share": round(ai_share, 4)},
        "segments": {s: seg_totals[s] for s in segs},
        "hypotheses": hyps,
        "none_share": round(none_share, 4),
        "none_docs": int(none_mask.sum()),
        "price_sanity": {"price_share": round(price_share, 4),
                         "non_price_share": round(1 - price_share, 4)},
        "headline": headline,
        "seg_leader": seg_leader,
    }


# ---------------------------------------------------------------- audit table
def build_audit_table(rep: dict, rel: pd.DataFrame) -> list[dict]:
    """One row per reportable claim: overall (supported/partial) + segment-leading cells.
    Verdict is left blank — Cowork fills Held up / Partly invented / Rejected post-interviews."""
    rows: list[dict] = []

    def _row(claim, sub, h, sources, docs):
        qs = _quotes(sub, h, 3)
        rows.append({
            "claim": claim,
            "sources": ", ".join(sources),
            "doc_count": int(docs),
            "quote_1": qs[0]["quote"] if len(qs) > 0 else "",
            "quote_2": qs[1]["quote"] if len(qs) > 1 else "",
            "quote_3": qs[2]["quote"] if len(qs) > 2 else "",
            "cross_source_ok": len(sources) >= MIN_SOURCES,
            "verdict": "",   # filled after primary research
        })

    for h in HYPS:
        H = rep["hypotheses"][h]
        if H["decision"] in ("supported", "partial") and H["docs"] >= MIN_CLAIM_DOCS \
                and H["cross_source_ok"]:
            ev = rel[rel[f"{h}_present"]]
            _row(f"{H['name']} (overall, {H['overall_share']*100:.0f}% of relevant, {H['decision']})",
                 ev, h, H["sources"], H["docs"])
        for s, cell in H["by_segment"].items():
            if cell["leads"] and cell["docs"] >= MIN_CLAIM_DOCS and len(cell["sources"]) >= MIN_SOURCES:
                sub = rel[(rel["intent_segment"] == s) & (rel[f"{h}_present"])]
                _row(f"{HYP_NAME[h]} LEADS the '{s}' segment ({cell['share']*100:.0f}% of it)",
                     sub, h, cell["sources"], cell["docs"])
    return rows


def discard_pile(df: pd.DataFrame, rep: dict, rel: pd.DataFrame) -> dict:
    none_docs = rel[~(rel["h1_present"] | rel["h2_present"] | rel["h3_present"])]
    # single-source / sub-min hypothesis-segment cells that were NOT promoted to a claim
    weak = []
    for h in HYPS:
        for s, cell in rep["hypotheses"][h]["by_segment"].items():
            if 0 < cell["docs"] < MIN_CLAIM_DOCS or (cell["docs"] and len(cell["sources"]) < MIN_SOURCES):
                weak.append({"hypothesis": h, "segment": s, "docs": cell["docs"],
                             "sources": cell["sources"], "why": "sub-min-docs or single-source"})
    return {
        "not_relevant": {"count": int((~df["is_relevant"]).sum())},
        "none_hypothesis": {"count": int(len(none_docs)),
                            "samples": none_docs["raw_text"].str[:160].head(8).tolist()},
        "weak_cells": weak,
    }


def build_index(rel: pd.DataFrame, cap: int = 4000) -> list[dict]:
    """Client-side RAG index: relevant docs with a display quote + search text."""
    out = []
    for _, r in rel.head(cap).iterrows():
        quote = next((r[f"{h}_span"] for h in HYPS if r[f"{h}_span"].strip()), "")
        out.append({
            "doc_id": r["doc_id"], "source": r["source"], "url": r["url"],
            "segment": r["intent_segment"],
            "hyps": [h for h in HYPS if r[f"{h}_present"]],
            "quote": (quote or r["raw_text"][:160]).strip(),
            "text": r["raw_text"][:240],
        })
    return out


# ---------------------------------------------------------------- writers
def write_audit(rows: list[dict], csv_path: str, md_path: str) -> None:
    cols = ["claim", "sources", "doc_count", "quote_1", "quote_2", "quote_3",
            "cross_source_ok", "verdict"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    L = ["# Audit table — AI-surfaced claims for primary-research verification\n",
         "_Verdict is filled AFTER interviews/survey: Held up / Partly invented / Rejected._\n\n",
         "| Claim | Sources | Docs | Sample verbatim quotes | Verdict |\n",
         "|---|---|---|---|---|\n"]
    for r in rows:
        qs = " <br> ".join(f"“{r[q]}”" for q in ("quote_1", "quote_2", "quote_3") if r[q])
        L.append(f"| {r['claim']} | {r['sources']} | {r['doc_count']} | {qs} | {r['verdict'] or '_(pending)_'} |\n")
    open(md_path, "w", encoding="utf-8").write("".join(L))


def write_holdout(rel: pd.DataFrame, n: int = 60) -> None:
    """Deterministic blind sample (every Nth relevant row) with blank hypothesis columns."""
    step = max(1, len(rel) // n)
    sample = rel.iloc[::step].head(n)
    cols = ["doc_id", "source", "raw_text"]
    with open("holdout_sample.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols + ["h1_present", "h2_present", "h3_present", "intent_segment"])
        for _, r in sample.iterrows():
            w.writerow([r["doc_id"], r["source"], r["raw_text"], "", "", "", ""])
    open("holdout_rubric.md", "w", encoding="utf-8").write(
        "# Blind hold-out coding rubric\n\n"
        f"Hand-code the {len(sample)} rows in `holdout_sample.csv` against the SAME rules as "
        "hypotheses.md, WITHOUT looking at the model's labels. Fill h1/h2/h3_present (true/false) "
        "and intent_segment, then compare to the model to report one plain agreement number.\n\n"
        "- **H1** unresolved doubt (fit/size/quality/authenticity/styling/social) on a wanted item.\n"
        "- **H2** relevance lapsed (occasion passed, forgot, bought elsewhere).\n"
        "- **H3** the save was never a buy signal (mood-board/price-watch/browse/size-hold).\n"
        "- A row may be true on several, one, or none.\n"
        f"- intent_segment ∈ {sorted(INTENT_SEGMENTS)}\n")


def write_findings(rep: dict, audit: list[dict], discard: dict, path: str = "findings.md") -> None:
    c = rep["corpus"]
    L = ["# Findings — Myntra Wishlist→Purchase Discovery Engine (Attempt 3)\n\n",
         "_Pre-registered hypotheses (see `hypotheses.md`), coded independently per document. "
         "This is a hypothesis generator over complaint-skewed public text, NOT proof. "
         "Every claim is for primary research to confirm or kill (see `audit_table.md`)._\n\n",
         f"## Headline\n**{rep['headline']}**\n\n",
         "> Note: this engine does not emit a single ranked “opportunity score.” The unit of "
         "output is per-hypothesis evidence share, reported per intent-segment.\n\n",
         "## Corpus & model mix\n",
         f"- {c['n_total']} texts; **{c['n_relevant']} relevant**; {c['n_sources']} sources: {c['sources']}\n",
         f"- Model mix: {rep['model_mix']['counts']} — **{rep['model_mix']['ai_share']*100:.1f}% AI**, "
         "remainder rule-based fallback (logged, never counted as AI).\n",
         f"- Price sanity (not the headline): {rep['price_sanity']['price_share']*100:.0f}% price / "
         f"{rep['price_sanity']['non_price_share']*100:.0f}% non-price.\n\n",
         "## Hypotheses (overall)\n",
         "| Hypothesis | Docs | Share | Sources | ≥2 sources | Decision |\n|---|---|---|---|---|---|\n"]
    for h in HYPS:
        H = rep["hypotheses"][h]
        L.append(f"| {H['name']} | {H['docs']} | {H['overall_share']*100:.1f}% | {H['n_sources']} | "
                 f"{'yes' if H['cross_source_ok'] else 'NO'} | **{H['decision']}** |\n")
    L.append(f"\n- **“None” (no hypothesis) share: {rep['none_share']*100:.1f}%** "
             f"({rep['none_docs']} docs) — tracked, not hidden.\n\n")

    L.append("## Per-segment split (H-share within each intent segment)\n")
    L.append("| Segment | n | H1 | H2 | H3 | leads |\n|---|---|---|---|---|---|\n")
    for s, tot in rep["segments"].items():
        cells = {h: rep["hypotheses"][h]["by_segment"][s]["share"] for h in HYPS}
        lead = rep["seg_leader"].get(s, "") or "—"
        L.append(f"| {s} | {tot} | {cells['h1']*100:.0f}% | {cells['h2']*100:.0f}% | "
                 f"{cells['h3']*100:.0f}% | {lead} |\n")

    L.append("\n## Audit table (for primary research)\n")
    L.append(f"{len(audit)} claims exported to `audit_table.md` — Verdict pending interviews.\n\n")
    L.append("## Discard pile (shown for honesty)\n")
    L.append(f"- Not relevant: {discard['not_relevant']['count']} rows.\n")
    L.append(f"- Supported no hypothesis (“none”): {discard['none_hypothesis']['count']} rows.\n")
    L.append(f"- Weak/single-source hypothesis-segment cells not promoted to claims: "
             f"{len(discard['weak_cells'])}.\n\n")
    L.append("## Limitations\n"
             "- Complaint-skewed: reviews over-represent the frustrated; shares are complaint-share, "
             "not user prevalence.\n- English-biased collection (`lang=en`).\n"
             "- App/forum text is a PROXY for the wishlist funnel — every link is a hypothesis.\n"
             "- Blind hold-out agreement is reported once in the deck after hand-coding "
             "`holdout_sample.csv`.\n")
    open(path, "w", encoding="utf-8").write("".join(L))


# ---------------------------------------------------------------- selftest
def _fake_rel() -> pd.DataFrame:
    rows = []
    def add(doc, src, seg, h1, h2, h3, s1="", s2="", s3=""):
        rows.append({"doc_id": doc, "source": src, "url": "u", "raw_text": f"{s1} {s2} {s3} text",
                     "is_relevant": True, "is_myntra_specific": True, "intent_segment": seg,
                     "h1_present": h1, "h1_conf": 0.8 if h1 else 0.0, "h1_span": s1,
                     "h2_present": h2, "h2_conf": 0.8 if h2 else 0.0, "h2_span": s2,
                     "h3_present": h3, "h3_conf": 0.8 if h3 else 0.0, "h3_span": s3,
                     "topic": "fit_uncertainty", "evidence_strength": "explicit", "method": "gemini"})
    # deferred_purchase: H1-heavy across 2 sources; mood_board: H3-heavy across 2 sources
    for i in range(6):
        add(f"d{i}", "google_play" if i % 2 else "reddit", "deferred_purchase", True, False, False, s1="not sure of size")
    for i in range(6):
        add(f"m{i}", "youtube" if i % 2 else "reddit", "mood_board", False, False, True, s3="just for inspo")
    add("none1", "reddit", "unclear", False, False, False)   # a real "none"
    return pd.DataFrame(rows)


def _selftest() -> None:
    assert _decide(0.2, False) == "supported"
    assert _decide(0.05, False) == "rejected"
    assert _decide(0.05, True) == "partial"      # leads a segment => not rejected
    assert _decide(0.10, False) == "partial"
    rel = _fake_rel()
    df = rel.copy()
    df.loc[len(df)] = {**{c: "" for c in df.columns}, "doc_id": "irr", "source": "reddit",
                       "raw_text": "app crashed", "is_relevant": False, "is_myntra_specific": False,
                       "intent_segment": "unclear", "h1_present": False, "h2_present": False,
                       "h3_present": False, "h1_conf": 0.0, "h2_conf": 0.0, "h3_conf": 0.0,
                       "topic": "other", "evidence_strength": "weak_inference", "method": "gemini"}
    rep = analyze(df)
    assert rep["seg_leader"]["deferred_purchase"] == "h1", rep["seg_leader"]
    assert rep["seg_leader"]["mood_board"] == "h3", rep["seg_leader"]
    assert rep["none_docs"] == 1 and rep["none_share"] > 0     # "none" tracked
    assert "Split" in rep["headline"]                          # split, not a single winner
    audit = build_audit_table(rep, df[df["is_relevant"]])
    assert audit and all(r["cross_source_ok"] for r in audit)  # every claim clears >=2 sources
    assert all(r["verdict"] == "" for r in audit)              # verdict pending
    d = discard_pile(df, rep, df[df["is_relevant"]])
    assert d["not_relevant"]["count"] == 1 and d["none_hypothesis"]["count"] == 1
    print("selftest OK")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Dual-hypothesis analysis -> data.json + audit table")
    ap.add_argument("-i", "--input", default="classified_data.csv")
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    df = load(args.input)
    rel = df[df["is_relevant"]].copy()
    print(f"Loaded {len(df)} rows; {len(rel)} relevant.", file=sys.stderr)

    rep = analyze(df)
    audit = build_audit_table(rep, rel)
    discard = discard_pile(df, rep, rel)
    rep["audit_table"] = audit
    rep["discard_pile"] = discard
    rep["index"] = build_index(rel)

    import os
    os.makedirs(os.path.dirname(args.data) or ".", exist_ok=True)
    with open(args.data, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False)
    write_audit(audit, "audit_table.csv", "audit_table.md")
    write_holdout(rel)
    write_findings(rep, audit, discard)
    print(f"Wrote {args.data} ({len(rep['index'])} indexed), audit_table.* ({len(audit)} claims), "
          f"holdout_sample.csv, findings.md")
    print(f"HEADLINE: {rep['headline']}")


if __name__ == "__main__":
    main()
