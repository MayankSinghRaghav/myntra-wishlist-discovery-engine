"""
classify.py — Stage 3+4 (Extract + Map). Break each relevant passage into ATOMIC CLAIMS,
map each to a frozen hypothesis (H1|H2|H3|other) with a STANCE (supports|contradicts|neutral),
and attach a verbatim quote. Diagnosis only — NEVER a solution/feature (see the build spec).

The engine must be able to KILL a hypothesis: a claim that *contradicts* a hypothesis is as
valuable as one that supports it, and is surfaced with stance="contradicts".

Writes claims.csv, one row per atomic claim (+ a marker row per doc with no claims), carrying
full provenance so every claim is independently re-verifiable (build-spec prohibition #4).
Batched, resumable (skips doc_ids already written), free-tier friendly, with a tagged rule
fallback that is NEVER counted as AI.

Env:  GEMINI_API_KEY
Run:  python classify.py -i raw_data.csv -o claims.csv
      python classify.py --limit 30        # small live test
      python classify.py --selftest        # offline coercion + stance + span checks
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time

# ---- closed label sets (frozen) ---------------------------------------------
HYPOTHESES = {"h1", "h2", "h3", "other"}
STANCES = {"supports", "contradicts", "neutral"}
# product category is the only reliably text-inferable segment axis (age/geo rarely are)
CATEGORIES = {"ethnic", "western_top", "bottoms", "dress", "footwear",
              "accessory", "beauty", "outerwear", "other", ""}

CLAIM_COLUMNS = [
    "claim_id", "doc_id", "source", "platform", "url", "posted_date",
    "is_relevant", "claim_text", "hypothesis", "stance", "quote", "category", "method",
]

PROMPT = """You analyse public texts (app reviews, YouTube/Reddit comments) about shopping on
Myntra, an Indian fashion app. A PM is diagnosing why users SAVE items to a wishlist but do NOT
buy them. You surface EVIDENCE only — never propose a fix, feature, or solution.

Three FROZEN, competing hypotheses (a claim may support one, contradict one, or be neutral):
- H1 PURCHASE-TIME UNCERTAINTY: the item is still wanted but an UNRESOLVED fit/size/quality/
  return-safety doubt stalls commitment.
- H2 RELEVANCE DECAY: intent was real at save-time but the trigger expired (occasion passed,
  season turned, need met elsewhere, look dated).
- H3 WISHLIST != PURCHASE INTENT: the save was never a deferred purchase (inspiration, comparison,
  bookmark, aspiration, price-watch).

SCOPE — this diagnosis is about the SAVE→BUY decision (why a saved/wishlisted/considered item is or
is NOT bought). Map a claim to H1/H2/H3 ONLY when it bears on that pre-purchase decision. A complaint
about a COMPLETED purchase (wrong/old item delivered, return rejected, bad delivery, "Myntra is fraud")
is post-purchase experience — set its hypothesis to "other", UNLESS the person explicitly ties it to
now hesitating on SAVED items (a return-safety fear about future buys, which is H1). Do not inflate a
hypothesis with post-purchase grievances.

Return a JSON array, EXACTLY one object per input text, same order. Each object:
- is_relevant (bool): true if it concerns a fashion saving/wishlist/consideration/buy-or-not decision
  OR a fit/size/quality/return-safety judgement that could affect one. false for pure app-bug/login/
  crash/payment/spam/off-topic and for generic app praise or gripes with no decision content.
- claims (array): 0-3 ATOMIC claims extracted from THIS text (one behaviour/motivation each).
  [] if irrelevant or nothing about wishlist->purchase. Each claim:
    - claim_text: one atomic statement of the behaviour/motivation (<=160 chars). No solutions.
    - hypothesis: the hypothesis this claim bears on — "H1" | "H2" | "H3" | "other".
    - stance: toward that hypothesis — "supports" | "contradicts" | "neutral".
      (e.g. "I always buy what I save" CONTRADICTS H3; "just saving for inspo" SUPPORTS H3;
       "knew my size, just forgot" CONTRADICTS H1 and SUPPORTS H2 — pick the sharper mapping.)
    - quote: EXACT verbatim substring of the input text that grounds the claim (required).
    - category: product category if identifiable — one of ethnic|western_top|bottoms|dress|
      footwear|accessory|beauty|outerwear|other, else "".

