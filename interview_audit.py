"""
interview_audit.py — per-claim audit of the top-ranked register claims against the n=6 interviews.

Evidence base: the 6 interview transcripts (interviews.md), coded 2026-08-20 before the engine ran.
Main-driver tally across the 6: Price 2 · H3 2 · H2 1 · Attention/forgetting 1 · H1 as PRIMARY: 0.
Per-hypothesis read: H1 kill-condition triggered (0/6 named fit/quality/return as the deciding
reason); H2 supported (occasion decay — Sneha's wedding, Aarav's trip); H3 supported in two flavours
(inspiration — Riya; comparison — Kunal); price is a top-2 driver but the BARRED lever; forgetting is
a distinct re-exposure thread.

Each of the top 30 register claims is coded by the blind rule:
  held up        — the interviews corroborate the claim
  partly invented— the corpus overstates beyond what the interviews support
  rejected       — the interviews contradict the claim
  not tested     — the interviews don't speak to it (NO fabricated support)

The verdicts are analyst coding (a primary-research input, like Cowork filling the register); the
COVERAGE and TALLY are computed in code from the register. Reproducible: python interview_audit.py.
"""
from __future__ import annotations

import json
import sys

N_INTERVIEWS = 6

# id, verdict, one-line note (grounded in the transcripts, interviews.md), claim_text prefix (drift guard).
CODING = [
    ("C001", "held up", "The user uses the app for", "H3 corroborated — Riya 'just scrolls Myntra like Instagram'; her wishlist is 'a collection of things she likes' (~10% converts). Window-shopping saves were never purchase intent."),
    ("C002", "partly invented", "Will refrain from buying", "Return grievance is real, but not one of the 6 named return-safety as the blocker — the corpus overstates it as a save→buy blocker."),
    ("C003", "partly invented", "Bad return refund and support", "Post-purchase support grievance; 0/6 cited return/quality doubt as the deciding reason a saved item went unbought."),
    ("C004", "not tested", "No questions asked return", "No respondent mentioned returns at all — as a help or a blocker — so the interviews don't test whether easy returns remove hesitation."),
    ("C005", "partly invented", "Dresses were returned due to", "A completed-purchase size return; fit doubt was never the deciding blocker — Priya even skipped the size chart, yet forgot rather than doubting fit."),
    ("C006", "partly invented", "Experienced a fitting issue", "A post-purchase fit return; 0/6 named fit as the deciding reason not to buy a saved item."),
    ("C007", "partly invented", "The size runs a bit small", "Mild fit note; the interviews place fit/quality as background sentiment, never the blocker."),
    ("C008", "partly invented", "User returned a trouser", "Post-purchase size return; not the deciding save→buy blocker in any interview."),
    ("C009", "partly invented", "Cloth quality is not so good", "Quality doubt is background — Priya 'had no time to check reviews or the size chart', yet the blocker was forgetting, not quality."),
    ("C010", "not tested", "Delayed delivery caused the gift", "A late-delivered gift (a COMPLETED purchase), not a wishlist occasion-decay. No respondent had a delivery-delay story — the interviews cover not-buying saved items. (Occasion-decay IS supported — Sneha's wedding, Aarav's trip — but via items left UNBOUGHT, not late delivery.)"),
    ("C011", "not tested", "Delayed delivery ruined plans", "Same — a delivery-SLA failure on a bought item, not the wishlist occasion-decay the interviews describe; no respondent reported one."),
    ("C012", "held up", "The user cross-checks prices", "Corroborated — Aarav 're-check price', Rahul 'wait for a big sale', Kunal saved 7–8 to 'compare later, choose one'. Price-checking / comparison is real."),
    ("C013", "held up", "It is always a joyful experience", "H3 corroborated — low-commitment saving matches Riya ('things she likes') and Priya ('saves interesting things to avoid deciding in the moment'); adding ≠ intent."),
    ("C014", "not tested", "Customer faced issues with no return", "Post-purchase service grievance; the interviews probed why saved items weren't bought, not post-purchase service — no evidence either way."),
    ("C015", "not tested", "User browsed, selected items", "Cart/checkout frustration; outside the save→buy intent the interviews covered."),
    ("C016", "not tested", "Not going to purchase anything", "Post-purchase service grievance; the interviews don't speak to it."),
    ("C017", "not tested", "Delayed exchange for an engagement", "Post-purchase exchange delay on a bought item; outside the save→buy scope the interviews covered."),
    ("C018", "not tested", "Wrong item delivered and support", "Wrong-item delivery + support dispute; post-purchase service, not probed in the interviews."),
    ("C019", "not tested", "Stopped purchasing on Myntra", "COD/delivery-partner grievance; the interviews don't cover it."),
    ("C020", "not tested", "User experienced receiving an old", "Wrong-item (old notebook) delivery grievance; post-purchase service, no interview evidence."),
    ("C021", "partly invented", "Lack of customer support for return", "Return/support grievance framed as a blocker; 0/6 named return-safety as the deciding save→buy reason."),
    ("C022", "partly invented", "The return policy is considered", "'Return policy poor' is a grievance; the interviews put return doubt as background, never the blocker."),
    ("C023", "partly invented", "Being charged a", "A return-FEE grievance — note the interviews' price driver was ITEM price (Aarav ₹2,800, Rahul ₹4,500), and even that wasn't H1. The corpus overstates a return fee as an uncertainty blocker."),
    ("C024", "partly invented", "Slow and uncollected returns", "Explicit 'return-safety doubt' claim; no respondent treated return-safety as the deciding blocker."),
    ("C025", "not tested", "Pincode delivery restrictions", "Delivery-availability (pincode); Rahul's item was once blocked by SIZE unavailability, but pincode delivery specifically wasn't probed."),
    ("C026", "partly invented", "Wrong shade received and exchange", "Wrong-shade + exchange grievance framed as affecting purchase; return doubt was background, not the blocker."),
    ("C027", "partly invented", "Return fees for disliked items", "Return-fee-affects-decision; the interviews' price sensitivity was item price (Aarav/Rahul), not return fees, and not H1."),
    ("C028", "not tested", "Missing tag on shoe box", "A specific return-refusal (missing tag) service failure; not covered by the interviews."),
    ("C029", "partly invented", "Uncertainty about whether a product", "Explicit return-uncertainty; 0/6 named return doubt as the deciding reason a saved item went unbought."),
    ("C030", "partly invented", "Will definitely stop placing", "Return-denial grievance affecting future orders; return-safety not corroborated as the blocker."),
]


