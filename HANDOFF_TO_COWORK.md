# Discovery Engine → Cowork handoff (Build 1 output for deck slides 3–4)

**Repo:** github.com/MayankSinghRaghav/myntra-wishlist-discovery-engine (public, all prompts visible)
**Live URL:** _pending Vercel deploy (Mayank to connect the repo — static, no build)._
**Generated against:** `hypotheses.md` FROZEN 2026-08-20 07:20 IST. Classification ran AFTER the
freeze commit — pre-registration intact.

This engine **diagnoses and stops.** It proposes no solution or feature. Everything below is
public-evidence signal for the interviews to confirm or kill — not a conclusion.

---

## 1. What you consume (three artifacts, all in the repo root)

| File | Purpose | Feeds |
|---|---|---|
| `claims_register.json` | ranked atomic claims w/ stance + provenance + blank verdict fields | **slide 4 audit table** |
| `corpus_manifest.json` | honest source counts + date range | **slide 3 corpus size** |
| `early_signal.md` | pre-interview hypothesis lean + screener segment | interview screener (`04_interview_guide.md` §0) |

The dashboard (Vercel URL) is the slide-3 "live link" — it renders all three plus a keyless RAG
that refuses on thin/off-corpus queries.

## 2. `claims_register.json` schema (the seam into your audit table)

One JSON array; one object per atomic claim. **The two audit fields are shipped BLANK — you fill
them from the blind-coded interviews.** Keep the schema stable so the two halves stay compatible.

| field | type | meaning |
|---|---|---|
| `claim_id` | str | ranked id, `C001`… (rank = confidence, then frequency, then #sources) |
| `claim_text` | str | atomic statement of ONLY what the quote says — no invented reasoning, no solution |
| `hypothesis_map` | enum | `H1` \| `H2` \| `H3` \| `other` |
| `stance` | enum | `supports` \| `contradicts` \| `neutral` — toward `hypothesis_map` |
| `theme` | str | closed domain theme (fit_size, quality, returns_delivery, inspiration, price_watch, …) |
| `source_quotes` | array | `[{verbatim, url, platform, date}]` — ≥1, every one re-openable to source |
| `n_independent_srcs` | int | distinct platforms corroborating |
| `inferred_segment` | obj\|null | `{category}` or null (age/geo not inferable from public text) |
| `engine_confidence` | enum | `low` \| `med` \| `high` (+ `confidence_basis` one-liner) |
| `thin_evidence` | bool | true = single platform |
| `corpus_frequency` | int | # passages behind the claim |
| **`audit_verdict`** | str | **BLANK** → you set: `held up` \| `partly invented` \| `rejected` |
| **`audit_note`** | str | **BLANK** → your one-line rationale from interviews |

**Example record (verbatim from the output):**
```json
{
 "claim_id": "C001",
 "claim_text": "The user uses the app for window shopping.",
 "hypothesis_map": "H3", "stance": "supports", "theme": "misc",
 "source_quotes": [
   {"verbatim": "best place for window shopping", "url": "https://play.google.com/…", "platform": "google_play", "date": "2026-08-15"},
   {"verbatim": "i enjoy window shopping hahaha!", "url": "https://play.google.com/…", "platform": "google_play", "date": "2026-06-10"}
 ],
 "n_independent_srcs": 1, "inferred_segment": null,
 "engine_confidence": "med", "thin_evidence": true, "corpus_frequency": 3,
 "audit_verdict": "", "audit_note": ""
}
```

## 3. Composition (slide-3 numbers — all real, none padded)

- **Corpus:** 4,756 documents → **249 relevant (5.2%)** → 259 atomic claims → **236 traceable** →
  **224 register entries** (23 claims dropped for no verbatim quote — see discard pile).
- **Platforms (3 independent):** google_play 4,256 · youtube 328 · reddit 172. Date range
  2018-10-12 → 2026-08-18. Not ingested (thin/planned): Apple App Store, X, Quora.
- **Model mix:** 100% Gemini on the final run (0 rule-fallback). The rule-based fallback exists and
  is always tagged; it is never counted as AI.
- **Hypothesis lean (supports − contradicts, claim counts):**

  | Hypothesis | supports | contradicts | neutral | net |
  |---|---|---|---|---|
  | H1 purchase-time uncertainty | 145 | **27** | 20 | +118 |
  | H2 relevance decay | 11 | 0 | 1 | +11 |
  | H3 wishlist ≠ intent | 22 | **3** | 4 | +19 |

  **30 contradicting claims surfaced** — the engine is structurally able to help kill a hypothesis,
  not just confirm. That capability is the point; the counts are complaint-share, not prevalence.

## 4. Slide-4 starter rows (strongest candidates already in the register)

Concrete claims to seed the audit table (each traceable in `claims_register.json`):

**H1 supports** — `C002` "Will refrain from buying next time due to exchange-only return policy"
(**2 platforms**, the only cross-source entry) · `C003` "Bad return/refund experience ruins trust →
return-safety hesitation for future buys."
**H2 supports** — `C010`/`C011` occasion-timing: gift/event items whose delivery missed the date.
**H3 supports** — `C001` "uses the app for window shopping" (n=3) · comparison-tool usage.
**Kill-signal (H1 contradicts)** — `C004` "no-questions-asked return removes hesitation", `C050`
"hassle-free return reduces hesitation." → Myntra's return policy cuts BOTH ways: bad experiences
feed H1, easy returns argue against it. Worth an explicit interview probe.

## 5. Honest limitations — put these ON slides 3–4, don't bury them

These are the credibility of the engine, not caveats to hide:

1. **Corroboration is thin: 223 of 224 claims are single-platform, low-confidence.** Only ONE claim
   reaches ≥2 independent platforms. This is real, not a bug — I verified 12/31 theme buckets do
   mix platforms topically, but individual claims rarely restate closely enough across authors to
   merge. **Read: the public corpus supports the interviews; it cannot carry the diagnosis alone.**
2. **Complaint-skewed proxy.** App-store/forum text over-represents the frustrated and is a PROXY
   for the wishlist funnel — not the funnel itself. Every wishlist→purchase link here is a hypothesis.
3. **H1 support leans on return/delivery experience**, which is partly post-purchase. The interviews
   must test whether return-safety fear actually blocks SAVED-item purchase (H1) vs. being general
   post-purchase grievance. The engine routes pure grievances to `other`, but the boundary is fuzzy.
4. **H2 has zero contradicting evidence** in the corpus — weak kill-signal for H2 specifically;
   the H2-vs-H3 discrimination protocol (`hypotheses.md`) will have to do that work in interviews.
5. **Discard pile (shown for honesty):** 4,507 not-relevant docs · 23 claims dropped for no traceable
   quote · 223 thin single-platform claims. Nothing was quietly kept.

## 6. What the engine does NOT say
No solution, no feature, no ranked "opportunity." No aggregate "engine was X% right." The verdict on
each claim comes from your interviews (§2), not from the engine. Segment recommendation (screener):
over-sample recent wishlist users in the leading product categories (bottoms / western_top / ethnic);
recruit age/geo open — not inferable from public text.

---
_Engineering: Claude Code. Diagnosis-only engine per the frozen build spec. Reproduce: `pip install
-r requirements-pipeline.txt` → `classify.py` (needs GEMINI_API_KEY) → `analyze.py`. Offline checks:
`python test_pipeline.py`._