Rules: do NOT invent. quote MUST be copied verbatim; a claim with no verbatim quote is invalid.
Contradicting evidence is as important as supporting — surface it. Use closed values only.
Texts:
{texts}"""


# ---------------------------------------------------------------- coercion
def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def one_of(v, allowed: set[str], default: str) -> str:
    s = str(v).strip().lower()
    return s if s in allowed else default


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def verify_span(span: str, text: str, limit: int = 200) -> str:
    """Return span iff it is a (whitespace/case-normalized) substring of text; else ""."""
    span = str(span or "").strip()[:limit]
    if not span:
        return ""
    return span if _norm(span) and _norm(span) in _norm(text) else ""


def norm_hyp(v) -> str:
    return one_of(v, HYPOTHESES, "other")


def coerce_claim(obj: dict, text: str) -> dict | None:
    """One raw claim -> validated fields, or None if it can't ship (no text / no verbatim quote)."""
    claim_text = str(obj.get("claim_text", "") or "").strip()[:160]
    if len(claim_text) < 6:
        return None
    quote = verify_span(obj.get("quote"), text)  # build-spec #4: no traceable quote => flagged out
    return {
        "claim_text": claim_text,
        "hypothesis": norm_hyp(obj.get("hypothesis")),
        "stance": one_of(obj.get("stance"), STANCES, "neutral"),
        "quote": quote,
        "category": one_of(obj.get("category"), CATEGORIES, "other"),
    }


def _doc_rows(doc: dict, is_rel: bool, claims: list[dict], method: str) -> list[dict]:
    """Expand one document into claim rows (or a single marker row if it has none)."""
    carry = {k: doc.get(k, "") for k in ("doc_id", "source", "platform", "url", "posted_date")}
    base = {**carry, "is_relevant": is_rel, "method": method}
    if not claims:  # keep a marker so resume skips this doc and corpus counts stay honest
        return [{**base, "claim_id": f"{doc['doc_id']}#0", "claim_text": "",
                 "hypothesis": "", "stance": "", "quote": "", "category": ""}]
    return [{**base, "claim_id": f"{doc['doc_id']}#{i}", **c} for i, c in enumerate(claims)]


# ---------------------------------------------------------------- rule fallback
_IRRELEVANT = re.compile(r"\b(crash|login|log in|otp|payment fail|app not open|server error|hang)\b", re.I)
_RULES = [  # (regex, hypothesis, stance) — coarse, clearly-tagged fallback only
    (re.compile(r"\b(not sure|unsure|which size|will it fit|true to size|size chart|quality|"
                r"material|fabric|original|authentic|fake|return)\b", re.I), "h1", "supports"),
    (re.compile(r"\b(forgot|forget|already bought|already got|no longer|don'?t need|occasion|"
                r"season|was for)\b", re.I), "h2", "supports"),
    (re.compile(r"\b(inspo|inspiration|mood ?board|just saving|wait for (a )?(sale|offer)|"
                r"price drop|see later|just browsing|comparing)\b", re.I), "h3", "supports"),
]


def rule_claims(text: str) -> tuple[bool, list[dict]]:
    """Deterministic keyword fallback. Tagged rule_fallback upstream — never AI output."""
    t = text or ""
    if _IRRELEVANT.search(t) or len(t) < 12:
        return False, []
    claims = []
    for rx, hyp, stance in _RULES:
        m = rx.search(t)
        if m:
            quote = t[m.start():m.start() + 80].strip()
            claims.append({"claim_text": t[:120].strip(), "hypothesis": hyp, "stance": stance,
                           "quote": verify_span(quote, t), "category": "other"})
    return True, [c for c in claims if c["quote"]]


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


def classify_batch(model, docs: list[dict]) -> list[dict]:
    texts = [d["raw_text"] for d in docs]
    numbered = "\n".join(f"[{i}] {t[:800]}" for i, t in enumerate(texts))
    resp = model.generate_content(PROMPT.format(texts=numbered))
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("["):]
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("model did not return a list")

    rows: list[dict] = []
    for i, doc in enumerate(docs):
        obj = data[i] if i < len(data) and isinstance(data[i], dict) else {}
        is_rel = as_bool(obj.get("is_relevant"))
        claims = []
        if is_rel:
            for c in (obj.get("claims") or [])[:3]:
                cc = coerce_claim(c, doc["raw_text"]) if isinstance(c, dict) else None
                if cc:
                    claims.append(cc)
        rows += _doc_rows(doc, is_rel, claims, "gemini")
    return rows


