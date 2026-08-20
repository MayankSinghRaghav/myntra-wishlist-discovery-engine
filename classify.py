"""
classify.py — Step 2. Dual-hypothesis coding of each text (Gemini JSON, temp=0).

Every document is coded INDEPENDENTLY on the three pre-registered hypotheses
(see hypotheses.md) — a doc may support several, one, or NONE. It is also placed
in a closed intent_segment (the segmentation dimension) and given one closed
topic label. No free-form themes; verbatim spans are verified against the source.

Batched (~20/call), resumable (skips doc_ids already written), free-tier friendly.
When a batch exhausts its retries, rows fall back to a keyword RULE classifier that
is tagged method="rule_fallback" and is NEVER counted as AI output downstream.

Env:  GEMINI_API_KEY   (never hardcoded)
Run:  python classify.py -i raw_data.csv -o classified_data.csv
      python classify.py --limit 30          # small live test
      python classify.py --selftest          # offline: coercion + rule + span checks
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time

# ---- closed taxonomies (MUST match hypotheses.md) ---------------------------
INTENT_SEGMENTS = {"deferred_purchase", "mood_board", "price_watch",
                   "catalogue_browse", "size_unavailable_hold", "unclear"}
TOPICS = {
    "fit_uncertainty", "size_uncertainty", "quality_uncertainty", "authenticity_trust",
    "style_occasion_match", "choice_overload", "info_insufficient", "conflicting_reviews",
    "social_validation_need", "needs_external_comparison", "price_value", "delivery_returns",
    "stockout", "forgetting", "none", "other",
}
EVIDENCE = {"explicit", "strong_inference", "weak_inference"}
HYPS = ("h1", "h2", "h3")

OUT_COLUMNS = [
    "doc_id", "source", "platform", "url", "posted_date", "rating", "raw_text",
    "is_relevant", "is_myntra_specific", "intent_segment",
    "h1_present", "h1_conf", "h1_span",
    "h2_present", "h2_conf", "h2_span",
    "h3_present", "h3_conf", "h3_span",
    "topic", "evidence_strength", "method",
]

PROMPT = """You label short public texts (app reviews, YouTube/Reddit comments) about shopping
on Myntra, an Indian fashion app. A Growth PM wants to know why users SAVE (wishlist) items but
do NOT buy them. Three competing hypotheses are being tested (code each INDEPENDENTLY — a text
may support several, one, or none):

- H1 UNCERTAINTY BLOCKS CONVERSION: user wants it but an UNRESOLVED doubt (fit, size, quality,
  authenticity, styling/occasion, social validation) stalls the decision.
- H2 RELEVANCE DECAYS: nothing unresolved — the window closed (occasion passed, trend moved,
  forgot, already bought elsewhere).
- H3 WISHLIST != PURCHASE INTENT: the save was never a buy signal (mood-board/inspiration,
  price-watch, catalogue browsing, holding for an out-of-stock size).

Return a JSON array, EXACTLY one object per input text, same order. Keys per object:
- is_relevant (bool): true if about shopping/product/fit/quality/price/delivery/buying decision.
  false for pure app-bug/login/crash/payment-failure/spam.
- is_myntra_specific (bool)
- intent_segment: one of {segments}
- h1_present (bool), h1_conf (0.0-1.0), h1_span (EXACT verbatim substring of the text, or "")
- h2_present (bool), h2_conf (0.0-1.0), h2_span (verbatim substring, or "")
- h3_present (bool), h3_conf (0.0-1.0), h3_span (verbatim substring, or "")
- topic: one of {topics}
- evidence_strength: one of {evidence}

