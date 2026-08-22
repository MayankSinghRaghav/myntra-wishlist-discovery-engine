"""
analyze.py — Stages 5-7 (Score, Cluster, Emit). Turn atomic claims into a RANKED CLAIM REGISTER
with per-claim provenance and stance, plus a corpus manifest and a pre-interview early-signal note.

Diagnosis only. This engine surfaces evidence and STOPS — it never proposes, ranks, or hints at a
solution/feature (build-spec hard prohibition #1). Contradicting claims are kept, not collapsed.

Emits:
  claims_register.json   ranked atomic claims: hypothesis_map, stance, source_quotes[],
                         n_independent_srcs, inferred_segment, engine_confidence, thin_evidence,
                         audit_verdict/audit_note (BLANK — filled later from blind interviews)
  corpus_manifest.json   honest source counts by platform + date range (slide-3 corpus size)
  early_signal.md        pre-interview, corpus-only lean per hypothesis + segment signal for the screener
  data.json              dashboard artifact (register + manifest + lean + discard + RAG index)

Run:  python analyze.py -i claims.csv
      python analyze.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from difflib import SequenceMatcher

from classify import HYPOTHESES  # closed set, single source of truth

SIM = 0.55          # difflib similarity to merge two atomic claims into one register entry
# (0.60 missed a confirmed real cross-platform paraphrase at 0.579 while the "must not merge"
# opposite-polarity regression case sits at 0.386 -- 0.55 keeps a safety margin on both sides)
MAX_QUOTES = 5      # source_quotes per register entry
HYP_LABEL = {"h1": "H1", "h2": "H2", "h3": "H3", "other": "other"}
HYP_NAME = {
    "h1": "H1 — purchase-time uncertainty stalls still-wanted items",
    "h2": "H2 — relevance decays inside the 30-day window",
    "h3": "H3 — wishlist add ≠ purchase intent",
    "other": "other / unmapped",
}


# ---------------------------------------------------------------- io
def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


# ---------------------------------------------------------------- clustering
# Closed domain theme taxonomy — a claim is bucketed by its first matching theme (order matters).
# Keyword themes cluster robustly across paraphrase where char-similarity fails; keyword-less
# claims fall back to difflib. Themes never cross (hypothesis, stance) boundaries.
import re as _re  # noqa: E402

THEME_KEYWORDS = [
    ("fit_size", _re.compile(r"\b(fit|fitting|size|sizing|true to size|size chart|too (small|big|tight|loose)|runs (small|big))\b", _re.I)),
    ("quality", _re.compile(r"\b(quality|material|fabric|cheap|flimsy|thin|wash|shrink|shrunk|pilling|stitch)\b", _re.I)),
    ("authenticity", _re.compile(r"\b(original|authentic|genuine|fake|first copy|duplicate)\b", _re.I)),
    ("returns_delivery", _re.compile(r"\b(return|refund|exchange|replace|delivery|damaged|wrong (product|item)|defect)\b", _re.I)),
    ("price_watch", _re.compile(r"\b(sale|offer|discount|price|cheaper|coupon|deal|wait(ing)? for)\b", _re.I)),
    ("inspiration", _re.compile(r"\b(inspo|inspiration|aspir|mood ?board|dream|someday|wishlist goals)\b", _re.I)),
    ("comparison", _re.compile(r"\b(compar|shortlist|options|versus|\bvs\b|decide between)\b", _re.I)),
    ("bookmark", _re.compile(r"\b(save (for )?later|see later|bookmark|remember|for later|note down)\b", _re.I)),
    ("forgot", _re.compile(r"\b(forgot|forget|slipped my mind|lost track)\b", _re.I)),
    ("occasion", _re.compile(r"\b(occasion|wedding|festival|diwali|party|trip|event|birthday|function)\b", _re.I)),
    ("season_trend", _re.compile(r"\b(season|summer|winter|monsoon|trend|dated|out of style)\b", _re.I)),
]


def theme_of(row: dict) -> str:
    hay = f"{row['claim_text']} {row['quote']}"
    for name, rx in THEME_KEYWORDS:
        if rx.search(hay):
            return name
    return "misc"


def cluster(items: list[dict], threshold: float = SIM) -> list[list[dict]]:
    """difflib fallback for keyword-less ('misc') claims within one (hypothesis, stance) group."""
    clusters: list[list[dict]] = []
    seeds: list[str] = []
    for it in items:
        t = _norm(it["claim_text"])
        placed = False
        for i, seed in enumerate(seeds):
            if SequenceMatcher(None, t, seed).ratio() >= threshold:
                clusters[i].append(it)
                placed = True
                break
        if not placed:
            clusters.append([it])
            seeds.append(t)
    return clusters


def _representative(members: list[dict]) -> str:
    """Medoid claim_text — the member most similar to the rest (most representative wording)."""
    if len(members) == 1:
        return members[0]["claim_text"]
    texts = [m["claim_text"] for m in members]
    norms = [_norm(t) for t in texts]
    best, best_score = texts[0], -1.0
    for i, ni in enumerate(norms):
        score = sum(SequenceMatcher(None, ni, nj).ratio() for j, nj in enumerate(norms) if i != j)
        if score > best_score:
            best, best_score = texts[i], score
    return best


def _quotes(members: list[dict]) -> list[dict]:
    out, seen = [], set()
    for pref_new_platform in (True, False):
        plats = {q["platform"] for q in out}
        for m in members:
            q = m["quote"].strip()
            if not q or q in seen:
                continue
            if pref_new_platform and m["source"] in plats:
                continue
            out.append({"verbatim": q, "url": m["url"], "platform": m["source"],
                        "date": m["posted_date"]})
            seen.add(q)
            if len(out) >= MAX_QUOTES:
                return out
    return out


def _confidence(n_srcs: int, freq: int) -> tuple[str, str]:
    basis = f"{freq} passage(s) across {n_srcs} independent platform(s)"
    if n_srcs >= 2 and freq >= 5:
        return "high", basis
    if n_srcs >= 2 or freq >= 3:
        return "med", basis
    return "low", basis


def _segment(members: list[dict]) -> dict | None:
    cats = [m["category"] for m in members if m["category"] and m["category"] != "other"]
    if not cats:
        return None
    top = max(set(cats), key=cats.count)
    return {"category": top}  # age_band / geo not reliably inferable from public text -> omitted


# ---------------------------------------------------------------- build register
def build_register(claim_rows: list[dict]) -> list[dict]:
    # cluster key = (hypothesis, stance, theme). Theme narrows the pool (so unrelated topics
    # never merge); difflib similarity within that pool decides which claims are truly the SAME
    # atomic statement. A shared theme keyword (e.g. "quality") does NOT make two claims the same
    # claim — "quality was outstanding" and "quality was extremely poor" must stay separate entries.
    by_group: dict[tuple, list[dict]] = {}
    for r in claim_rows:
        by_group.setdefault((r["hypothesis"], r["stance"], theme_of(r)), []).append(r)

    entries = []
    for (hyp, stance, theme), rows in by_group.items():
        groups = cluster(rows)
        for members in groups:
            srcs = sorted({m["source"] for m in members})
            freq = len(members)
            conf, basis = _confidence(len(srcs), freq)
            entries.append({
                "claim_text": _representative(members),
                "hypothesis_map": HYP_LABEL.get(hyp, "other"),
                "stance": stance,
                "theme": theme,
                "source_quotes": _quotes(members),
                "n_independent_srcs": len(srcs),
                "inferred_segment": _segment(members),
                "engine_confidence": conf,
                "confidence_basis": basis,
                "thin_evidence": len(srcs) < 2,
                "corpus_frequency": freq,
                "audit_verdict": "",   # filled later from blind interviews
                "audit_note": "",
            })

    rank = {"high": 0, "med": 1, "low": 2}
    entries.sort(key=lambda e: (rank[e["engine_confidence"]], -e["corpus_frequency"],
                                -e["n_independent_srcs"]))
    for i, e in enumerate(entries, 1):
        e["claim_id"] = f"C{i:03d}"
    return [{"claim_id": e.pop("claim_id"), **e} for e in entries]


# ---------------------------------------------------------------- primary-research overlay
# INTERVIEW VERDICTS are NOT corpus output — they are results from the 6 primary interviews, entered
# here so the tool shows corpus signal and interview verdict together (the corpus proposes; the
# interviews decide). The corpus's loudest hypothesis (H1) was REJECTED as the primary blocker.
INTERVIEW = {
    "n_interviews": 6,
    "h1": {"verdict": "Rejected as primary blocker", "strength": "rejected",
           "detail": "0 of 6 interviews named fit/size/quality/return as the deciding reason a saved item went unbought"},
    "h2": {"verdict": "Supported", "strength": "strong",
           "detail": "occasion/relevance decay confirmed — Sneha's wedding passed, Aarav's trip decayed; 'occasion passed' was the most common survey reason (bigger than the prior expected)"},
    "h3": {"verdict": "Strongly supported", "strength": "strong",
           "detail": "two flavours — pure inspiration (Riya, off-app trigger) + comparison-shortlisting (Kunal): item-level non-conversion is correct behaviour, so the denominator is contaminated"},
    # findings the interviews surfaced OUTSIDE the three hypotheses (flagged, not structural calls)
    "additional": [
        {"label": "Price (the barred lever)", "detail": "the two clearest real-intent cases (Aarav, Rahul) were both blocked by price and both asked for a target-price alert — the one lever the brief forbids"},
        {"label": "Forgetting / attention", "detail": "Priya (and Riya) simply forgot — a Stage-1 re-exposure failure distinct from H2's relevance decay; the item stays relevant, the user never returns"},
    ],
}

# pre-purchase uncertainty vs post-purchase grievance — the H1 re-cut lives in reclassify_h1.py
# (a standalone, reproducible pass). analyze.py delegates to it so there is ONE classifier.
import reclassify_h1  # noqa: E402

# Per-claim audit of the top-30 claims against the n=6 interviews lives in interview_audit.py
# (explicit, transcript-grounded coding). analyze.py delegates so there is one coded source of truth.
import interview_audit  # noqa: E402


def apply_interview_audit(register: list[dict]) -> dict:
    return interview_audit.apply(register)


# ---------------------------------------------------------------- manifest / lean / discard
def corpus_manifest(rows: list[dict]) -> dict:
    docs = {r["doc_id"]: r for r in rows}                      # last row per doc; is_relevant stable
    by_platform: dict[str, int] = {}
    for d in docs.values():
        by_platform[d["source"]] = by_platform.get(d["source"], 0) + 1
    dates = sorted(d["posted_date"] for d in docs.values() if d["posted_date"])
    n_rel = sum(1 for d in docs.values() if str(d["is_relevant"]).lower() in {"true", "1"})
    return {
        "n_documents": len(docs),
        "n_relevant": n_rel,
        "platforms": sorted(by_platform),
        "n_independent_platforms": len(by_platform),
        "counts_by_platform": by_platform,
        "date_range": {"earliest": dates[0] if dates else None,
                       "latest": dates[-1] if dates else None},
        "not_ingested": ["apple_app_store", "x_twitter", "quora"],  # honest: wired-or-planned, thin
    }


def hypothesis_lean(claim_rows: list[dict]) -> dict:
    lean = {h: {"supports": 0, "contradicts": 0, "neutral": 0} for h in HYPOTHESES}
    for r in claim_rows:
        if r["hypothesis"] in lean and r["stance"] in lean[r["hypothesis"]]:
            lean[r["hypothesis"]][r["stance"]] += 1
    for h, d in lean.items():
        d["net"] = d["supports"] - d["contradicts"]
        d["total"] = d["supports"] + d["contradicts"] + d["neutral"]
    return lean


def category_signal(claim_rows: list[dict]) -> dict:
    cats: dict[str, int] = {}
    for r in claim_rows:
        c = r["category"]
        if c and c != "other":
            cats[c] = cats.get(c, 0) + 1
    return dict(sorted(cats.items(), key=lambda kv: -kv[1]))


def discard_pile(rows: list[dict], claim_rows: list[dict], register: list[dict]) -> dict:
    docs = {r["doc_id"]: r for r in rows}
    not_rel = [d for d in docs.values() if str(d["is_relevant"]).lower() not in {"true", "1"}]
    unverified = [r for r in claim_rows if not r["quote"].strip()]  # claim w/o traceable quote (#4)
    thin = [e for e in register if e["thin_evidence"]]
    return {
        "not_relevant": {"count": len(not_rel)},
        "unverified_claims": {"count": len(unverified),
                              "samples": [r["claim_text"] for r in unverified[:8]]},
        "thin_single_source_claims": {"count": len(thin)},
    }


def build_index(claim_rows: list[dict], cap: int = 4000) -> list[dict]:
    out = []
    for r in claim_rows[:cap]:
        if not r["quote"].strip():
            continue
        out.append({"claim": r["claim_text"], "quote": r["quote"], "platform": r["source"],
                    "url": r["url"], "hypothesis": HYP_LABEL.get(r["hypothesis"], "other"),
                    "stance": r["stance"], "text": (r["claim_text"] + " " + r["quote"])[:240]})
    return out


# ---------------------------------------------------------------- early_signal.md
def write_early_signal(lean: dict, cats: dict, manifest: dict, register: list[dict],
                       path: str = "early_signal.md") -> None:
    L = ["# Early signal — corpus-only, PRE-INTERVIEW (not conclusions)\n\n",
         "_Generated from public-evidence claims BEFORE any interview was coded. This is a lean and a\n"
         "screener input, NOT a verdict. Every claim here is audited per-claim against blind interviews\n"
         "(deck slide 4). No solution is proposed — the engine surfaces evidence and stops._\n\n",
         f"Corpus: **{manifest['n_documents']} documents**, {manifest['n_relevant']} relevant, across "
         f"**{manifest['n_independent_platforms']} independent platforms** {manifest['platforms']}. "
         f"{len(register)} distinct claims in the register.\n\n",
         "## Hypothesis lean (supports vs contradicts, claim counts)\n",
         "| Hypothesis | supports | contradicts | neutral | net |\n|---|---|---|---|---|\n"]
    for h in ("h1", "h2", "h3", "other"):
        d = lean[h]
        L.append(f"| {HYP_NAME[h]} | {d['supports']} | {d['contradicts']} | {d['neutral']} | "
                 f"{d['net']:+d} |\n")
    L.append("\n_Net = supports − contradicts. A large **contradicts** count is the engine helping to "
             "KILL a hypothesis — that is a finding, not noise. Counts are complaint-skewed public "
             "text, not user prevalence._\n\n")
    L.append("## Segment signal for the interview screener (product-category concentration)\n")
    if cats:
        for c, n in list(cats.items())[:8]:
            L.append(f"- **{c}**: {n} claims\n")
        top = next(iter(cats))
        L.append(f"\n**Screener recommendation (pre-interview):** over-sample recent wishlist users in "
                 f"the **{top}** category, where the corpus signal concentrates. Age/geo are not "
                 f"reliably inferable from public text — recruit those open.\n")
    else:
        L.append("- No reliable category concentration in the corpus yet — recruit category-open.\n")
    L.append("\n_Caveat: pre-interview, corpus-only. Do not treat lean as proof; the audit table "
             "(slide 4) sets each claim's verdict from primary research._\n")
    open(path, "w", encoding="utf-8").write("".join(L))


# ---------------------------------------------------------------- selftest
def _fake() -> list[dict]:
    def row(doc, src, ct, hyp, stance, quote, cat="", rel="True"):
        plat = {"reddit": "reddit_post", "youtube": "youtube_comment", "google_play": "android_app_review"}[src]
        return {"claim_id": f"{doc}#0", "doc_id": doc, "source": src, "platform": plat,
                "url": f"http://{doc}", "posted_date": "2026-03-01", "is_relevant": rel,
                "claim_text": ct, "hypothesis": hyp, "stance": stance, "quote": quote,
                "category": cat, "method": "gemini"}
    return [
        row("d1", "reddit", "not sure about the size", "h1", "supports", "not sure about the size", "ethnic"),
        row("d2", "google_play", "not sure about the size either", "h1", "supports", "not sure about the size", "ethnic"),
        # same theme (quality) + same (hypothesis, stance) as d7, but NOT the same claim —
        # regression case for the bug where a whole theme bucket was merged into one entry
        row("d3", "youtube", "i always end up buying what i wishlist", "h3", "contradicts", "always buying what i wishlist"),
        row("d4", "reddit", "just saving these for inspiration", "h3", "supports", "saving these for inspiration"),
        row("d5", "reddit", "claim with no quote", "h2", "supports", ""),   # unverified -> discard
        row("d7", "google_play", "quality was extremely poor", "h1", "supports", "quality was extremely poor", "ethnic"),
        row("d8", "google_play", "quality was outstanding and product matched the photos exactly",
            "h1", "supports", "quality was outstanding", "ethnic"),   # mislabelled by the classifier,
        # but must NOT merge with d7 just because both are H1/supports/theme=quality
        {"claim_id": "d6#0", "doc_id": "d6", "source": "reddit", "platform": "reddit_post",
         "url": "u", "posted_date": "", "is_relevant": "False", "claim_text": "", "hypothesis": "",
         "stance": "", "quote": "", "category": "", "method": "gemini"},   # not-relevant marker
    ]


def _selftest() -> None:
    rows = _fake()
    claim_rows = [r for r in rows if r["claim_text"]]
    shippable = [r for r in claim_rows if r["quote"].strip()]
    reg = build_register(shippable)
    # the two near-identical "not sure about the size" H1/supports claims merge into ONE entry
    fit = [e for e in reg if e["hypothesis_map"] == "H1" and e["theme"] == "fit_size"]
    assert len(fit) == 1 and fit[0]["n_independent_srcs"] == 2 and not fit[0]["thin_evidence"], fit
    # d7 (poor quality) and d8 (outstanding quality) share theme+hypothesis+stance but are NOT
    # the same claim -> must stay as SEPARATE entries, not collapsed into one blob (regression)
    quality = [e for e in reg if e["hypothesis_map"] == "H1" and e["theme"] == "quality"]
    assert len(quality) == 2, quality
    assert all(e["corpus_frequency"] == 1 for e in quality), quality
    # supports and contradicts on H3 stay SEPARATE entries (never collapsed)
    h3 = sorted([e for e in reg if e["hypothesis_map"] == "H3"], key=lambda e: e["stance"])
    assert [e["stance"] for e in h3] == ["contradicts", "supports"], h3
    assert all(e["audit_verdict"] == "" for e in reg)          # verdict blank
    assert all(e["source_quotes"] for e in reg)                # every shipped claim traceable
    lean = hypothesis_lean(claim_rows)
    assert lean["h3"]["contradicts"] == 1 and lean["h3"]["supports"] == 1
    man = corpus_manifest(rows)   # d1-d5,d7,d8 relevant (d5 relevant but its claim is unverified), d6 not
    assert man["n_documents"] == 8 and man["n_relevant"] == 7 and man["n_independent_platforms"] == 3
    disc = discard_pile(rows, claim_rows, reg)
    assert disc["unverified_claims"]["count"] == 1 and disc["not_relevant"]["count"] == 1
    # interview overlay: audit fills verdicts on top claims; coverage computed from the register
    split = reclassify_h1.apply(reg)
    assert split["total"] == sum(1 for e in reg if e["hypothesis_map"] == "H1" and e["stance"] == "supports")
    aud = apply_interview_audit(reg)
    assert aud["n_audited"] == sum(1 for e in reg if e["audit_verdict"]) and aud["n_audited"] <= aud["n_total"]
    assert all(e["audit_note"] for e in reg if e["audit_verdict"])  # every verdict carries a note
    print("selftest OK")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Claims -> ranked register + manifest + early signal")
    ap.add_argument("-i", "--input", default="claims.csv")
    ap.add_argument("--data", default="data.json")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    rows = load(args.input)
    claim_rows = [r for r in rows if r["claim_text"]]
    shippable = [r for r in claim_rows if r["quote"].strip()]
    print(f"{len(rows)} rows; {len(claim_rows)} claims; {len(shippable)} traceable.", file=sys.stderr)

    register = build_register(shippable)
    audit = apply_interview_audit(register)   # primary-research overlay: fills audit_verdict on top claims
    manifest = corpus_manifest(rows)
    lean = hypothesis_lean(claim_rows)
    h1_split = reclassify_h1.apply(register, net_lean=lean["h1"]["net"])  # writes h1_bucket + returns split
    manifest["h1_support_split"] = h1_split
    manifest["audit_coverage"] = audit
    cats = category_signal(claim_rows)
    discard = discard_pile(rows, claim_rows, register)

    manifest["n_claims_extracted"] = len(claim_rows)
    manifest["n_claims_traceable"] = len(shippable)
    manifest["n_register_entries"] = len(register)
    method_docs: dict[str, int] = {}
    for r in {r["doc_id"]: r for r in rows}.values():
        method_docs[r["method"]] = method_docs.get(r["method"], 0) + 1
    manifest["model_mix"] = method_docs

    json.dump(register, open("claims_register.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(manifest, open("corpus_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_early_signal(lean, cats, manifest, register)
    json.dump({"manifest": manifest, "register": register, "lean": lean, "categories": cats,
               "discard_pile": discard, "interview": INTERVIEW, "h1_split": h1_split, "audit": audit,
               "index": build_index(shippable)},
              open(args.data, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"Wrote claims_register.json ({len(register)} claims), corpus_manifest.json, "
          f"early_signal.md, {args.data}")
    contra = sum(lean[h]["contradicts"] for h in HYPOTHESES)
    print(f"lean: " + " | ".join(f"{HYP_LABEL[h]} net {lean[h]['net']:+d}" for h in ("h1", "h2", "h3"))
          + f"  ({contra} contradicting claims surfaced)")


if __name__ == "__main__":
    main()
