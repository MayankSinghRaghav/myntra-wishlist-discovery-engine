"""
reclassify_h1.py — re-cut the H1-supporting claims to power the interview finding with DATA (not n=6).

The interviews rejected H1 as the primary blocker; the corpus gives H1 a big +net lean. This pass
classifies each H1-SUPPORTING claim in claims_register.json, from its verbatim quote text, as:

  pre_purchase   — fit/size/quality doubt BEFORE buying a saved/considered item (true H1)
  post_purchase  — bad return/delivery/wrong-item experience AFTER a purchase (a grievance, not a blocker)
  unclear        — quote carries both signals, or neither  (NOT forced)

It writes an `h1_bucket` field onto each H1-supporting claim, recomputes the split, and writes it into
corpus_manifest.json (`h1_support_split`) and data.json (`h1_split`, read by the dashboard). Every
number is computed here in code from the register — nothing hand-entered.

Run (standalone, reproducible — no API key):  python reclassify_h1.py
Or it runs automatically inside `python analyze.py` (which imports classify_h1 + apply).
Selftest:  python reclassify_h1.py --selftest
"""
from __future__ import annotations

import json
import re
import sys

# ── keyword evidence (explicit + documented, so the split is auditable) ──────
# POST = language about a COMPLETED purchase that then went wrong. Stems (no trailing \b) so
# inflections match: return/returns/returned, deliver/delivery/delivered, receiv(e/ed/ing), etc.
_POST = re.compile(
    r"\b(returns?|returned|refund|exchang|replac|deliver|courier|pick[- ]?up|shipment|shipping|"
    r"receiv|arriv|when it came|after (i |)(bought|order|ordered|purchas)|on arrival|"
    r"wrong (product|item|size|order)|damag|defective|torn|faulty|old product|used product|"
    r"cancel|my order|the order|order was|quality check|not as (shown|described))", re.I)
# PRE = an actual DOUBT at the moment of deciding whether to buy a considered item (not merely
# that the item was saved — a save alone is not uncertainty).
_PRE = re.compile(
    r"\b(not sure|unsure|confus|can'?t decide|don'?t know (if|which|what)|size chart|which size|"
    r"will it fit|true to size|size guide|before (buy|order|purchas|i buy)|should i buy|"
    r"thinking of buying|planning to buy|look(s)? like the (photo|pic|image)|"
    r"hesitat|not confident|afraid it (won'?t|wont)|worried it)", re.I)


def classify_h1(text: str) -> str:
    """Bucket one claim's text by the verbatim evidence. Ambiguous → 'unclear' (never forced)."""
    post = bool(_POST.search(text or ""))
    pre = bool(_PRE.search(text or ""))
    if pre and not post:
        return "pre_purchase"
    if post and not pre:
        return "post_purchase"
    return "unclear"


def _text_of(entry: dict) -> str:
    # primarily the verbatim quotes (per the task), plus the claim_text
    quotes = " ".join(q.get("verbatim", "") for q in entry.get("source_quotes", []))
    return f"{entry.get('claim_text', '')} {quotes}"


def h1_supporting(register: list[dict]) -> list[dict]:
    return [e for e in register if e.get("hypothesis_map") == "H1" and e.get("stance") == "supports"]


def apply(register: list[dict], net_lean: int | None = None) -> dict:
    """Write `h1_bucket` onto each H1-supporting claim and return the computed split."""
    sup = h1_supporting(register)
    counts = {"pre_purchase": 0, "post_purchase": 0, "unclear": 0}
    for e in sup:
        b = classify_h1(_text_of(e))
        e["h1_bucket"] = b
        counts[b] += 1
    split = {"total": len(sup), **counts,
             "method": "Deterministic keyword classification of each H1-supporting claim's verbatim "
                       "quotes into pre-purchase uncertainty vs post-purchase grievance. A claim with "
                       "both signals, or neither, is 'unclear' — never forced. Fully reproducible "
                       "(reclassify_h1.py, no API key)."}
    if net_lean is not None:
        split["net_lean"] = net_lean
    split["summary"] = summarize(split)
    return split