Rules: do NOT invent content. Each *_span MUST be copied verbatim from the input text; if nothing
supports that hypothesis, set present=false and span="". Use closed values only.
Texts:
{texts}"""


# ---------------------------------------------------------------- coercion
def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def one_of(v, allowed: set[str], default: str) -> str:
    s = str(v).strip().lower()
    return s if s in allowed else default


def as_conf(v) -> float:
    try:
        return round(min(1.0, max(0.0, float(v))), 3)
    except (TypeError, ValueError):
        return 0.0


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def verify_span(span: str, text: str, limit: int = 160) -> str:
    """Return the span iff it is a (whitespace/case-normalized) substring of text; else ""."""
    span = str(span or "").strip()[:limit]
    if not span:
        return ""
    return span if _norm(span) and _norm(span) in _norm(text) else ""


def coerce(obj: dict, text: str, method: str = "gemini") -> dict:
    d = {
        "is_relevant": as_bool(obj.get("is_relevant")),
        "is_myntra_specific": as_bool(obj.get("is_myntra_specific")),
        "intent_segment": one_of(obj.get("intent_segment"), INTENT_SEGMENTS, "unclear"),
        "topic": one_of(obj.get("topic"), TOPICS, "other"),
        "evidence_strength": one_of(obj.get("evidence_strength"), EVIDENCE, "weak_inference"),
        "method": method,
    }
    for h in HYPS:
        present = as_bool(obj.get(f"{h}_present"))
        span = verify_span(obj.get(f"{h}_span"), text)
        # a present=true hypothesis with no verifiable span is downgraded, not trusted
        if present and not span:
            present, conf = False, 0.0
        else:
            conf = as_conf(obj.get(f"{h}_conf")) if present else 0.0
        d[f"{h}_present"] = present
        d[f"{h}_conf"] = conf
        d[f"{h}_span"] = span
    return d


def empty_labels(text: str = "", note: str = "parse_error") -> dict:
    d = coerce({}, text, method=note)
    d["is_relevant"] = False
    return d


# ---------------------------------------------------------------- rule fallback
_IRRELEVANT = re.compile(r"\b(crash|login|log in|otp|payment fail|refund not|app not open|"
                         r"server error|hang|lag|bug)\b", re.I)
_H1 = re.compile(r"\b(not sure|unsure|confused|which size|will it fit|true to size|fit|"
                 r"size chart|quality|material|fabric|original|authentic|fake|suit me|look good)\b", re.I)
_H2 = re.compile(r"\b(forgot|forget|already bought|already got|no longer|don'?t need|"
                 r"moved on|occasion|was for|out of season)\b", re.I)
_H3 = re.compile(r"\b(wishlist|save for later|saved for later|inspo|inspiration|mood ?board|"
                 r"wait for (a )?(sale|offer|discount)|price drop|see later|just browsing)\b", re.I)
_PRICE = re.compile(r"\b(sale|offer|discount|price drop|cheaper|coupon)\b", re.I)
_STOCK = re.compile(r"\b(out of stock|size (not )?available|restock|back in stock)\b", re.I)
_MOOD = re.compile(r"\b(inspo|inspiration|mood ?board)\b", re.I)


def _first(rx, text: str) -> str:
    m = rx.search(text or "")
    return text[m.start():m.start() + 80].strip() if m else ""


def rule_label(text: str) -> dict:
    """Deterministic keyword fallback. Tagged method='rule_fallback' — never AI output."""
    t = text or ""
    relevant = not _IRRELEVANT.search(t) and len(t) > 8
    if _STOCK.search(t):
        seg = "size_unavailable_hold"
    elif _MOOD.search(t):
        seg = "mood_board"
    elif _PRICE.search(t):
        seg = "price_watch"
    elif _H3.search(t):
        seg = "catalogue_browse"
    elif _H1.search(t) or _H2.search(t):
        seg = "deferred_purchase"
    else:
        seg = "unclear"
    obj = {"is_relevant": relevant, "is_myntra_specific": False,
           "intent_segment": seg, "topic": "other", "evidence_strength": "weak_inference"}
    for h, rx in (("h1", _H1), ("h2", _H2), ("h3", _H3)):
        span = _first(rx, t)
        obj[f"{h}_present"] = bool(span) and relevant
        obj[f"{h}_conf"] = 0.3 if span else 0.0
        obj[f"{h}_span"] = span
    return coerce(obj, t, method="rule_fallback")


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
    prompt = PROMPT.format(segments=sorted(INTENT_SEGMENTS), topics=sorted(TOPICS),
                           evidence=sorted(EVIDENCE), texts=numbered)
    resp = model.generate_content(prompt)
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("model did not return a list")
    out = [coerce(o, texts[i]) if isinstance(o, dict) else empty_labels(texts[i], "bad_obj")
           for i, o in enumerate(data[:len(texts)])]
    while len(out) < len(texts):
        out.append(empty_labels(texts[len(out)], "missing_from_batch"))
    return out


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
    assert one_of("DEFERRED_PURCHASE", INTENT_SEGMENTS, "unclear") == "deferred_purchase"
    assert one_of("garbage", INTENT_SEGMENTS, "unclear") == "unclear"
    assert as_conf("1.5") == 1.0 and as_conf("x") == 0.0 and as_conf("0.42") == 0.42
    # span verification: normalized substring keeps, otherwise blanks
    assert verify_span("Not SURE", "i am not sure of the size") == "Not SURE"
    assert verify_span("totally invented", "i am not sure") == ""
    # present=true with a non-verifiable span is downgraded to false
    c = coerce({"h1_present": True, "h1_span": "invented", "h1_conf": 0.9}, "some text")
    assert c["h1_present"] is False and c["h1_span"] == "" and c["h1_conf"] == 0.0
    c2 = coerce({"h1_present": True, "h1_span": "not sure", "h1_conf": 0.8,
                 "intent_segment": "mood_board"}, "i'm not sure it fits")
    assert c2["h1_present"] and c2["h1_span"] == "not sure" and c2["intent_segment"] == "mood_board"
    # rule fallback is always tagged and never labels itself AI
    r = rule_label("saving this for inspo, will wait for a sale")
    assert r["method"] == "rule_fallback" and r["intent_segment"] in {"price_watch", "mood_board"}
    assert r["h3_present"] is True
    ir = rule_label("app keeps crashing on login otp")
    assert ir["is_relevant"] is False
    assert set(coerce({}, "x")) | {"doc_id"} >= (set(OUT_COLUMNS) - {
        "doc_id", "source", "platform", "url", "posted_date", "rating", "raw_text"})
    print("selftest OK")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Dual-hypothesis classification -> classified_data.csv")
    ap.add_argument("-i", "--input", default="raw_data.csv")
    ap.add_argument("-o", "--output", default="classified_data.csv")
    ap.add_argument("--model", default="gemini-flash-lite-latest",
                    help="flash-lite = higher free-tier quota")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between calls (free-tier RPM)")
    ap.add_argument("--limit", type=int, default=0, help="max NEW rows (0 = all)")
    ap.add_argument("--no-fallback", action="store_true",
                    help="write parse_error rows instead of the rule fallback (for auditing quota loss)")
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
    print(f"{len(rows)} rows, {len(done)} done, {len(todo)} to classify.", file=sys.stderr)
    if not todo:
        print("Nothing to do.")
        return

    model = make_model(args.model)
    fout, writer = open_appender(args.output)
    carry = ("doc_id", "source", "platform", "url", "posted_date", "rating", "raw_text")
    n_done = n_fallback = 0
    try:
        for start in range(0, len(todo), args.batch):
            chunk = todo[start:start + args.batch]
            texts = [r["raw_text"] for r in chunk]
            labels = None
            for attempt in range(3):
                try:
                    labels = classify_batch(model, texts)
                    break
                except Exception as e:  # noqa: BLE001 — free-tier 429s must not lose rows
                    wait = args.sleep * (attempt + 1) * 3
                    print(f"  batch {start} attempt {attempt+1} err: {e}; retry in {wait:.0f}s",
                          file=sys.stderr)
                    time.sleep(wait)
            if labels is None:
                labels = ([empty_labels(t) for t in texts] if args.no_fallback
                          else [rule_label(t) for t in texts])
                n_fallback += 0 if args.no_fallback else len(chunk)
                print(f"  batch {start} -> {'parse_error' if args.no_fallback else 'rule_fallback'}",
                      file=sys.stderr)
            for r, lab in zip(chunk, labels):
                writer.writerow({**{k: r.get(k, "") for k in carry}, **lab})
            fout.flush()
            n_done += len(chunk)
            print(f"  classified {n_done}/{len(todo)}", file=sys.stderr)
            time.sleep(args.sleep)
    finally:
        fout.close()
    print(f"Done. Appended {n_done} rows to {args.output} "
          f"({n_fallback} via rule fallback — logged, not AI).")


if __name__ == "__main__":
    main()
