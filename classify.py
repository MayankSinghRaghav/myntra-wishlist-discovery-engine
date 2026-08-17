"""
classify.py — Step 2. Label each text with Gemini (JSON mode, temperature=0).

Batched (~15 texts/call), resumable (skips doc_ids already in the output),
rate-limited for the free tier. Reads raw_data.csv, writes classified_data.csv
carrying the original fields + labels so the dashboard needs only this one file.

Env:  GEMINI_API_KEY   (never hardcoded)
Run:  python classify.py -i raw_data.csv -o classified_data.csv
      python classify.py --limit 30          # small test run
      python classify.py --selftest          # offline: enum coercion checks
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

# ---- taxonomy (kept identical to the case-study spec) -----------------------
INTENTS = {"latent_intent", "inspiration", "price_waiter", "comparison_shortlist", "unclear"}
BARRIERS = {
    "fit_uncertainty", "size_uncertainty", "quality_uncertainty", "authenticity_trust",
    "style_occasion_match", "choice_overload", "info_insufficient", "conflicting_reviews",
    "social_validation_need", "needs_external_comparison", "price_value", "delivery_returns",
    "stockout", "forgetting", "none", "other",
}
EMOTIONS = {"confident", "curious", "overwhelmed", "anxious", "skeptical",
            "indecisive", "excited", "frustrated", "unclear"}
STAGES = {"discovery", "consideration", "shortlisting", "evaluation", "decision",
          "purchase", "post_purchase", "unclear"}
EVIDENCE = {"explicit", "strong_inference", "weak_inference"}

OUT_COLUMNS = [
    "doc_id", "source", "platform", "url", "posted_date", "rating", "raw_text",
    "is_relevant", "is_myntra_specific", "intent", "barriers", "information_gap",
    "emotional_state", "journey_stage", "evidence_strength", "evidence_span",
    "new_pattern_note",
]

PROMPT = """You are labelling short public texts (app reviews, YouTube/Reddit comments)
about shopping on Myntra, an Indian fashion e-commerce app. A Growth PM wants to
understand why users SAVE fashion items (wishlist) but do not BUY them, focusing on
NON-PRICE barriers (confidence, uncertainty, timing, decision quality).

Return a JSON array with EXACTLY one object per input text, in the same order.
Each object MUST have these keys:
- is_relevant (bool): true if about shopping/product/fit/quality/price/delivery/returns/
  buying decision. false for pure app-bug/login/crash/payment-failure/spam.
- is_myntra_specific (bool)
- intent: one of {intents}
- barriers: array (0+) from {barriers}. Use [] or ["none"] if no barrier.
- information_gap: short phrase describing what info the user lacked, or ""
- emotional_state: one of {emotions}
- journey_stage: one of {stages}
- evidence_strength: one of {evidence}  (explicit if literally stated; else inference)
- evidence_span: EXACT quote (<=120 chars) copied from the text that justifies the main
  label. If nothing supports it, use "" (that means low confidence).
- new_pattern_note: if a real barrier appears that is NOT in the list, describe it; else ""