def summarize(split: dict) -> str:
    t = split["total"]
    pre, post, unc = split["pre_purchase"], split["post_purchase"], split["unclear"]
    if not t:
        return "No H1-supporting claims to classify."
    net = split.get("net_lean")
    net_txt = f" (net +{net})" if net is not None else ""
    ps, prs = post / t * 100, pre / t * 100
    if post > pre:
        return (f"Of {t} H1-supporting claims, post-purchase grievance is the larger bucket — "
                f"{post} ({ps:.0f}%) vs {pre} pre-purchase ({prs:.0f}%), {unc} unclear. Computed from the "
                f"verbatim quotes, this means the corpus's H1 lean{net_txt} is largely NOT about "
                f"pre-purchase hesitation on saved items; it is dominated by complaints about "
                f"returns/delivery on completed purchases. That is the data-scale echo of the 6 interviews: "
                f"H1 is not the primary saved-item→purchase blocker.")
    if pre > post:
        return (f"Of {t} H1-supporting claims, pre-purchase uncertainty is the larger bucket — "
                f"{pre} ({prs:.0f}%) vs {post} post-purchase ({ps:.0f}%), {unc} unclear. So the corpus H1 "
                f"signal{net_txt} IS substantially about saved-item hesitation, which sits in tension with "
                f"the interviews — treat with caution and lean on primary research to resolve it.")
    return (f"Of {t} H1-supporting claims, pre- and post-purchase are balanced ({pre} vs {post}, {unc} "
            f"unclear). The corpus H1 signal{net_txt} is genuinely mixed and cannot alone settle whether "
            f"uncertainty blocks saved-item purchase — the interviews carry that call.")


# ── standalone reproducible run ──────────────────────────────────────────────
def _load(path):
    return json.load(open(path, encoding="utf-8"))


def _dump(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1 if path.endswith("register.json") else None)


def main() -> None:
    if "--selftest" in sys.argv:
        _selftest()
        return
    try:  # summaries contain arrows/'≫'; don't let a Windows console codepage crash the run
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    register = _load("claims_register.json")
    data = _load("data.json")
    manifest = _load("corpus_manifest.json")
    net = (data.get("lean", {}).get("h1", {}) or {}).get("net")

    split = apply(register, net_lean=net)

    # write the per-claim field back + the split into manifest + data.json (dashboard reads h1_split)
    json.dump(register, open("claims_register.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    manifest["h1_support_split"] = split
    json.dump(manifest, open("corpus_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    data["h1_split"] = split
    data["register"] = register  # carry the h1_bucket fields into the dashboard artifact
    json.dump(data, open("data.json", "w", encoding="utf-8"), ensure_ascii=False)

    print(f"H1-supporting claims: {split['total']}")
    print(f"  pre_purchase : {split['pre_purchase']}")
    print(f"  post_purchase: {split['post_purchase']}")
    print(f"  unclear      : {split['unclear']}")
    if net is not None:
        print(f"H1 net corpus lean: +{net}")
    print("\n" + split["summary"])
    print("\nWrote h1_bucket -> claims_register.json; h1_support_split -> corpus_manifest.json; h1_split -> data.json")
    print("Next: python build_static.py  (then redeploy)")


def _selftest() -> None:
    assert classify_h1("not sure of the size before buying") == "pre_purchase"
    assert classify_h1("I returned it, the delivery was wrong") == "post_purchase"
    assert classify_h1("not sure of size so I returned it") == "unclear"   # both signals
    assert classify_h1("the app is nice") == "unclear"                     # neither
    reg = [
        {"hypothesis_map": "H1", "stance": "supports", "claim_text": "unsure which size to order",
         "source_quotes": [{"verbatim": "not sure of my size"}]},
        {"hypothesis_map": "H1", "stance": "supports", "claim_text": "bad return experience",
         "source_quotes": [{"verbatim": "they rejected my return after delivery"}]},
        {"hypothesis_map": "H3", "stance": "supports", "claim_text": "just browsing",
         "source_quotes": [{"verbatim": "window shopping"}]},   # not H1 -> untouched
    ]
    split = apply(reg, net_lean=118)
    assert split["total"] == 2 and split["pre_purchase"] == 1 and split["post_purchase"] == 1
    assert reg[0]["h1_bucket"] == "pre_purchase" and reg[1]["h1_bucket"] == "post_purchase"
    assert "h1_bucket" not in reg[2]                                        # H3 claim untouched
    assert "118" in split["summary"] or "net" in split["summary"]
    print("selftest OK")


if __name__ == "__main__":
    main()