# ---------------------------------------------------------------- io
def load_done(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {row["doc_id"] for row in csv.DictReader(f)}


def open_appender(path: str):
    exists = os.path.exists(path)
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=CLAIM_COLUMNS)
    if not exists:
        w.writeheader()
    return f, w


# ---------------------------------------------------------------- selftest
def _selftest() -> None:
    assert norm_hyp("H1") == "h1" and norm_hyp("junk") == "other"
    assert one_of("CONTRADICTS", STANCES, "neutral") == "contradicts"
    assert verify_span("not SURE", "i'm not sure of size") == "not SURE"
    assert verify_span("invented", "different text") == ""
    # a claim with no verbatim quote can't ship
    assert coerce_claim({"claim_text": "users just browse", "quote": "invented"}, "real text") == \
        {"claim_text": "users just browse", "hypothesis": "other", "stance": "neutral",
         "quote": "", "category": "other"}
    good = coerce_claim({"claim_text": "always buy what I save", "hypothesis": "H3",
                         "stance": "contradicts", "quote": "always buy what I save",
                         "category": "ethnic"}, "i always buy what I save eventually")
    assert good["hypothesis"] == "h3" and good["stance"] == "contradicts" and good["category"] == "ethnic"
    # doc with no claims -> single marker row; with claims -> one row each
    doc = {"doc_id": "d1", "source": "reddit", "platform": "reddit_post", "url": "u", "posted_date": ""}
    assert len(_doc_rows(doc, False, [], "gemini")) == 1
    rows = _doc_rows(doc, True, [good], "gemini")
    assert len(rows) == 1 and rows[0]["claim_id"] == "d1#0" and rows[0]["stance"] == "contradicts"
    rel, cl = rule_claims("not sure of the size, might return it")
    assert rel and cl and cl[0]["hypothesis"] == "h1" and cl[0]["quote"]
    assert rule_claims("app keeps crashing on login")[0] is False
    assert set(CLAIM_COLUMNS) >= set(rows[0])
    print("selftest OK")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Extract atomic claims + stance -> claims.csv")
    ap.add_argument("-i", "--input", default="raw_data.csv")
    ap.add_argument("-o", "--output", default="claims.csv")
    ap.add_argument("--model", default="gemini-flash-lite-latest")
    ap.add_argument("--batch", type=int, default=15)
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=0, help="max NEW docs (0 = all)")
    ap.add_argument("--no-fallback", action="store_true", help="mark quota-lost docs, skip rule fallback")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        _selftest()
        return

    with open(args.input, encoding="utf-8") as f:
        docs = list(csv.DictReader(f))
    done = load_done(args.output)
    todo = [d for d in docs if d["doc_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(docs)} docs, {len(done)} done, {len(todo)} to process.", file=sys.stderr)
    if not todo:
        print("Nothing to do.")
        return

    model = make_model(args.model)
    fout, writer = open_appender(args.output)
    n_docs = n_claims = n_fallback = 0
    try:
        for start in range(0, len(todo), args.batch):
            chunk = todo[start:start + args.batch]
            rows = None
            for attempt in range(3):
                try:
                    rows = classify_batch(model, chunk)
                    break
                except Exception as e:  # noqa: BLE001 — free-tier 429s must not lose docs
                    wait = args.sleep * (attempt + 1) * 3
                    print(f"  batch {start} attempt {attempt+1} err: {e}; retry in {wait:.0f}s",
                          file=sys.stderr)
                    time.sleep(wait)
            if rows is None:
                if args.no_fallback:
                    rows = [_doc_rows(d, False, [], "quota_lost")[0] for d in chunk]
                else:
                    rows = []
                    for d in chunk:
                        rel, cl = rule_claims(d["raw_text"])
                        rows += _doc_rows(d, rel, cl, "rule_fallback")
                    n_fallback += len(chunk)
                print(f"  batch {start} -> {'quota_lost' if args.no_fallback else 'rule_fallback'}",
                      file=sys.stderr)
            for r in rows:
                writer.writerow(r)
            fout.flush()
            n_docs += len(chunk)
            n_claims += sum(1 for r in rows if r["claim_text"])
            print(f"  processed {n_docs}/{len(todo)} docs, {n_claims} claims", file=sys.stderr)
            time.sleep(args.sleep)
    finally:
        fout.close()
    print(f"Done. {n_docs} docs -> {n_claims} claims in {args.output} "
          f"({n_fallback} docs via rule fallback — logged, not AI).")


if __name__ == "__main__":
    main()
