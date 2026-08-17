# Findings — Myntra Wishlist->Purchase Discovery Engine
_Hypothesis generator from public user text. NOT proof. Reach = complaint-share, not true prevalence. MetricRelevance = hypothesised link._
## KILL-SWITCH: price vs non-price blocker
- **7.7%** of relevant texts point to a **price** blocker (`intent=price_waiter` OR `price_value` barrier) — 270/3512 rows.
- **92.3%** point to **non-price** barriers (fit, size, quality, trust, choice overload, stockout, forgetting, ...).
- **Read:** Non-price strategy has HEADROOM — most blockers are addressable without discounts.

## Corpus
- 4256 texts collected; **3512 relevant**; 2588 Myntra-specific.
- Sources: {'google_play': 4256}
- Intent mix: {'latent_intent': 1637, 'unclear': 1182, 'comparison_shortlist': 392, 'inspiration': 201, 'price_waiter': 100}
- Journey stage: {'post_purchase': 2179, 'discovery': 507, 'evaluation': 358, 'consideration': 161, 'purchase': 145, 'decision': 99, 'unclear': 41, 'shortlisting': 22}
- Emotional state: {'confident': 1384, 'frustrated': 1263, 'excited': 654, 'skeptical': 120, 'curious': 48, 'indecisive': 20, 'anxious': 14, 'unclear': 7, 'overwhelmed': 2}

## Ranked opportunities (gated, non-monetary)
| # | Barrier | Funnel | Score | Reach | Severity | MetricRel | Evid | n | Pre-buy% |
|---|---|---|---|---|---|---|---|---|---|
| 1 | stockout | re-exposure | 12.5 | Med | High | High | 1.0 | 94 | 20% |
| 2 | size_uncertainty | confidence | 12.5 | Med | High | High | 1.0 | 86 | 19% |
| 3 | fit_uncertainty | confidence | 11.5 | Low | High | High | 1.0 | 10 | 20% |
| 4 | delivery_returns | confidence | 11.482 | High | High | Med | 0.998 | 1128 | 8% |
| 5 | choice_overload | re-engagement | 11.186 | Low | High | High | 0.973 | 11 | 100% |
| 6 | authenticity_trust | confidence | 10.5 | Med | High | Med | 1.0 | 170 | 26% |
| 7 | quality_uncertainty | confidence | 10.458 | Med | High | Med | 0.996 | 301 | 14% |
| 8 | info_insufficient | confidence | 9.5 | Low | High | Med | 1.0 | 15 | 80% |
| 9 | style_occasion_match | confidence | 9.5 | Low | High | Med | 1.0 | 10 | 10% |
| 10 | conflicting_reviews | confidence | 9.5 | Low | High | Med | 1.0 | 9 | 67% |
| 11 | forgetting | re-engagement | 8.5 | Low | Low | High | 1.0 | 4 | 75% |
| 12 | needs_external_comparison | confidence | 7.5 | Low | High | Low | 1.0 | 3 | 100% |

_Pre-buy% = share of the barrier's texts voiced at a PRE-purchase stage. Low % ⇒ mostly post-purchase ⇒ weaker link to the save→buy step (reported, not scored)._

## Insight cards (top opportunities)

