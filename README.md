# Myntra Wishlist→Purchase — AI Discovery Engine

Mines public user text to test **why people save fashion items on Myntra but don't buy them**.
Unlike a typical theme-ranker, this engine is built to **produce disconfirming evidence**: three
hypotheses are **pre-registered before any run**, every document is coded **independently** on all
three, results are reported **per intent-segment (never averaged)**, and every AI-surfaced claim
lands in an **audit table** for primary research to confirm or kill.

> Hypothesis generator over complaint-skewed public text — **not proof.** Shares are
> complaint-share, not user prevalence. Every wishlist→purchase link is a hypothesis.

## Why this shape (what changed)

A ranked "opportunity score" picks a winner and primes every downstream source to agree. This
engine has **no single ranked output**. Its unit of output is *evidence share per hypothesis, per
segment* — a **split** (e.g. "H1 leads deferred-purchase, H3 leads mood-board") is the target
finding, and a hypothesis can be **rejected** by pre-registered thresholds.

### Pre-registered hypotheses (see [`hypotheses.md`](hypotheses.md), committed before any run)
- **H1 — Uncertainty blocks conversion** (fit/size/quality/authenticity/styling/social unresolved).
- **H2 — Relevance decays** (occasion passed, trend moved, forgot, bought elsewhere).
- **H3 — Wishlist ≠ purchase intent** (mood-board, price-watch, catalogue-browse, size-hold).

## Pipeline

```
collect.py   →  raw_data.csv          public text (Play + YouTube + Reddit), PII-stripped, deduped
classify.py  →  classified_data.csv   Gemini: is_relevant, intent_segment, H1/H2/H3 {present,conf,verbatim span}, topic
analyze.py   →  data.json             H1/H2/H3 × segment matrix, "none" share, model-mix, audit table, discard pile, RAG index
             →  audit_table.csv/.md    Claim | Sources | Docs | 3 verbatim quotes | Verdict(pending)
             →  holdout_sample.csv     blind hold-out template + holdout_rubric.md
             →  findings.md            honest narrative (the split, decisions, discard pile, limits)
index.html   →  static dashboard       reads data.json, client-side RAG, NO API key at runtime
```

## Design guarantees

- **Pre-registration.** Classification cannot run until `hypotheses.md` is committed; that commit
  is the timestamp. Decision thresholds (support ≥15%, reject <8% & leads no segment) are set there.
- **Independent dual-hypothesis coding.** A doc may support several / one / **none**; the **"none"
  share is tracked and reported**, not hidden.
- **Closed taxonomy only** — no free-form theme invention (segments + topics are fixed enums,
  out-of-set values are coerced).
- **Every quote verbatim-checked.** A span is kept only if it is a normalized substring of its
  source; a hypothesis flagged `present` with no verifiable span is downgraded to absent.
- **Cross-source rule.** A claim is reported only with **≥2 independent sources**; single-source
  themes go to the discard pile. The RAG chat **refuses** on thin or single-source evidence.
- **Model-mix transparency + rule fallback.** If the free tier fails a batch, rows fall back to a
  keyword **rule classifier tagged `rule_fallback`** — logged, surfaced, and **never counted as AI**.
- **Discard pile shown** — not-relevant rows, "none" docs, weak/single-source cells.
- **Blind hold-out.** `holdout_sample.csv` is hand-coded against the same rubric; agreement is
  reported once, plainly.

All prompts are in the source: the classification prompt is `PROMPT` in
[`classify.py`](classify.py); the coding rules and thresholds are in [`hypotheses.md`](hypotheses.md).

## Run it

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt

# 1. Collect ≥2 sources (Play keyless; YouTube keyless; Reddit needs a free key)
python collect.py --play-count 2500 --also-relevant 500 -o raw_data.csv
python collect.py --youtube videos.txt --per-video 300 -o raw_data.csv   # 1 Myntra-haul URL per line
export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
python collect.py --reddit -o raw_data.csv

# 2. Classify (batched, resumable — safe to Ctrl-C / re-run; free-tier flash-lite)
export GEMINI_API_KEY=your_key      # PowerShell: $env:GEMINI_API_KEY="your_key"
python classify.py --limit 30       # small live test first
python classify.py                  # full corpus

# 3. Analyze → data.json + audit table + findings
python analyze.py

# 4. Dashboard (static — just serve the folder)
python -m http.server 8099          # open http://localhost:8099

# offline sanity checks (no network, no key)
python test_pipeline.py
```

Each script has `--selftest` and `-h`.

## Deploy (Vercel — static, keyless, free)

The site is plain `index.html` + `app.js` + `data.json` (no framework, no build). `vercel.json`
pins it as a static project.

```bash
npm i -g vercel
vercel            # first deploy (preview)
vercel --prod     # public URL
```

Or connect the GitHub repo in the Vercel dashboard → Framework **Other** → Deploy. No env vars,
no secrets: the app only reads the committed (PII-stripped) `data.json` and never calls an LLM.

## Data & privacy

- **No PII.** Author names/handles are never stored — only public text, rating, date, source URL, labels.
- **No fabricated volume.** Every row traces to a real public post; per-source counts are logged honestly.
  A connector wired but not ingested is labelled as such, not padded.
- Dedup by SHA-256 of normalized text.

## Limitations

Complaint-skewed · English-biased collection · app/forum text is a **proxy** for the wishlist
funnel · no true per-user frequencies. Full paragraph in [`findings.md`](findings.md).
