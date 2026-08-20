# Pre-registered hypotheses — Myntra Wishlist→Purchase Discovery Engine

**Committed before any dual-hypothesis classification was run against user data.**
The authoritative timestamp is this file's first git commit. Nothing in the classification
or analysis pipeline is permitted to run against the corpus until this file is committed.

**Why this exists:** the previous engine clustered themes, ranked them into a single
"opportunity score", picked a winner, and primed every downstream source to confirm it. This
version pre-commits *what would count as evidence for and against each hypothesis, and what
result would reject it*, so a hypothesis can actually die. Reporting is per-hypothesis and
per-segment — there is no single ranked winner.

---

## The three competing hypotheses

Each explains why a user **saves** (wishlists) a fashion item on Myntra but does **not buy** it.
They are competing, not nested: a document is coded independently on each, and may support
several, one, or **none**. "None" is a real outcome and its share is reported.

### H1 — Uncertainty blocks conversion
The user *wants* the item but cannot resolve a doubt, so the decision stalls.
Doubt is about: **fit, size, quality/material, authenticity, styling/occasion match, or need
for social validation.**
- **Counts as evidence (present=true):** the text voices an *unresolved* doubt tied to a
  saved/considered item ("not sure of the size", "will it look good on me", "is this original").
- **Does NOT count:** post-purchase complaints (returns, damaged on arrival), pure app bugs,
  price-only objections.
- **Would disconfirm H1:** doubts cluster at the *post-purchase* stage (they're returns/quality
  problems, not decision-stage blocks), OR the dominant segment is one with no purchase intent
  (then H3, not H1, explains the non-purchase).

### H2 — Relevance decays
Nothing is "unresolved" — the window simply closed. The user moved on.
Causes: **occasion passed, trend moved, forgot the item, or already bought it elsewhere.**
- **Counts as evidence (present=true):** the text signals lapsed relevance ("forgot it was
  there", "already got one", "don't need it now", "was for Diwali").
- **Does NOT count:** an active, still-wanted item held up by a doubt (that's H1).
- **Would disconfirm H2:** decay language is rare across all segments, OR items are still
  actively wanted (contradicts "window closed").

### H3 — Wishlist ≠ purchase intent
The save was never a buy signal. The wishlist is used as something else.
Sub-types: **mood-board / inspiration, price-watch, catalogue-as-Pinterest browsing,
size-unavailable holding.**
- **Counts as evidence (present=true):** the text shows the save is not intended as a purchase
  ("just saving for inspo", "waiting for a sale", "adding to see later", "saved till my size is back").
- **Does NOT count:** a genuine intent to buy that is merely deferred by a doubt (H1) or by
  decay (H2).
- **Would disconfirm H3:** the corpus shows saved items are overwhelmingly intended purchases
  deferred by resolvable blocks (then the lever is H1/H2, not "re-teach what a wishlist is").

---

## Closed taxonomy — `intent_segment` (the segmentation dimension)

Segmentation of *how the user is using the save* is coded **before** any conclusion on blockers,
and every hypothesis result is reported **per segment, never averaged across segments**. Closed
set — the model may not invent a segment:

| segment | meaning |
|---|---|
| `deferred_purchase` | genuine intent to buy, deferred (the H1/H2 battleground) |
| `mood_board` | inspiration / aesthetic collection, no buy intent |
| `price_watch` | saved to buy *if* it gets cheaper |
| `catalogue_browse` | using the wishlist as a browsing / "see later" catalogue |
| `size_unavailable_hold` | wants it, holding because the size is out of stock |
| `unclear` | intent not determinable from the text |

## Closed taxonomy — `topic` (what the doubt/subject is about)

One label per document, closed set (reused from the validated barrier taxonomy):

`fit_uncertainty, size_uncertainty, quality_uncertainty, authenticity_trust,
style_occasion_match, choice_overload, info_insufficient, conflicting_reviews,
social_validation_need, needs_external_comparison, price_value, delivery_returns,
stockout, forgetting, none, other`

---

## Coding rules (binding on the classifier)

1. **Independent coding.** H1, H2, H3 are judged separately. Multiple / one / none are all valid.
2. **Verbatim span required.** Each `present=true` must carry a `span` copied verbatim from the
   source text. Any span later found not to be a substring of its source is blanked and the claim
   is dropped from reporting.
3. **Closed sets only.** Out-of-taxonomy values are coerced to the default; no free-form themes.
4. **Cross-source rule.** A theme/claim is reported as real only with **≥2 independent sources**.
   Single-source themes go to the discard pile.
5. **"None" is tracked.** Documents supporting no hypothesis are counted and reported, not hidden.

## Pre-registered decision rules (how a hypothesis is rejected — set before the run)

- A hypothesis is **SUPPORTED overall** only if its evidence share ≥ **15%** of relevant
  documents **and** it clears the ≥2-source rule.
- A hypothesis is **REJECTED** if its overall evidence share < **8%** **and** it does not lead
  in any single intent-segment. (It could not muster even a within-segment plurality.)
- Between 8% and 15%, or leads only within one narrow segment → **PARTIAL / segment-specific**;
  reported as such, not promoted to a headline.
- The **headline finding is the segment split** (which hypothesis leads in which segment), not a
  single winner. If H1/H2/H3 shares are within 5 points of each other overall with no segment
  separation, the honest finding is "no dominant mechanism" — that is a valid, reportable result.

_Thresholds are complaint-share of a skewed corpus, not user prevalence. Every wishlist→purchase
link here is a hypothesis for primary research to confirm or kill (see the audit table)._
