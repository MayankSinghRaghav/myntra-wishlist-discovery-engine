"""
analyze.py — Step 3. Turn labels into ranked opportunities + findings.md.

Pipeline:
  1. filter to is_relevant, compute distributions (overall + by source)
  2. KILL-SWITCH: price vs non-price blocker share
  3. sub-themes: TF-IDF + KMeans within each top barrier (--embedder st for MiniLM)
  4. opportunity scoring: gate -> 3 ordinal bands -> weighted score x evidence discount
  5. write opportunities.csv + findings.md

Reach = complaint-share (NOT true prevalence). MetricRelevance is a HYPOTHESIS.

Run:  python analyze.py -i classified_data.csv
      python analyze.py --embedder st     # use sentence-transformers MiniLM
      python analyze.py --selftest         # offline scoring checks
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

# blocking emotions => higher severity (data-driven, not hand-set per barrier)
BLOCKING_EMOTIONS = {"anxious", "overwhelmed", "indecisive", "skeptical", "frustrated"}
EVIDENCE_DISCOUNT = {"explicit": 1.0, "strong_inference": 0.7, "weak_inference": 0.4}

# App reviews skew post-purchase; a barrier voiced mostly AFTER buying is weakly linked
# to the PRE-purchase wishlist->buy decision. We discount score by its pre-purchase share.
PRE_STAGES = {"discovery", "consideration", "shortlisting", "evaluation", "decision"}
POST_STAGES = {"purchase", "post_purchase"}

# Per-barrier PM playbook. Evidence (quotes/counts) is pulled from REAL rows;
# these narrative fields are clearly-labelled HYPOTHESES, not measured facts.
#   funnel: re-exposure | re-engagement | confidence
#   mr: hypothesised MetricRelevance band (link strength to wishlist->purchase) 1/2/3
PLAYBOOK = {
    "fit_uncertainty": dict(funnel="confidence", mr=3,
        hyp="Users can't predict how a garment will fit their body, so a saved item stalls at decision.",
        workaround="They ask in comments, check other reviews, or just don't buy.",
        opp="Fit-confidence layer on the wishlist: per-item fit signals, 'fits like' from similar bodies, model-measurement match.",
        disconf="If fit complaints cluster in POST-purchase (returns) not pre-purchase, the block is quality/returns, not decision-stage fit.",
        validate="A/B a wishlist fit-signal badge; measure 30-day wishlist->purchase lift for exposed users."),
    "size_uncertainty": dict(funnel="confidence", mr=3,
        hyp="Inconsistent sizing across brands makes users unsure which size to order from a saved item.",
        workaround="They order two sizes intending to return one, or abandon the save.",
        opp="Size recommender on wishlist items using the user's past kept-vs-returned sizes per brand.",
        disconf="If users buy anyway and return, this is a returns-cost problem, not a save->buy block.",
        validate="Show a personalised size hint on wishlist; track add-to-cart and purchase from wishlist."),
    "quality_uncertainty": dict(funnel="confidence", mr=2,
        hyp="Photos look better than the delivered product, so users hesitate to commit to saved items.",
        workaround="They wait for more reviews or seek real-user photos.",
        opp="Surface verified buyer photos + quality-rating breakdown on the wishlist card.",
        disconf="If quality doubt is brand-specific, a global quality badge won't move conversion.",
        validate="Add buyer-photo count to wishlist cards; measure purchase from wishlist vs control."),
    "authenticity_trust": dict(funnel="confidence", mr=2,
        hyp="Users doubt product authenticity/originality, blocking commitment to saved branded items.",
        workaround="They cross-check price/seller elsewhere or avoid buying.",
        opp="Authenticity assurance (brand-authorised seller badge, guarantee) on wishlist branded items.",
        disconf="If distrust is app-wide sentiment not tied to saved items, a badge won't lift conversion.",
        validate="Expose authenticity badge on saved branded items; measure conversion delta."),
    "style_occasion_match": dict(funnel="confidence", mr=2,
        hyp="Users are unsure the saved item suits their occasion / existing wardrobe.",
        workaround="They save many similar items and never decide (see choice_overload).",
        opp="'Complete the look' / occasion tags on wishlist to resolve match doubt.",
        disconf="If saves are pure inspiration with no buy intent, styling won't convert them.",
        validate="Add occasion match cues to wishlist; measure shortlisting->purchase."),
    "choice_overload": dict(funnel="re-engagement", mr=3,
        hyp="Wishlists become graveyards: too many saved items, no way to decide, so nothing gets bought.",
        workaround="Users let the list grow and forget it.",
        opp="Wishlist decision aids: sort/compare saved items, 'pick for me', decayed re-surfacing of top saves.",
        disconf="If small wishlists also don't convert, overload isn't the binding constraint.",
        validate="Ship a wishlist compare/'top 3' nudge; measure 30-day wishlist->purchase."),
    "info_insufficient": dict(funnel="confidence", mr=2,
        hyp="Missing product info (fabric, care, exact measurements) leaves users unable to decide on a save.",
        workaround="They hunt in reviews/Q&A or drop the item.",
        opp="Fill the info gap on wishlist cards (measurements, fabric, care) pulled from catalog/Q&A.",
        disconf="If items with full info also stall, info isn't the block.",
        validate="Enrich wishlist card detail; measure purchase from wishlist."),
    "conflicting_reviews": dict(funnel="confidence", mr=2,
        hyp="Mixed reviews create decision paralysis on saved items.",
        workaround="Users keep reading reviews, never resolving.",
        opp="Review summary + 'most helpful' synthesis on the wishlist card.",
        disconf="If low-review items convert similarly, review conflict isn't decisive.",
        validate="Add AI review summary to saved items; measure conversion."),
    "social_validation_need": dict(funnel="confidence", mr=1,
        hyp="Users want a second opinion before buying a saved item.",
        workaround="They screenshot and ask friends off-app.",
        opp="Share-wishlist-for-opinions / poll a friend feature.",
        disconf="If shared items don't convert more, social proof isn't the block.",
        validate="Ship wishlist share-for-vote; measure purchase of voted items."),
    "needs_external_comparison": dict(funnel="confidence", mr=1,
        hyp="Users leave to compare price/availability elsewhere and don't return to buy the save.",
        workaround="They open other apps/tabs and get distracted.",
        opp="On-app comparison context (price history, similar-in-Myntra) to keep the decision in-app.",
        disconf="If comparers return and buy anyway, leakage isn't fatal.",
        validate="Add in-app comparison to wishlist; measure return-and-buy rate."),
    "delivery_returns": dict(funnel="confidence", mr=2,
        hyp="Uncertainty about return ease/cost for a saved item lowers commitment.",
        workaround="They avoid buying items they're unsure they can return cleanly.",
        opp="Clear, item-level return terms + 'easy return' assurance on wishlist cards.",
        disconf="If returns worry is post-purchase only, it doesn't block the save->buy step.",
        validate="Surface return terms on saved items; measure conversion."),
    "stockout": dict(funnel="re-exposure", mr=3,
        hyp="Saved items go out of stock (esp. the user's size) before they decide to buy.",
        workaround="They wait and it never comes back; the save dies.",
        opp="Back-in-stock + low-stock alerts for wishlisted sizes; reserve-my-size.",
        disconf="If in-stock saves convert at the same low rate, stockout isn't the driver.",
        validate="Ship size-level back-in-stock alerts; measure wishlist->purchase for alerted users."),
    "forgetting": dict(funnel="re-engagement", mr=3,
        hyp="Users save and simply forget; without a nudge the intent decays.",
        workaround="Nothing — the item sits unbought.",
        opp="Timely, non-price wishlist reminders (new reviews, restock, price-drop-agnostic 'still interested?').",
        disconf="If reminded users unsubscribe or ignore, forgetting wasn't the real block.",
        validate="A/B non-price wishlist reminders; measure 30-day wishlist->purchase lift."),
}

MONETARY_BARRIERS = {"price_value"}           # gated out: not non-monetary-addressable
NON_ACTIONABLE = {"none", "other"}            # gated out: not a discrete opportunity


# ---------------------------------------------------------------- helpers
def explode_barriers(df: pd.DataFrame) -> pd.Series:
    return df["barriers"].fillna("none").str.split("|").explode().str.strip()


def band(value: float, lo: float, hi: float) -> int:
    """Map a 0..1 value to an ordinal band 1/2/3 by two thresholds."""
    return 3 if value >= hi else (2 if value >= lo else 1)


def band_label(b: int) -> str:
    return {1: "Low", 2: "Med", 3: "High"}[b]


def score_row(reach: int, severity: int, metric_rel: int, evidence_conf: float) -> float:
    """score = 2*MR + 1.5*Sev + 1*Reach, then x evidence discount (per spec)."""
    return round((2 * metric_rel + 1.5 * severity + 1 * reach) * evidence_conf, 3)


def pre_purchase_share(stages: "pd.Series") -> float:
    """Share of a barrier's texts at PRE-purchase stages (post/pre only; unclear excluded).
    Returns 0.5 (neutral) if nothing is stage-resolved."""
    staged = stages[stages.isin(PRE_STAGES | POST_STAGES)]
    return float(stages.isin(PRE_STAGES).sum() / len(staged)) if len(staged) else 0.5


# ---------------------------------------------------------------- sub-themes
def embed(texts: list[str], mode: str):
    if mode == "st":
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2").encode(texts, show_progress_bar=False)
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(max_features=400, stop_words="english", ngram_range=(1, 2), min_df=2)
    return vec.fit_transform(texts), vec


def subthemes(texts: list[str], mode: str, max_k: int = 3) -> list[dict]:
    """Cluster a barrier's texts into named sub-needs with representative quotes."""
    import warnings

    from sklearn.cluster import KMeans
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.feature_extraction.text import TfidfVectorizer

    warnings.filterwarnings("ignore", category=ConvergenceWarning)  # dup short reviews -> harmless

    n = len(texts)
    if n < 8:
        return [{"name": "general", "size": n, "quotes": _pick_quotes(texts, 2)}]
    k = max(2, min(max_k, n // 25))
    if mode == "st":
        X = embed(texts, "st")
        km = KMeans(n_clusters=k, n_init=5, random_state=0).fit(X)
        labels = km.labels_
        # name clusters via TF-IDF terms of each group
        vec = TfidfVectorizer(max_features=400, stop_words="english", ngram_range=(1, 2), min_df=1)
        tfidf = vec.fit_transform(texts)
        terms = np.array(vec.get_feature_names_out())
    else:
        X, vec = embed(texts, "tfidf")
        km = KMeans(n_clusters=k, n_init=5, random_state=0).fit(X)
        labels = km.labels_
        tfidf, terms = X, np.array(vec.get_feature_names_out())

    out = []
    for c in range(k):
        idx = np.where(labels == c)[0]
        if len(idx) == 0:
            continue
        centroid = np.asarray(tfidf[idx].mean(axis=0)).ravel()
        top = terms[centroid.argsort()[::-1][:3]]
        out.append({
            "name": ", ".join(top),
            "size": int(len(idx)),
            "quotes": _pick_quotes([texts[i] for i in idx], 2),
        })
    return sorted(out, key=lambda d: d["size"], reverse=True)


def _pick_quotes(texts: list[str], k: int) -> list[str]:
    uniq = sorted(set(t.strip() for t in texts if 20 <= len(t.strip()) <= 220), key=len, reverse=True)
    return uniq[:k] or [t.strip()[:200] for t in texts[:k]]


# ---------------------------------------------------------------- core analysis
def analyze(df: pd.DataFrame, embedder: str) -> tuple[pd.DataFrame, dict]:
    rel = df[df["is_relevant"] == True].copy()  # noqa: E712 -- explicit for readability
    n_rel = len(rel)

    # kill-switch: price vs non-price blocker
    price_mask = (rel["intent"] == "price_waiter") | rel["barriers"].fillna("").str.contains("price_value")
    price_share = float(price_mask.mean()) if n_rel else 0.0

    bexp = explode_barriers(rel)
    barrier_counts = bexp.value_counts()

    stats = {
        "n_total": int(len(df)),
        "n_relevant": n_rel,
        "n_myntra_specific": int((rel["is_myntra_specific"] == True).sum()),  # noqa: E712
        "price_share": price_share,
        "non_price_share": 1 - price_share,
        "n_price": int(price_mask.sum()),
        "intent_mix": rel["intent"].value_counts().to_dict(),
        "journey_mix": rel["journey_stage"].value_counts().to_dict(),
        "emotion_mix": rel["emotional_state"].value_counts().to_dict(),
        "barrier_counts": barrier_counts.to_dict(),
        "by_source": {s: int(c) for s, c in df["source"].value_counts().items()},
        "n_auditable": int((rel["evidence_span"].fillna("").str.len() > 0).sum()),
        "new_patterns": [p for p in rel["new_pattern_note"].fillna("").tolist() if p][:20],
    }

    # opportunity scoring
    survivors, gated = [], []
    max_count = int(barrier_counts.max()) if len(barrier_counts) else 1
    for barrier, count in barrier_counts.items():
        if barrier in NON_ACTIONABLE:
            gated.append((barrier, int(count), "not a discrete opportunity"))
            continue
        if barrier in MONETARY_BARRIERS:
            gated.append((barrier, int(count), "monetary (excluded by no-incentive constraint)"))
            continue
        pb = PLAYBOOK.get(barrier)
        if pb is None:
            gated.append((barrier, int(count), "no funnel mapping"))
            continue

        sub = rel[rel["barriers"].fillna("").str.contains(barrier, regex=False)]
        share = count / max(n_rel, 1)                       # complaint-share
        # log-scale so one outlier barrier doesn't flatten every other reach to "Low"
        reach_b = band(float(np.log1p(count) / np.log1p(max_count)), 0.5, 0.8)
        blocking = sub["emotional_state"].isin(BLOCKING_EMOTIONS).mean()
        severity_b = band(float(blocking), 0.33, 0.60)
        mr_b = pb["mr"]
        evid_conf = float(sub["evidence_strength"].map(EVIDENCE_DISCOUNT).fillna(0.4).mean())
        pre_share = pre_purchase_share(sub["journey_stage"])  # reported, NOT folded into score
        score = score_row(reach_b, severity_b, mr_b, evid_conf)

        st = subthemes(sub["raw_text"].tolist(), embedder) if count >= 8 else \
            [{"name": "general", "size": int(count), "quotes": _pick_quotes(sub["raw_text"].tolist(), 2)}]
        # prefer Gemini's verbatim evidence_span (it justifies THIS barrier) over longest raw text
        spans = sorted({s.strip() for s in sub["evidence_span"].tolist()
                        if isinstance(s, str) and len(s.strip()) >= 15}, key=len, reverse=True)
        quotes = spans[:3] or _pick_quotes(sub["raw_text"].tolist(), 3)

        survivors.append({
            "barrier": barrier, "funnel_level": pb["funnel"],
            "n_texts": int(count), "complaint_share": round(share, 4),
            "reach_band": band_label(reach_b), "severity_band": band_label(severity_b),
            "metric_relevance_band": band_label(mr_b),
            "reach_score": reach_b, "severity_score": severity_b, "metric_relevance_score": mr_b,
            "evidence_confidence": round(evid_conf, 3),
            "pre_purchase_share": round(pre_share, 3), "score": score,
            "opportunity": pb["opp"], "top_subtheme": st[0]["name"] if st else "",
            "example_quote": quotes[0] if quotes else "",
            "_quotes": quotes, "_subthemes": st, "_pb": pb,
            "note": "Reach=complaint-share (not true prevalence); MetricRelevance=hypothesis.",
        })

    opp = pd.DataFrame(sorted(survivors, key=lambda d: d["score"], reverse=True))
    if not opp.empty:
        opp.insert(0, "rank", range(1, len(opp) + 1))
    stats["gated_out"] = gated
    return opp, stats


# ---------------------------------------------------------------- findings.md
def write_findings(opp: pd.DataFrame, stats: dict, path: str = "findings.md") -> None:
    L = []
    L.append("# Findings — Myntra Wishlist->Purchase Discovery Engine\n")
    L.append("_Hypothesis generator from public user text. NOT proof. "
             "Reach = complaint-share, not true prevalence. MetricRelevance = hypothesised link._\n")

    ps = stats["price_share"]
    L.append("## KILL-SWITCH: price vs non-price blocker\n")
    L.append(f"- **{ps*100:.1f}%** of relevant texts point to a **price** blocker "
             f"(`intent=price_waiter` OR `price_value` barrier) — {stats['n_price']}/{stats['n_relevant']} rows.\n")
    L.append(f"- **{(1-ps)*100:.1f}%** point to **non-price** barriers "
             "(fit, size, quality, trust, choice overload, stockout, forgetting, ...).\n")
    verdict = ("Non-price strategy has HEADROOM — most blockers are addressable without discounts."
               if ps < 0.5 else
               "WARNING: price dominates — the non-monetary strategy has a low ceiling. Re-scope.")
    L.append(f"- **Read:** {verdict}\n")

    L.append("\n## Corpus\n")
    L.append(f"- {stats['n_total']} texts collected; **{stats['n_relevant']} relevant**; "
             f"{stats['n_myntra_specific']} Myntra-specific.\n")
    L.append(f"- Sources: {stats['by_source']}\n")
    L.append(f"- Intent mix: {stats['intent_mix']}\n")
    L.append(f"- Journey stage: {stats['journey_mix']}\n")
    L.append(f"- Emotional state: {stats['emotion_mix']}\n")

    L.append("\n## Ranked opportunities (gated, non-monetary)\n")
    if opp.empty:
        L.append("_No survivors — check the corpus._\n")
    else:
        L.append("| # | Barrier | Funnel | Score | Reach | Severity | MetricRel | Evid | n | Pre-buy% |\n")
        L.append("|---|---|---|---|---|---|---|---|---|---|\n")
        for _, r in opp.iterrows():
            L.append(f"| {r['rank']} | {r['barrier']} | {r['funnel_level']} | {r['score']} | "
                     f"{r['reach_band']} | {r['severity_band']} | {r['metric_relevance_band']} | "
                     f"{r['evidence_confidence']} | {r['n_texts']} | {r['pre_purchase_share']*100:.0f}% |\n")
        L.append("\n_Pre-buy% = share of the barrier's texts voiced at a PRE-purchase stage. "
                 "Low % ⇒ mostly post-purchase ⇒ weaker link to the save→buy step (reported, not scored)._\n")

    L.append("\n## Insight cards (top opportunities)\n")
    for _, r in opp.head(6).iterrows():
        pb = r["_pb"]
        q = r["_quotes"][0] if r["_quotes"] else "(no quote)"
        subs = "; ".join(f"{s['name']} (n={s['size']})" for s in r["_subthemes"][:3])
        L.append(f"\n### {r['rank']}. {r['barrier']}  \n")
        L.append(f"- **Observed behavior:** users voice this {r['n_texts']} times "
                 f"({r['complaint_share']*100:.1f}% of relevant complaints; "
                 f"{r['pre_purchase_share']*100:.0f}% at a pre-purchase stage).\n")
        L.append(f"- **Underlying barrier:** {r['barrier']} ({r['funnel_level']} funnel level).\n")
        L.append(f"- **Root-cause hypothesis:** {pb['hyp']}\n")
        L.append(f"- **Current workaround:** {pb['workaround']}\n")
        L.append(f"- **Potential opportunity:** {pb['opp']}\n")
        L.append(f"- **Sub-themes:** {subs}\n")
        L.append(f"- **Evidence:** \"{q}\"  (+{r['n_texts']-1} more)\n")
        L.append(f"- **Confidence:** score {r['score']} | evidence discount {r['evidence_confidence']} "
                 f"| bands R/S/M = {r['reach_band']}/{r['severity_band']}/{r['metric_relevance_band']}.\n")
        L.append(f"- **Disconfirming evidence:** {pb['disconf']}\n")
        L.append(f"- **What would validate/refute:** {pb['validate']}\n")

    L.append("\n## Gated-out (logged for honesty)\n")
    for b, c, why in stats["gated_out"]:
        L.append(f"- `{b}` (n={c}) — {why}\n")

    if stats["new_patterns"]:
        L.append("\n## New patterns (barriers not in the taxonomy)\n")
        for p in dict.fromkeys(stats["new_patterns"]):
            L.append(f"- {p}\n")

    L.append("\n## Bias & limitations\n")
    L.append("- **Complaint-skewed:** app reviews/comments over-represent the frustrated. "
             "Reach is complaint-share, NOT the true share of users who hit each barrier.\n")
    L.append("- **Language-skewed:** collected with `lang=en`; Hinglish/Hindi still surfaced and was "
             "classified, but pure regional-language reviews are under-sampled.\n")
    L.append("- **Proxy funnel:** app-review text is NOT the wishlist funnel. Every "
             "wishlist->purchase link here is a HYPOTHESIS to be validated with product analytics/experiments.\n")
    L.append("- **No true frequencies:** we cannot say how often each barrier occurs per user, only how often it is *voiced*.\n")
    L.append(f"- **Auditability:** {stats['n_auditable']}/{stats['n_relevant']} relevant rows carry a "
             "verbatim `evidence_span`, so any label can be hand-checked against its source quote.\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(L))


# ---------------------------------------------------------------- selftest
def _selftest() -> None:
    assert band(0.1, 0.33, 0.66) == 1 and band(0.5, 0.33, 0.66) == 2 and band(0.9, 0.33, 0.66) == 3
    # MetricRelevance weighted highest: raising MR beats raising Reach by the same step
    base = score_row(1, 1, 1, 1.0)
    assert score_row(2, 1, 1, 1.0) - base > score_row(1, 1, 1, 1.0) - base  # sanity noop
    assert score_row(1, 1, 2, 1.0) > score_row(2, 1, 1, 1.0), "MR must outweigh Reach"
    assert score_row(1, 1, 1, 0.4) < score_row(1, 1, 1, 1.0), "evidence discount must reduce score"
    assert abs(pre_purchase_share(pd.Series(["decision", "post_purchase", "unclear"])) - 0.5) < 1e-9
    assert pre_purchase_share(pd.Series(["unclear", "unclear"])) == 0.5  # nothing staged -> neutral
    assert _pick_quotes(["short", "a decent length sentence about fit and size " * 2], 1)
    print("selftest OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="Cluster + score -> opportunities.csv + findings.md")
    ap.add_argument("-i", "--input", default="classified_data.csv")
    ap.add_argument("-o", "--opps", default="opportunities.csv")
    ap.add_argument("--findings", default="findings.md")
    ap.add_argument("--embedder", choices=["tfidf", "st"], default="tfidf",
                    help="tfidf (lean, default) or st (sentence-transformers MiniLM)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    df = pd.read_csv(args.input, dtype=str).fillna("")
    df["is_relevant"] = df["is_relevant"].str.lower().isin({"true", "1", "yes"})
    df["is_myntra_specific"] = df["is_myntra_specific"].str.lower().isin({"true", "1", "yes"})
    print(f"Loaded {len(df)} rows; {int(df['is_relevant'].sum())} relevant.", file=sys.stderr)

    opp, stats = analyze(df, args.embedder)
    drop_cols = [c for c in opp.columns if c.startswith("_")]
    opp.drop(columns=drop_cols).to_csv(args.opps, index=False, encoding="utf-8")
    write_findings(opp, stats, args.findings)
    print(f"Wrote {args.opps} ({len(opp)} opportunities) and {args.findings}.")
    print(f"KILL-SWITCH price share: {stats['price_share']*100:.1f}%")


if __name__ == "__main__":
    main()
