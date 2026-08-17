# Myntra Wishlist→Purchase — Discovery Engine

An AI-powered **product-discovery engine** for a Growth-PM case study. It mines
public user text to discover *why people save fashion items on Myntra but don't buy them*,
classifies the **non-price** barriers, ranks opportunities, and exposes everything in a
deployed dashboard.

> It is a **hypothesis generator, not proof.** Reach = *complaint-share*, not true prevalence.
> Every wishlist→purchase link is a hypothesis to validate with product analytics/experiments.

**Goal:** raise the 30-day **Wishlist→Purchase** user conversion rate.
**Hard constraint:** no monetary incentives (no discounts/coupons/cashback) — so we hunt
non-price barriers: uncertainty, confidence, timing, decision quality.

### 🔴 Kill-switch metric
We explicitly measure the share of texts whose blocker is **price** (`intent=price_waiter`
OR `price_value` barrier) vs **non-price**. If price dominates, the whole non-monetary
strategy has a low ceiling. That number is reported in [`findings.md`](findings.md) and on
the dashboard.

---

## Pipeline

```
collect.py   →  raw_data.csv          public text (Play / YouTube / Reddit), PII-stripped, deduped
classify.py  →  classified_data.csv   Gemini labels (barrier, intent, journey, emotion, evidence span)
analyze.py   →  opportunities.csv      gated + scored opportunities
             →  findings.md            insight cards + kill-switch number + limitations
app.py       →  Streamlit dashboard    reads the CSVs, NO Gemini at runtime (keyless)
```

## Setup

```bash
python -m venv .venv && . .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-pipeline.txt              # to re-run the pipeline
pip install -r requirements.txt                       # just to run the app
```

Gemini key (classification only — never hardcoded):

```bash
export GEMINI_API_KEY=your_key      # PowerShell: $env:GEMINI_API_KEY="your_key"
```

## Run each step

```bash
# 1. Collect (~2500 Play Store reviews; add YouTube/Reddit optionally)
python collect.py --play-count 2500 -o raw_data.csv
python collect.py --youtube videos.txt --per-video 300 -o raw_data.csv   # 1 URL per line
python collect.py --reddit                                               # needs REDDIT_CLIENT_ID/SECRET

# 2. Classify with Gemini (batched, resumable — safe to re-run / Ctrl-C)
python classify.py -i raw_data.csv -o classified_data.csv
python classify.py --limit 30            # small test run first

# 3. Analyze → opportunities + findings
python analyze.py -i classified_data.csv
python analyze.py --embedder st          # optional: sentence-transformers MiniLM sub-themes

# 4. Dashboard
streamlit run app.py

# offline sanity checks (no network, no key)
python test_pipeline.py
```

Each script has `--selftest` and `-h`.

## Deploy (Streamlit Community Cloud)

Repo: <https://github.com/MayankSinghRaghav/myntra-wishlist-discovery-engine>

**One-click deploy:**
<https://share.streamlit.io/deploy?repository=MayankSinghRaghav/myntra-wishlist-discovery-engine&branch=main&mainModule=app.py>

Or manually:
1. Go to <https://share.streamlit.io> → sign in with GitHub → **Create app** → **Deploy a public app from GitHub**.
2. Repository `MayankSinghRaghav/myntra-wishlist-discovery-engine`, branch `main`, main file `app.py`.
3. **No secrets needed** — the app only reads the committed (PII-stripped) CSVs and never calls Gemini. Deploy → public URL.

`requirements.txt` is intentionally minimal (streamlit/pandas/plotly) to keep the cloud build
fast; the heavier pipeline deps live in `requirements-pipeline.txt`.

## Data & privacy

- **No PII committed.** Author names/handles are never stored — only public review text,
  rating, date, source URL, and labels.
- **No fabricated data.** Every row traces to a real public post; every label carries a
  verbatim `evidence_span` for hand-auditing.
- Dedup by SHA-256 of normalized text.

## Taxonomy (barriers)

`fit_uncertainty, size_uncertainty, quality_uncertainty, authenticity_trust,
style_occasion_match, choice_overload, info_insufficient, conflicting_reviews,
social_validation_need, needs_external_comparison, price_value, delivery_returns,
stockout, forgetting, none, other`

Opportunity score = `2·MetricRelevance + 1.5·Severity + 1·Reach`, then × evidence discount
(explicit 1.0 / strong 0.7 / weak 0.4). Monetary (`price_value`) and non-actionable
(`none`, `other`) barriers are **gated out** and logged.

## Limitations

Complaint-skewed · English-skewed · app-review text ≠ the wishlist funnel · no true
frequencies. See the full paragraph in [`findings.md`](findings.md).