Do not invent content. The evidence_span must be a verbatim substring of the input.
Texts:
{texts}"""


# ---------------------------------------------------------------- coercion
def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def one_of(v, allowed: set[str], default: str) -> str:
    s = str(v).strip().lower()
    return s if s in allowed else default


def coerce_barriers(v) -> str:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return "none"
    keep = [str(x).strip().lower() for x in v if str(x).strip().lower() in BARRIERS]
    keep = [b for b in keep if b != "none"] or (["none"] if v else ["none"])
    # de-dup, preserve order
    seen, out = set(), []
    for b in keep:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return "|".join(out)


def coerce(obj: dict) -> dict:
    """Map one raw model object to safe, validated label fields."""
    return {
        "is_relevant": as_bool(obj.get("is_relevant")),
        "is_myntra_specific": as_bool(obj.get("is_myntra_specific")),
        "intent": one_of(obj.get("intent"), INTENTS, "unclear"),
        "barriers": coerce_barriers(obj.get("barriers")),
        "information_gap": str(obj.get("information_gap", "") or "")[:200],
        "emotional_state": one_of(obj.get("emotional_state"), EMOTIONS, "unclear"),
        "journey_stage": one_of(obj.get("journey_stage"), STAGES, "unclear"),
        "evidence_strength": one_of(obj.get("evidence_strength"), EVIDENCE, "weak_inference"),
        "evidence_span": str(obj.get("evidence_span", "") or "")[:120],
        "new_pattern_note": str(obj.get("new_pattern_note", "") or "")[:200],
    }


def empty_labels(note: str = "parse_error") -> dict:
    d = coerce({})
    d["is_relevant"] = False
    d["new_pattern_note"] = note
    return d


# ---------------------------------------------------------------- gemini
def make_model(model_name: str):
    import google.generativeai as genai

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("ERROR: GEMINI_API_KEY not set. `export GEMINI_API_KEY=...` and retry.")
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        model_name,
        generation_config={"temperature": 0, "response_mime_type": "application/json"},
    )


def classify_batch(model, texts: list[str]) -> list[dict]:
    numbered = "\n".join(f"[{i}] {t[:800]}" for i, t in enumerate(texts))
    prompt = PROMPT.format(intents=sorted(INTENTS), barriers=sorted(BARRIERS),
                           emotions=sorted(EMOTIONS), stages=sorted(STAGES),
                           evidence=sorted(EVIDENCE), texts=numbered)
    resp = model.generate_content(prompt)
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("model did not return a list")
    # align lengths defensively
    out = [coerce(o) if isinstance(o, dict) else empty_labels("bad_obj") for o in data]
    while len(out) < len(texts):
        out.append(empty_labels("missing_from_batch"))
    return out[: len(texts)]


# ---------------------------------------------------------------- io
def load_done(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {row["doc_id"] for row in csv.DictReader(f)}


def open_appender(path: str):
    exists = os.path.exists(path)
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
    if not exists:
        w.writeheader()
    return f, w


# ---------------------------------------------------------------- selftest
def _selftest() -> None:
    assert one_of("PRICE_WAITER", INTENTS, "unclear") == "price_waiter"
    assert one_of("garbage", INTENTS, "unclear") == "unclear"
    assert coerce_barriers(["fit_uncertainty", "nonsense", "none"]) == "fit_uncertainty"
    assert coerce_barriers([]) == "none"
    assert coerce_barriers("price_value") == "price_value"
    assert coerce_barriers(["size_uncertainty", "size_uncertainty"]) == "size_uncertainty"
    assert as_bool("True") and not as_bool("no")
    c = coerce({"intent": "x", "barriers": ["quality_uncertainty"], "evidence_span": "z" * 300})
    assert c["intent"] == "unclear" and len(c["evidence_span"]) == 120
    print("selftest OK")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini classification -> classified_data.csv")
    ap.add_argument("-i", "--input", default="raw_data.csv")
    ap.add_argument("-o", "--output", default="classified_data.csv")
    ap.add_argument("--model", default="gemini-flash-lite-latest",
                    help="flash-lite has higher free-tier quota; gemini-2.5-flash caps at ~20 req/window")
    ap.add_argument("--batch", type=int, default=20, help="bigger batch = fewer calls = less quota pressure")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between calls (free-tier RPM)")
    ap.add_argument("--limit", type=int, default=0, help="max NEW rows to classify (0 = all)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    with open(args.input, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    done = load_done(args.output)
    todo = [r for r in rows if r["doc_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(rows)} rows, {len(done)} already done, {len(todo)} to classify.", file=sys.stderr)
    if not todo:
        print("Nothing to do.")
        return

    model = make_model(args.model)
    fout, writer = open_appender(args.output)
    carry = ("doc_id", "source", "platform", "url", "posted_date", "rating", "raw_text")
    n_done = 0
    try:
        for start in range(0, len(todo), args.batch):
            chunk = todo[start:start + args.batch]
            texts = [r["raw_text"] for r in chunk]
            labels = None
            for attempt in range(3):  # retry w/ backoff so free-tier 429s don't lose rows
                try:
                    labels = classify_batch(model, texts)
                    break
                except Exception as e:  # noqa: BLE001
                    wait = args.sleep * (attempt + 1) * 3
                    print(f"  batch {start} attempt {attempt+1} err: {e}; retry in {wait:.0f}s",
                          file=sys.stderr)
                    time.sleep(wait)
            if labels is None:
                print(f"  batch {start} gave up -> parse_error", file=sys.stderr)
                labels = [empty_labels() for _ in chunk]
            for r, lab in zip(chunk, labels):
                writer.writerow({**{k: r.get(k, "") for k in carry}, **lab})
            fout.flush()
            n_done += len(chunk)
            print(f"  classified {n_done}/{len(todo)}", file=sys.stderr)
            time.sleep(args.sleep)
    finally:
        fout.close()
    print(f"Done. Appended {n_done} rows to {args.output}.")


if __name__ == "__main__":
    main()