def apply(register: list[dict]) -> dict:
    """Write audit_verdict/audit_note onto the coded claims; return computed coverage + tally."""
    by_id = {e.get("claim_id"): e for e in register}
    for cid, verdict, prefix, note in CODING:
        e = by_id.get(cid)
        if not e:
            print(f"  WARN: {cid} not in register — skipped", file=sys.stderr)
            continue
        if not e.get("claim_text", "").startswith(prefix[:18]):
            print(f"  WARN: {cid} text drifted ('{e.get('claim_text','')[:24]}') — skipped to avoid mis-verdict",
                  file=sys.stderr)
            continue
        e["audit_verdict"] = verdict
        e["audit_note"] = note
    return coverage(register)


def coverage(register: list[dict]) -> dict:
    verdicted = [e for e in register if e.get("audit_verdict")]
    tally: dict[str, int] = {}
    for e in verdicted:
        tally[e["audit_verdict"]] = tally.get(e["audit_verdict"], 0) + 1
    substantive = sum(n for k, n in tally.items() if k != "not tested")
    total = len(register)
    return {
        "n_audited": len(verdicted), "n_total": total,
        "coverage_pct": round(len(verdicted) / total * 100, 1) if total else 0.0,
        "n_substantive": substantive, "n_not_tested": tally.get("not tested", 0),
        "distribution": tally, "n_interviews": N_INTERVIEWS,
    }


# ── standalone reproducible run ──────────────────────────────────────────────
def main() -> None:
    if "--selftest" in sys.argv:
        _selftest()
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    register = json.load(open("claims_register.json", encoding="utf-8"))
    data = json.load(open("data.json", encoding="utf-8"))
    manifest = json.load(open("corpus_manifest.json", encoding="utf-8"))

    cov = apply(register)

    json.dump(register, open("claims_register.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    manifest["audit_coverage"] = cov
    json.dump(manifest, open("corpus_manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    data["register"] = register
    data["audit"] = cov
    json.dump(data, open("data.json", "w", encoding="utf-8"), ensure_ascii=False)

    print(f"Audit coverage: {cov['n_audited']} of {cov['n_total']} claims verdicted ({cov['coverage_pct']}%) "
          f"against {cov['n_interviews']} interviews")
    for k in ("held up", "partly invented", "rejected", "not tested"):
        if cov["distribution"].get(k):
            print(f"  {k:16s}: {cov['distribution'][k]}")
    print(f"  (substantive verdicts: {cov['n_substantive']}; not tested: {cov['n_not_tested']})")
    print("\nWrote audit_verdict/audit_note -> claims_register.json; audit_coverage -> corpus_manifest.json; audit -> data.json")
    print("Next: python build_static.py  (then redeploy)")


def _selftest() -> None:
    reg = [{"claim_id": cid, "claim_text": prefix, "audit_verdict": "", "audit_note": ""}
           for cid, _, prefix, _ in CODING]
    reg.append({"claim_id": "C099", "claim_text": "untouched", "audit_verdict": "", "audit_note": ""})
    cov = apply(reg)
    assert cov["n_audited"] == 30 and cov["n_total"] == 31
    assert cov["distribution"]["held up"] == 3
    assert cov["distribution"]["partly invented"] == 15
    assert cov["distribution"]["not tested"] == 12
    assert "rejected" not in cov["distribution"]           # none forced
    assert cov["n_substantive"] == 18 and cov["n_not_tested"] == 12
    assert all(e["audit_note"] for e in reg if e["audit_verdict"])  # every verdict carries a note
    assert reg[-1]["audit_verdict"] == ""                  # C099 untouched
    print("selftest OK")


if __name__ == "__main__":
    main()
