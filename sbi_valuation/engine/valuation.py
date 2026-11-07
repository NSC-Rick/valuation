"""
Valuation methods: SDE multiple, EBITDA multiple, adjusted net asset.

Safeguards enforced here:

- Multiples carry explicit provenance (``kind="illustrative"`` vs
  ``kind="supported"``); illustrative results are always flagged as such.
- EBITDA multiples are only ever applied to an EBITDA basis — never to SDE.
- Methods are never averaged together; each produces its own indication.
- Earnings-based methods refuse to run on negative or missing earnings.
- Enterprise-to-equity reconciliation is explicit and disclosed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models.assessment import (
    AssetMethodInputs,
    MultipleAssumption,
    ValuationInputs,
)
from .normalization import derive_buyer_ebitda


@dataclass
class ValuationIndication:
    method: str
    method_label: str
    earnings_basis: str = ""
    earnings: Optional[float] = None
    multiple_low: Optional[float] = None
    multiple_mid: Optional[float] = None
    multiple_high: Optional[float] = None
    value_low: Optional[float] = None
    value_mid: Optional[float] = None
    value_high: Optional[float] = None
    illustrative: bool = True
    runnable: bool = False
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass
class EquityReconciliation:
    enterprise_value: Optional[float] = None
    plus_cash: float = 0.0
    less_debt: float = 0.0
    equity_value: Optional[float] = None
    note: str = ""


def _range(earnings: float, m: MultipleAssumption) -> tuple:
    return (earnings * m.low, earnings * m.mid, earnings * m.high)


def value_by_sde_multiple(
    sde: Optional[float], m: MultipleAssumption
) -> ValuationIndication:
    ind = ValuationIndication(
        method="sde_multiple",
        method_label="SDE multiple method",
        earnings_basis="SDE",
        earnings=sde,
        multiple_low=m.low,
        multiple_mid=m.mid,
        multiple_high=m.high,
        illustrative=(m.kind != "supported"),
    )
    if sde is None:
        ind.warnings.append("No normalized SDE available yet.")
        return ind
    if sde < 0:
        ind.warnings.append(
            "SDE is negative — an earnings-multiple result is not meaningful."
        )
        return ind
    ind.value_low, ind.value_mid, ind.value_high = _range(sde, m)
    ind.runnable = True
    ind.notes.append(
        "Value indicated = normalized SDE x SDE multiple. This is an "
        "owner-benefit-based indication of business value (typical asset-sale "
        "framing for owner-operated businesses), not a formal appraisal."
    )
    if m.kind == "ai_suggested":
        ind.notes.append(
            "Multiple originated from AI-assisted research — an educational "
            "suggestion to review, not externally supported evidence."
        )
    elif m.kind != "supported":
        ind.notes.append(
            "Multiple is an illustrative assumption — enter a supported "
            "multiple with a recorded source to strengthen this estimate."
        )
    else:
        ind.notes.append(
            f"Multiple source: {m.source or '(not recorded)'}"
            + (f" ({m.source_date})" if m.source_date else "")
        )
    return ind


def value_by_ebitda_multiple(
    ebitda: Optional[float], m: MultipleAssumption
) -> ValuationIndication:
    ind = ValuationIndication(
        method="ebitda_multiple",
        method_label="EBITDA multiple method",
        earnings_basis="EBITDA",
        earnings=ebitda,
        multiple_low=m.low,
        multiple_mid=m.mid,
        multiple_high=m.high,
        illustrative=(m.kind != "supported"),
    )
    if ebitda is None:
        ind.warnings.append(
            "No EBITDA basis available. Provide normalized EBITDA or an "
            "owner-replacement cost to derive it from SDE."
        )
        return ind
    if ebitda < 0:
        ind.warnings.append(
            "EBITDA is negative — an earnings-multiple result is not meaningful."
        )
        return ind
    ind.value_low, ind.value_mid, ind.value_high = _range(ebitda, m)
    ind.runnable = True
    ind.notes.append(
        "Value indicated = normalized EBITDA x EBITDA multiple. EBITDA "
        "excludes the working owner's compensation benefit — do not apply "
        "this multiple to SDE."
    )
    if m.kind != "supported":
        ind.notes.append("Multiple is an illustrative assumption.")
    else:
        ind.notes.append(
            f"Multiple source: {m.source or '(not recorded)'}"
            + (f" ({m.source_date})" if m.source_date else "")
        )
    return ind


def value_by_net_assets(ai: AssetMethodInputs) -> ValuationIndication:
    ind = ValuationIndication(
        method="adjusted_net_asset",
        method_label="Adjusted net asset method",
        earnings_basis="Asset values (FMV)",
        illustrative=False,
    )
    parts = {
        "Equipment, furniture & fixtures": ai.equipment_ffe,
        "Inventory": ai.inventory,
        "Accounts receivable": ai.receivables,
        "Other assets": ai.other_assets,
    }
    total = sum(v or 0.0 for v in parts.values())
    if ai.include_real_estate:
        total += ai.real_estate or 0.0
    elif ai.real_estate:
        ind.notes.append(
            "Real estate value entered but marked excluded — typical when "
            "the property is sold or leased separately."
        )
    liabilities = ai.liabilities_transferred or 0.0
    value = total - liabilities
    ind.earnings = total
    ind.value_low = ind.value_mid = ind.value_high = value
    ind.runnable = total > 0 or liabilities != 0
    ind.notes.append(
        "Value indicated = fair market value of included assets minus "
        "liabilities a buyer would assume. Most appropriate for "
        "asset-intensive businesses or when earnings do not support an "
        "earnings-based valuation."
    )
    if not ind.runnable:
        ind.warnings.append("No asset values entered yet.")
    return ind


def run_methods(
    assessment,
    sde: Optional[float],
) -> dict:
    """Run every valuation method with the inputs on the assessment.

    Returns {method_key: ValuationIndication}. Each indication stands on
    its own — results are never blended.
    """
    vi: ValuationInputs = assessment.valuation
    ebitda = vi.ebitda_override
    if ebitda is None:
        ebitda = derive_buyer_ebitda(sde, vi.owner_replacement_cost)
    return {
        "sde_multiple": value_by_sde_multiple(sde, vi.sde_multiple),
        "ebitda_multiple": value_by_ebitda_multiple(ebitda, vi.ebitda_multiple),
        "adjusted_net_asset": value_by_net_assets(vi.asset_inputs),
    }


def reconcile_equity(
    enterprise_value: Optional[float],
    excess_cash: Optional[float],
    debt_assumed: Optional[float],
    note: str = "",
) -> EquityReconciliation:
    """Enterprise value -> equity value bridge.

    In a typical small-business asset sale the parties negotiate a
    cash-free / debt-free transfer: the seller keeps cash and pays off
    debt. These optional fields let a user state a different assumption
    explicitly.
    """
    cash = excess_cash or 0.0
    debt = debt_assumed or 0.0
    equity = None if enterprise_value is None else enterprise_value + cash - debt
    return EquityReconciliation(
        enterprise_value=enterprise_value,
        plus_cash=cash,
        less_debt=debt,
        equity_value=equity,
        note=note,
    )
