"""
Earnings normalization engine: reported profit -> Seller's Discretionary
Earnings (SDE).

Core accounting rule: an expense may only be *added back* if it was actually
deducted to arrive at the starting figure. Which expenses were deducted
depends on the declared profit basis:

- net_income        -> interest, income tax, depreciation, amortization were
                       all deducted -> all are eligible add-backs.
- operating_income  -> depreciation & amortization deducted; interest and
  (EBIT)               income tax were NOT -> adding them back would double-count.
- ebitda            -> none of interest, tax, D&A were deducted -> none are
                       eligible add-backs (adding them would double-count).
- unknown           -> the basis cannot be established; normalization is
                       provisional only and every add-back is flagged.

Owner compensation is a normal payroll expense deducted under every basis,
so it is always eligible — but only ONE working owner's compensation is a
standard SDE add-back. Owner draws/distributions are never expenses and can
never be add-backs.

Normalization deductions (negative adjustments, e.g. the market cost of
replacing unpaid family labor) are always applied; they represent costs a
buyer would actually incur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models.assessment import (
    ADJUSTMENT_CATEGORY_LABELS,
    Adjustment,
    FinancialPeriod,
)

# Which expense bucket each category consumed when the reported figure was
# computed. "operating" expenses (owner comp, discretionary, nonrecurring)
# are deducted under every profit basis.
_BASIS_DEDUCTED = {
    "net_income": {"interest", "income_tax", "depreciation", "amortization", "operating"},
    "operating_income": {"depreciation", "amortization", "operating"},
    "ebitda": {"operating"},
    "unknown": set(),
}

_CATEGORY_BUCKET = {
    "interest": "interest",
    "income_tax": "income_tax",
    "depreciation": "depreciation",
    "amortization": "amortization",
    "owner_compensation": "operating",
    "discretionary": "operating",
    "nonrecurring": "nonrecurring_or_operating",
    "other_addback": "operating",
}

_ACTIVE_STATUSES = ("supported", "proposed", "needs_review")


@dataclass
class ReconciliationLine:
    label: str
    amount: float
    kind: str  # "start" | "add" | "deduct" | "subtotal"
    status: str = ""
    note: str = ""


@dataclass
class AdjustmentVerdict:
    adjustment_id: str
    eligible: bool
    reason: str = ""


@dataclass
class NormalizationResult:
    basis: str
    period_label: str
    reported_profit: Optional[float]
    supported_sde: Optional[float] = None
    provisional_sde: Optional[float] = None
    lines: list = field(default_factory=list)  # list[ReconciliationLine]
    verdicts: list = field(default_factory=list)  # list[AdjustmentVerdict]
    flags: list = field(default_factory=list)  # list[str]
    basis_established: bool = True

    @property
    def best_sde(self) -> Optional[float]:
        """Supported SDE if any supported adjustments exist or the figure is
        clean; otherwise the provisional figure (explicitly labeled as such
        by callers)."""
        if self.supported_sde is not None:
            return self.supported_sde
        return self.provisional_sde


def validate_adjustment(adj: Adjustment, basis: str) -> AdjustmentVerdict:
    """Decide whether an add-back is legitimate for the declared basis."""
    if adj.status == "rejected":
        return AdjustmentVerdict(adj.id, False, "Rejected / excluded by reviewer.")

    if adj.category == "normalization_deduction":
        if adj.amount >= 0:
            return AdjustmentVerdict(
                adj.id, False,
                "Normalization deductions must be entered as negative amounts.",
            )
        return AdjustmentVerdict(adj.id, True)

    if adj.amount < 0:
        # A negative add-back is just a deduction — always allowed.
        return AdjustmentVerdict(adj.id, True)

    if basis == "unknown":
        return AdjustmentVerdict(
            adj.id, False,
            "Profit basis is not established — add-backs cannot be verified. "
            "Identify whether the reported figure is net income, operating "
            "income, or EBITDA first.",
        )

    bucket = _CATEGORY_BUCKET.get(adj.category, "operating")
    if bucket == "nonrecurring_or_operating":
        bucket = "operating"

    if bucket not in _BASIS_DEDUCTED[basis]:
        pretty = ADJUSTMENT_CATEGORY_LABELS.get(adj.category, adj.category)
        return AdjustmentVerdict(
            adj.id, False,
            f"{pretty} was not deducted to arrive at "
            f"{basis.replace('_', ' ')} — adding it back would double-count.",
        )
    return AdjustmentVerdict(adj.id, True)


def reconcile(
    period: FinancialPeriod, adjustments: list
) -> NormalizationResult:
    """Build an itemized reported-profit -> SDE reconciliation.

    ``adjustments`` may span multiple periods; only those matching
    ``period.label`` (or with no period set) are applied.
    """
    basis = period.profit_basis or "unknown"
    res = NormalizationResult(
        basis=basis,
        period_label=period.label,
        reported_profit=period.reported_profit,
        basis_established=(basis != "unknown"),
    )

    if period.reported_profit is None:
        res.flags.append(
            "No reported profit for this period — enter a profit figure to "
            "compute adjusted earnings."
        )
        return res

    res.lines.append(
        ReconciliationLine(
            label=f"Reported profit ({basis.replace('_', ' ')})",
            amount=period.reported_profit,
            kind="start",
        )
    )
    if basis == "unknown":
        res.flags.append(
            "Profit basis is unknown. Normalization is provisional until the "
            "basis is identified."
        )

    applicable = [
        a for a in adjustments
        if not a.period_label or a.period_label == period.label
    ]

    owner_comp_lines = [
        a for a in applicable
        if a.category == "owner_compensation"
        and a.status in _ACTIVE_STATUSES
        and a.amount > 0
    ]
    if len(owner_comp_lines) > 1:
        res.flags.append(
            "More than one owner-compensation add-back found. SDE normally "
            "adds back ONE working owner's compensation only — review these "
            "entries."
        )

    supported_total = period.reported_profit
    provisional_total = period.reported_profit
    n_supported = n_proposed = 0

    for adj in applicable:
        if adj.status == "rejected":
            res.verdicts.append(
                AdjustmentVerdict(adj.id, False, "Rejected / excluded by reviewer.")
            )
            continue

        verdict = validate_adjustment(adj, basis)
        res.verdicts.append(verdict)
        if not verdict.eligible:
            res.lines.append(
                ReconciliationLine(
                    label=f"{adj.description or ADJUSTMENT_CATEGORY_LABELS.get(adj.category)} (excluded)",
                    amount=0.0,
                    kind="add",
                    status="excluded",
                    note=verdict.reason,
                )
            )
            res.flags.append(verdict.reason)
            continue

        kind = "add" if adj.amount >= 0 else "deduct"
        res.lines.append(
            ReconciliationLine(
                label=adj.description
                or ADJUSTMENT_CATEGORY_LABELS.get(adj.category, adj.category),
                amount=adj.amount,
                kind=kind,
                status=adj.status,
                note=adj.explanation,
            )
        )
        provisional_total += adj.amount
        n_proposed += 1
        if adj.status == "supported":
            supported_total += adj.amount
            n_supported += 1

    res.provisional_sde = provisional_total
    res.supported_sde = supported_total if n_supported or n_proposed == 0 else None
    if res.supported_sde is None:
        res.flags.append(
            "No supported adjustments yet — the SDE shown is provisional "
            "pending review of the adjustment register."
        )

    res.lines.append(
        ReconciliationLine(
            label="Seller's Discretionary Earnings (SDE)"
            if res.supported_sde is not None
            else "Provisional SDE",
            amount=res.supported_sde
            if res.supported_sde is not None
            else res.provisional_sde,
            kind="subtotal",
        )
    )

    if res.best_sde is not None and res.best_sde < 0:
        res.flags.append(
            "Normalized earnings are negative. An earnings-multiple "
            "valuation will not be meaningful — consider the adjusted net "
            "asset method and the improvement recommendations."
        )
    return res


def derive_buyer_ebitda(sde: Optional[float], owner_replacement_cost: Optional[float]) -> Optional[float]:
    """Implied adjusted EBITDA a buyer could expect after hiring a manager
    to replace the working owner.

    SDE includes the working owner's compensation as available benefit; a
    buyer who must pay a manager to do that job keeps only SDE minus the
    replacement cost. This conversion is always disclosed, never silent.
    """
    if sde is None:
        return None
    cost = owner_replacement_cost or 0.0
    return sde - cost
