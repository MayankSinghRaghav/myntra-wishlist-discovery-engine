# Myntra Wishlist→Purchase — AI Discovery Engine

Ingests a public-evidence corpus about Myntra wishlist→purchase behaviour and emits a **ranked
register of atomic claims** — each mapped to a **frozen hypothesis**, each carrying a **stance**
(supports / contradicts / neutral) and **traceable provenance** — so claims can be audited
per-claim against blind interviews.

> **This engine diagnoses and stops. It proposes no solution, feature, or ranking of fixes.**
> The solution is chosen later, from the diagnosis, by a human. (This guardrail is deliberate — the
> attempt-2 failure was the engine's architecture leaking into the solution.)

Hypothesis generator over complaint-skewed public text — **not proof.** Every claim is for primary
research to confirm or kill (see the audit seam below).

## The frozen hypotheses (see [`hypotheses.md`](hypotheses.md), committed before any run)
- **H1 — purchase-time uncertainty** stalls still-wanted items (fit/size/quality/return-safety).
- **H2 — relevance decays** inside the 30-day window (occasion/season/need expires).
- **H3 — wishlist add ≠ purchase intent** (inspiration, comparison, bookmark, aspiration).

They **compete, not stack.** We expect at least one to die — the engine must be able to surface
evidence that **kills** a hypothesis, so a claim that *contradicts* a hypothesis is kept and
labelled `stance = contradicts`, never collapsed.

## Pipeline (7 stages)

```
collect.py / ingest_apify.py → raw_data.csv       public text (Play + YouTube + Reddit), PII-stripped, deduped
classify.py                  → claims.csv          Gemini: is_relevant + ATOMIC CLAIMS {claim_text, hypothesis(H1|H2|H3|other), stance, verbatim quote, category}
analyze.py                   → claims_register.json ranked claims: source_quotes[], n_independent_srcs, inferred_segment, engine_confidence, thin_evidence, audit_verdict("")
                             → corpus_manifest.json honest source counts by platform + date range (slide-3 corpus size)
                             → early_signal.md      pre-interview lean per hypothesis + segment signal for the interview screener
                             → data.json            dashboard artifact
build_static.py              → index.html           self-contained dashboard (inlines dashboard.js + data.json; 0 external requests), client-side RAG, NO API key
```

## Output contract — `claims_register.json`
One record per atomic claim (the seam into the deck's slide-4 audit table):

| field | meaning |
|---|---|
| `claim_id` | ranked id (C001…) |
| `claim_text` | atomic statement (a behaviour/motivation), no solution language |
| `hypothesis_map` | `H1` \| `H2` \| `H3` \| `other` |
| `stance` | `supports` \| `contradicts` \| `neutral` (toward `hypothesis_map`) |
| `theme` | closed domain theme (fit_size, quality, returns_delivery, inspiration, …) |
| `source_quotes[]` | `{verbatim, url, platform, date}` — ≥1 required, else the claim is dropped (untraceable) |
| `n_independent_srcs` | distinct platforms corroborating the claim |
| `inferred_segment` | `{category}` or `null` (age/geo not reliably inferable from public text) |
| `engine_confidence` | `low` \| `med` \| `high` + one-line basis |
| `thin_evidence` | `true` if a single platform |
| `audit_verdict` / `audit_note` | **left blank** — filled later from blind interviews: Held up / Partly invented / Rejected |

`corpus_manifest.json` — real counts by platform + date range. `early_signal.md` — one page:
which hypotheses the corpus leans toward/against, and the category concentration that sets the
interview screener. Explicitly caveated as pre-interview, corpus-only, not conclusions.

## Guardrails (built in, not vibes)
- **No solution language** anywhere in the output — diagnosis only.
- **No aggregate "agreement %" as a headline.** Verdicts are per-claim, filled by primary research.
- **Contradicting evidence is never collapsed** — surfaced with `stance = contradicts`.
- **Every claim re-verifiable from stored provenance.** No verbatim quote (checked as a substring of
  its source) ⇒ the claim does not ship; it goes to the discard pile.
- **Cross-source rule** — corroboration is shown via `n_independent_srcs`; single-platform claims are
  flagged `thin`. The RAG chat **refuses** on thin or single-platform evidence.
- **No fabricated corpus counts** — the manifest states the true numbers, including thin areas and
  connectors wired-but-not-ingested (Apple App Store / X / Quora).
- **Rule-based fallback** exists so the free tier never hard-fails, and is **never counted as AI**.

## Run it

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt

# 1. Collect (Play keyless; YouTube keyless; Reddit needs a free key)
python collect.py --play-count 2500 --also-relevant 500 -o raw_data.csv
python collect.py --youtube videos.txt --per-video 300 -o raw_data.csv
export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
python collect.py --reddit -o raw_data.csv
# If YouTube/Reddit block your IP (429/403), collect on Apify's cloud instead (see below).

# 2. Extract atomic claims + stance (batched, resumable — safe to Ctrl-C / re-run)
export GEMINI_API_KEY=your_key      # PowerShell: $env:GEMINI_API_KEY="your_key"
python classify.py --limit 30       # small live test first
python classify.py                  # full corpus -> claims.csv

# 3. Rank register + manifest + early signal
python analyze.py                   # -> claims_register.json, corpus_manifest.json, early_signal.md, data.json
python build_static.py              # inline dashboard.js + data.json -> self-contained index.html

# 4. Dashboard (static — just serve the folder)
python -m http.server 8099          # open http://localhost:8099

# offline sanity checks (no network, no key)
python test_pipeline.py
```

Each script has `--selftest` and `-h`. All prompts are in the source: the extraction prompt is
`PROMPT` in [`classify.py`](classify.py); the hypotheses + kill-conditions are in [`hypotheses.md`](hypotheses.md).

### Cloud collection fallback (Apify) — when YouTube/Reddit block your IP
`collect.py` works for Play everywhere, but YouTube/Reddit rate-limit some networks (429 / 403).
Run those on Apify's cloud and normalize with `ingest_apify.py`:

- YouTube: [`streamers/youtube-comments-scraper`](https://apify.com/streamers/youtube-comments-scraper) — `{startUrls:[{url}], maxComments, sortCommentsBy}`
- Reddit: [`trudax/reddit-scraper-lite`](https://apify.com/trudax/reddit-scraper-lite) — `{searches:[...], maxItems, sort}`

Download each dataset (`https://api.apify.com/v2/datasets/<id>/items?format=json&clean=true`, public — no token) to `yt.json` / `reddit.json`, then:

```bash
python ingest_apify.py --play raw_data.csv --youtube yt.json --reddit reddit.json -o raw_data.csv
```

Author/username are dropped; Reddit HTML + "submitted by" boilerplate stripped; deduped against Play.

## Deploy (Vercel — static, keyless, free)
`python build_static.py` inlines `dashboard.js` + `data.json` into a self-contained `index.html`
(ad-blockers block generic root-level scripts like `/app.js`, so the deployed page fetches nothing).

```bash
npm i -g vercel
vercel --prod
```

No env vars, no secrets — the app only reads the committed (PII-stripped) `data.json` and never calls an LLM.

## The audit seam (engine ↔ synthesis)
`audit_verdict` / `audit_note` are the interface between this engine and the interview-synthesis
phase. The engine ships them **blank**; the synthesis phase fills them from blind-coded interviews.
The schema is kept stable so the two halves stay compatible.

## Data & privacy
- **No PII.** Author names/handles are never stored — only public text, date, source URL, labels.
- **No fabricated volume.** Every row/claim traces to a real public post; per-source counts are honest.
- Dedup by SHA-256 of normalized text.

## Limitations
Complaint-skewed · English-biased collection · public text is a **proxy** for the wishlist funnel ·
no true per-user frequencies · only 3 platforms ingested so far (App Store / X / Quora are thin).
