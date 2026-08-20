# Pre-Registered Hypotheses — Myntra Wishlist → Purchase

**Status: 🔒 FROZEN / COMMITTED — 2026-08-20 07:20 IST (Asia/Calcutta).**
Drafted 2026-08-20 06:52 IST. Amended 2026-08-20 07:20 IST (added H2-vs-H3 discrimination
protocol). Locked at three hypotheses. Price/value kept on watchlist (see note), not split out.

This file was committed **before the discovery engine ran and before any interview was coded.**
Any change from here is a logged amendment with its own timestamp — never a silent edit.

## Provenance (stated honestly for the audit trail)
Mayank reviewed all three hypotheses and drove the sharpest revision himself — flagging H2/H3
separability, which became the discrimination protocol below. The pre-data prior recorded next was
proposed by Claude with reasoning and adopted by Mayank on delegation, not independently generated.
Recorded truthfully rather than dressed up as an independent prior. Mayank may overwrite the prior
any time before data lands.

## Pre-data prior (recorded 2026-08-20 07:20 IST, before any engine or interview data)
- **Largest raw share of non-conversion → H3** — much of the 88–90% was likely never purchase intent.
- **Largest actionable leak → H1** — among real-intent saves, fit/size/quality uncertainty dominates
  and is the lever Myntra can actually move.
- **Smallest → H2** — intent decay is real but likely the most over-told story; "the occasion passed"
  often masks H1 or H3.
- Provenance: Claude-proposed, Mayank-adopted on delegation. Overwritable pre-data.
- This prior earns no protection — it is subject to every kill-condition below like any other claim.

## Metric under study
**W2P-30** = share of wishlist-adds that convert to purchase of that item (or close substitute)
within 30 days. Working baseline estimate ~10–12%.

## Falsifiability rule
Each hypothesis states, up front, the evidence pattern that would KILL it. If the interviews +
engine corpus produce the kill-pattern, we reject it on a slide. We are **not** looking to confirm
all three — we expect at least one to die.

---

## H1 — Purchase-time uncertainty stalls still-wanted items
**Statement:** A meaningful share of wishlisted items are still wanted and still relevant at day 30,
but do not convert because the shopper cannot resolve fit / size / quality / return-safety
uncertainty at the moment of commitment.
**Funnel stage attacked:** Stage 3 (commit intent).
**Mechanism:** No low-risk way to "try before trust" → the decision is deferred indefinitely.
**Would CONFIRM:** Respondents describe a specific item they still want but haven't bought, and the
blocker they name is fit/size/"will it look like the photo"/return hassle — not price, not "changed my mind."
**Would KILL it (reject if):** When shown their own un-bought wishlist items, respondents rarely cite
fit/quality/return doubt; the dominant reasons are "no longer needed," "found it elsewhere," or "was
never really going to buy it." I.e. uncertainty is a minor stage-3 leak, not the main one.
**Prior (Claude's, non-binding):** Medium-high. ~50% of Myntra revenue already runs through the
size/fit algorithm — circumstantial evidence fit-uncertainty is load-bearing, but that same fact
could mean fit is already solved at purchase and irrelevant at wishlist. Genuinely open.

## H2 — Relevance decays inside the 30-day window
**Statement:** Intent was real at save-time, but the item becomes irrelevant before re-consideration
because the triggering context expires — the occasion passes, the season turns, the need is met
elsewhere, or the look dates.
**Funnel stage attacked:** Stages 1–2 (re-exposure, re-consideration).
**Mechanism:** Wishlist captures a moment of intent but is not re-surfaced while the intent is still
live; by the time (if) the user returns, the reason to buy is gone.
**Would CONFIRM:** Respondents describe saving for a specific occasion/season/need, and the item dying
because "that event was over" / "it's not the season anymore" / "I'd already sorted it."
**Would KILL it (reject if):** Un-bought items are mostly evergreen (basics, staples with no
time-bound trigger) and respondents still didn't buy them — meaning decay isn't the story; something
timeless is still blocking them (points back to H1 or H3).
**Prior:** Medium. Fashion is seasonal and occasion-driven, so plausible — but risks being a just-so
story if respondents can't point to a concrete expired trigger.

## H3 — Wishlist add ≠ purchase intent
**Statement:** A large share of wishlist-adds are not deferred purchases at all — they are
organizational, aspirational, comparison, or "bookmark to look at" acts. Low W2P-30 is partly correct
behavior of a mixed-intent tool, not a conversion failure.
**Funnel stage attacked:** Stage 0 (the denominator itself).
**Mechanism:** The wishlist is overloaded — one button serves "buy later," "compare these," "aspire to
this," "save the brand," "remember this style." Treating all adds as intended purchases inflates the denominator.
**Would CONFIRM:** When walked through their wishlist, respondents themselves classify many items as
"never planned to buy that" / "just saving for inspo" / "comparing options, picked one."
**Would KILL it (reject if):** Respondents report they did intend to buy most of what they saved and
are frustrated they didn't — i.e. the intent was real and the failure is downstream (H1/H2), not a
denominator artifact.
**Prior:** Medium-high, and the most consequential if true — because it would mean the right fix is
segmenting intent at save-time, not nudging harder. Also the most dangerous to assume, because it can
excuse away a real conversion problem. Needs the sharpest evidence.

## Interaction / competition note
These are built to **compete, not stack.** They attack different funnel stages and imply different
solutions (H1 → safe-commit mechanism; H2 → intent-timed re-surfacing; H3 → intent segmentation at
save-time). If two are true, the deck must say which stage leaks most, not claim all three. If the
evidence is mushy, we say so — we do not smooth it into one confident narrative (attempt-2 failure mode).

## Pre-registered discrimination protocol: H2 vs H3 (added per Mayank, 2026-08-20)
H2 and H3 produce near-identical interview language ("I didn't buy it") and must be actively told
apart, or their kill-conditions don't fire. The whole boundary is one question — **was there genuine
purchase intent at the moment of saving?** Intent existed at save then died → H2; intent never existed
at save → H3.

**The trap we pre-commit to avoid:** asking a user "did you intend to buy it?" *after* they didn't buy
is contaminated by post-hoc rationalization. Pure self-reported intent systematically over-credits H3
and under-credits H2. We name this now so we never quietly lean on that contaminated question.

Discriminate by triangulating three signals, never one:
1. **Episodic reconstruction, not intent-labeling.** Replay the save moment concretely — "what were
   you doing when you saved this, why that item, what did you picture doing next?"
2. **Item taxonomy (objective-ish).** Tag each un-bought item as occasion/season-tied vs evergreen.
   Occasion-tied + occasion-passed supports H2; evergreen + "just saving for inspo" supports H3.
3. **Save-time behavioral signal from the engine.** High-consideration behavior at save (checked size
   chart / read reviews / compared) = real intent (weakens H3); reflexive one-tap save = weak intent (supports H3).

**Decision rule (pre-registered):** classify each un-bought item by the **majority of the three
signals**, not self-report alone. Where the three disagree, log "ambiguous" and report it as such. A
large ambiguous bucket is itself a finding.

## Engagement & decision log
- 2026-08-20 — Mayank: reviewed all three; endorsed competing-causal framing and discrimination-not-
  validation goal. Primary scrutiny = H2 vs H3 separability. No hypothesis rejected.
- 2026-08-20 07:20 IST — **FROZEN.** Pre-data prior recorded; H4 not split (price/value stays on
  watchlist inside H1's commit stage — add later as a timestamped amendment if it surfaces strongly);
  freeze authorised by Mayank. Segment left open until early engine output.

## Amendment log (append-only)
- (none yet — first post-freeze change gets a dated entry here)