### 1. stockout  
- **Observed behavior:** users voice this 94 times (2.7% of relevant complaints; 20% at a pre-purchase stage).
- **Underlying barrier:** stockout (re-exposure funnel level).
- **Root-cause hypothesis:** Saved items go out of stock (esp. the user's size) before they decide to buy.
- **Current workaround:** They wait and it never comes back; the save dies.
- **Potential opportunity:** Back-in-stock + low-stock alerts for wishlisted sizes; reserve-my-size.
- **Sub-themes:** order, delivery, customer (n=35); cancelled, myntra, time (n=34); product, order, price (n=25)
- **Evidence:** "After getting the product after 23 days the color was wrong of the dress. To chk the exchange, the price is 3 times high"  (+93 more)
- **Confidence:** score 12.5 | evidence discount 1.0 | bands R/S/M = Med/High/High.
- **Disconfirming evidence:** If in-stock saves convert at the same low rate, stockout isn't the driver.
- **What would validate/refute:** Ship size-level back-in-stock alerts; measure wishlist->purchase for alerted users.

### 2. size_uncertainty  
- **Observed behavior:** users voice this 86 times (2.5% of relevant complaints; 19% at a pre-purchase stage).
- **Underlying barrier:** size_uncertainty (confidence funnel level).
- **Root-cause hypothesis:** Inconsistent sizing across brands makes users unsure which size to order from a saved item.
- **Current workaround:** They order two sizes intending to return one, or abandon the save.
- **Potential opportunity:** Size recommender on wishlist items using the user's past kept-vs-returned sizes per brand.
- **Sub-themes:** product, size, exchange (n=41); support, ordered, size (n=28); like, delivery, app (n=17)
- **Evidence:** "They sent me the wrong pant and when I tried to return they said they sent me the right product... now I have a pant tha"  (+85 more)
- **Confidence:** score 12.5 | evidence discount 1.0 | bands R/S/M = Med/High/High.
- **Disconfirming evidence:** If users buy anyway and return, this is a returns-cost problem, not a save->buy block.
- **What would validate/refute:** Show a personalised size hint on wishlist; track add-to-cart and purchase from wishlist.

### 3. fit_uncertainty  
- **Observed behavior:** users voice this 10 times (0.3% of relevant complaints; 20% at a pre-purchase stage).
- **Underlying barrier:** fit_uncertainty (confidence funnel level).
- **Root-cause hypothesis:** Users can't predict how a garment will fit their body, so a saved item stalls at decision.
- **Current workaround:** They ask in comments, check other reviews, or just don't buy.
- **Potential opportunity:** Fit-confidence layer on the wishlist: per-item fit signals, 'fits like' from similar bodies, model-measurement match.
- **Sub-themes:** product, shopping, time (n=6); good, size, fitting (n=4)
- **Evidence:** "I ordered T-shirt in Regular Fit four times, but every time Myntra delivered a Slim Fit version instead."  (+9 more)
- **Confidence:** score 11.5 | evidence discount 1.0 | bands R/S/M = Low/High/High.
- **Disconfirming evidence:** If fit complaints cluster in POST-purchase (returns) not pre-purchase, the block is quality/returns, not decision-stage fit.
- **What would validate/refute:** A/B a wishlist fit-signal badge; measure 30-day wishlist->purchase lift for exposed users.

### 4. delivery_returns  
- **Observed behavior:** users voice this 1128 times (32.1% of relevant complaints; 8% at a pre-purchase stage).
- **Underlying barrier:** delivery_returns (confidence funnel level).
- **Root-cause hypothesis:** Uncertainty about return ease/cost for a saved item lowers commitment.
- **Current workaround:** They avoid buying items they're unsure they can return cleanly.
- **Potential opportunity:** Clear, item-level return terms + 'easy return' assurance on wishlist cards.
- **Sub-themes:** delivery, order, app (n=521); return, product, exchange (n=332); customer, support, service (n=275)
- **Evidence:** "Most if the items delivered are used or defective and when you place it for refund or replacement, it will take eternity"  (+1127 more)
- **Confidence:** score 11.482 | evidence discount 0.998 | bands R/S/M = High/High/Med.
- **Disconfirming evidence:** If returns worry is post-purchase only, it doesn't block the save->buy step.
- **What would validate/refute:** Surface return terms on saved items; measure conversion.

### 5. choice_overload  
- **Observed behavior:** users voice this 11 times (0.3% of relevant complaints; 100% at a pre-purchase stage).
- **Underlying barrier:** choice_overload (re-engagement funnel level).
- **Root-cause hypothesis:** Wishlists become graveyards: too many saved items, no way to decide, so nothing gets bought.
- **Current workaround:** Users let the list grow and forget it.
- **Potential opportunity:** Wishlist decision aids: sort/compare saved items, 'pick for me', decayed re-surfacing of top saves.
- **Sub-themes:** need, filters, brands (n=7); shopping, great, app (n=4)
- **Evidence:** "The heavy reliance on AI-generated models and heavily filtered product images... makes it impossible to judge the actual"  (+10 more)
- **Confidence:** score 11.186 | evidence discount 0.973 | bands R/S/M = Low/High/High.
- **Disconfirming evidence:** If small wishlists also don't convert, overload isn't the binding constraint.
- **What would validate/refute:** Ship a wishlist compare/'top 3' nudge; measure 30-day wishlist->purchase.

### 6. authenticity_trust  
- **Observed behavior:** users voice this 170 times (4.8% of relevant complaints; 26% at a pre-purchase stage).
- **Underlying barrier:** authenticity_trust (confidence funnel level).
- **Root-cause hypothesis:** Users doubt product authenticity/originality, blocking commitment to saved branded items.
- **Current workaround:** They cross-check price/seller elsewhere or avoid buying.
- **Potential opportunity:** Authenticity assurance (brand-authorised seller badge, guarantee) on wishlist branded items.
- **Sub-themes:** app, myntra, products (n=82); myntra, product, return (n=71); good, brands, good genuine (n=17)
- **Evidence:** "there r lot of duplicate products in myntra that are overpriced which I realised only now after I recieved duplicate pro"  (+169 more)
- **Confidence:** score 10.5 | evidence discount 1.0 | bands R/S/M = Med/High/Med.
- **Disconfirming evidence:** If distrust is app-wide sentiment not tied to saved items, a badge won't lift conversion.
- **What would validate/refute:** Expose authenticity badge on saved branded items; measure conversion delta.

## Gated-out (logged for honesty)
- `none` (n=1920) — not a discrete opportunity
- `price_value` (n=259) — monetary (excluded by no-incentive constraint)
- `other` (n=31) — not a discrete opportunity

## New patterns (barriers not in the taxonomy)
- User frustration with AI customer support agents
- account deactivation threat on product returns
- AI-generated product images causing trust issues and misrepresentation
- Lack of human customer support channel
- poor search discovery mechanism
- unclear or changing loyalty cash/wallet rules
- automatic order cancellation by platform
- general app dissatisfaction
- extreme general dissatisfaction
- poor post-purchase customer service and return handling
- delayed refunds and problematic return pickups
- unresponsive customer care regarding returns
- Fake discount sale order cancellation by platform
- Poor search engine results
- poor customer support response
- hidden refund deductions / charges
- pincode serviceability restriction
- platform charging return fees for wrong product delivered
- User received damaged products
- poor customer service and unauthorized order cancellation

## Bias & limitations
- **Complaint-skewed:** app reviews/comments over-represent the frustrated. Reach is complaint-share, NOT the true share of users who hit each barrier.
- **Language-skewed:** collected with `lang=en`; Hinglish/Hindi still surfaced and was classified, but pure regional-language reviews are under-sampled.
- **Proxy funnel:** app-review text is NOT the wishlist funnel. Every wishlist->purchase link here is a HYPOTHESIS to be validated with product analytics/experiments.
- **No true frequencies:** we cannot say how often each barrier occurs per user, only how often it is *voiced*.
- **Auditability:** 3508/3512 relevant rows carry a verbatim `evidence_span`, so any label can be hand-checked against its source quote.
