# Architecture Notes

## Data provenance classes

Every figure in the system belongs to exactly one class — the model and
engine never silently convert between them:

| Class | Where it lives | Rule |
|---|---|---|
| User-entered facts | `BusinessProfile`, `FinancialPeriod` | Always editable by the user |
| Proposed adjustments | `Adjustment(status="proposed")` | Included in provisional SDE only |
| Supported adjustments | `Adjustment(status="supported")` | Included in supported SDE |
| Needs-review | `Adjustment(status="needs_review")` | Provisional only, flagged |
| Rejected | `Adjustment(status="rejected")` | Kept in register, excluded from math |
| Market-derived assumptions | `MultipleAssumption(kind="supported")` | Requires recorded source + date |
| Illustrative assumptions | `MultipleAssumption(kind="illustrative")` | Never presented as benchmarks |
| Hypothetical scenarios | `Scenario` | Overrides applied at read time; **never** written back to inputs |
| Calculated outputs | engine results | Recomputed each render — never stored on the model |

Because outputs are always recomputed, editing an upstream input (e.g.
reported profit) automatically invalidates every downstream result —
tested in `test_integration.py`.

## Earnings normalization rules

Add-back eligibility is a function of declared profit basis
(`engine/normalization.py::_BASIS_DEDUCTED`):

- **net income** — interest, tax, D&A were deducted → eligible.
- **operating income (EBIT)** — only D&A + operating items were deducted;
  interest/tax add-backs are blocked (double-count).
- **EBITDA** — only operating items were deducted; all I/T/D&A add-backs
  blocked.
- **unknown** — basis unestablished; all add-backs blocked and flagged.

Owner draws/distributions are never expenses and can never be add-backs.
SDE adds back **one** working owner's compensation; multiple owner-comp
lines are flagged.

## Valuation safeguards

- Methods produce independent indications — never averaged.
- EBITDA multiple only ever multiplies an EBITDA basis.
- Enterprise→equity bridge is explicit (cash/debt assumptions stated).
- A midpoint is a reference point inside a range — never framed as a
  guaranteed price.

## Marketability simulation

`engine/marketability.py` exposes only descriptive bands and an
unlabeled-index curve, always labeled *Illustrative Relative
Marketability — Educational Simulation*. The 6/12/24-month timeframe
control changes guidance text only — spec §11 forbids numerical
probabilities without empirical data, and the module has no code path
that emits one.
