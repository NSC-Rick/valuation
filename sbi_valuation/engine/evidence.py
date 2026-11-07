"""
Evidence-quality assessment.

Rates five dimensions qualitatively (strong / moderate / limited /
insufficient) — deliberately NOT a statistical confidence interval — and
produces concrete recommendations for improving estimate reliability.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .drivers import CATEGORIES

RATINGS = ("strong", "moderate", "limited", "insufficient")
RATING_LABELS = {
    "strong": "Strong",
    "moderate": "Moderate",
    "limited": "Limited",
    "insufficient": "Insufficient",
}
RATING_ORDER = {r: i for i, r in enumerate(RATINGS)}


@dataclass
class EvidenceDimension:
    id: str
    name: str
    rating: str = "insufficient"
    reasons: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


@dataclass
class EvidenceReport:
    dimensions: list = field(default_factory=list)  # list[EvidenceDimension]

    @property
    def overall(self) -> str:
        if not self.dimensions:
            return "insufficient"
        worst = max(RATING_ORDER[d.rating] for d in self.dimensions)
        return RATINGS[worst]

    @property
    def all_recommendations(self) -> list:
        return [r for d in self.dimensions for r in d.recommendations]


def _source_weight(source: str) -> int:
    return {"tax_return": 3, "accountant": 2, "bookkeeping": 1, "estimate": 0}.get(source, 0)


def assess_evidence(assessment, normalization=None, valuations=None) -> EvidenceReport:
    rep = EvidenceReport()

    # -- 1. Financial history -------------------------------------------
    d = EvidenceDimension(id="financial_history", name="Financial history")
    periods = [p for p in assessment.financials if p.reported_profit is not None]
    full_years = [p for p in periods if not p.is_partial()]
    best_source = max((_source_weight(p.info_source) for p in periods), default=-1)
    if len(full_years) >= 3 and best_source >= 2:
        d.rating = "strong"
        d.reasons.append("Three completed years with accountant/tax-return sources.")
    elif len(full_years) >= 2 and best_source >= 1:
        d.rating = "moderate"
        d.reasons.append("At least two completed years of financial information.")
        d.recommendations.append("Add a third year and higher-quality sources (tax returns or accountant-prepared statements).")
    elif periods:
        d.rating = "limited"
        d.reasons.append("Only one period or estimate-level information provided.")
        d.recommendations.append("Add prior-year results and base figures on tax returns or prepared statements.")
    else:
        d.rating = "insufficient"
        d.reasons.append("No financial information entered.")
        d.recommendations.append("Enter at least the most recent completed fiscal year.")
    if any(p.is_partial() for p in periods):
        d.reasons.append("Includes a partial-year period (not annualized).")
    rep.dimensions.append(d)

    # -- 2. Earnings normalization --------------------------------------
    d = EvidenceDimension(id="normalization", name="Earnings normalization")
    if normalization is None or normalization.reported_profit is None:
        d.rating = "insufficient"
        d.reasons.append("No earnings figure to normalize.")
        d.recommendations.append("Complete the Financial Snapshot first.")
    else:
        acts = [v for v in normalization.verdicts]
        n_sup = sum(1 for a in assessment.adjustments if a.status == "supported")
        n_adj = len([a for a in assessment.adjustments if a.status != "rejected"])
        if not normalization.basis_established:
            d.rating = "limited"
            d.reasons.append("Profit basis is unknown — add-back eligibility cannot be verified.")
            d.recommendations.append("Identify whether the reported figure is net income, operating income, or EBITDA.")
        elif n_adj and n_sup == n_adj:
            d.rating = "strong"
            d.reasons.append("All adjustments reviewed and marked supported.")
        elif n_sup:
            d.rating = "moderate"
            d.reasons.append(f"{n_sup} of {n_adj} adjustments supported.")
            d.recommendations.append("Review and support the remaining proposed adjustments (evidence references help).")
        else:
            d.rating = "limited" if n_adj else "moderate"
            d.reasons.append(
                "Adjustments entered but none marked supported." if n_adj
                else "No adjustments — earnings used as reported."
            )
            if n_adj:
                d.recommendations.append("Mark adjustments supported once verified against records.")
    rep.dimensions.append(d)

    # -- 3. Market assumption support ------------------------------------
    d = EvidenceDimension(id="market", name="Market assumption support")
    mults = []
    if valuations:
        for ind in valuations.values():
            if ind.runnable:
                mults.append(ind)
    sup = [i for i in mults if not i.illustrative]
    if sup and len(sup) == len(mults) and mults:
        d.rating = "strong"
        d.reasons.append("All applied multiples cite an external source.")
    elif sup:
        d.rating = "moderate"
        d.reasons.append("Some multiples are supported; others are illustrative.")
        d.recommendations.append("Record a source and date for each multiple (broker guidance, published transaction data, advisor input).")
    elif mults:
        d.rating = "limited"
        d.reasons.append("Valuation uses illustrative multiples only.")
        d.recommendations.append("Replace illustrative multiples with sourced figures before relying on the estimate.")
    else:
        d.rating = "insufficient"
        d.reasons.append("No valuation method has produced an estimate yet.")
        d.recommendations.append("Complete Adjusted Earnings to enable valuation methods.")
    rep.dimensions.append(d)

    # -- 4. Business risk information ------------------------------------
    d = EvidenceDimension(id="risk_info", name="Business risk information")
    total_q = sum(len(c["questions"]) for c in CATEGORIES)
    answered = len([v for v in assessment.driver_answers.values() if v])
    unsure = len([v for v in assessment.driver_answers.values() if v == "not_sure"])
    if answered >= total_q and unsure <= total_q * 0.2:
        d.rating = "strong"
        d.reasons.append("All value-driver questions answered.")
    elif answered >= total_q * 0.6:
        d.rating = "moderate"
        d.reasons.append(f"{answered} of {total_q} driver questions answered.")
        d.recommendations.append("Complete remaining driver questions — especially 'Not sure' items, which are information gaps.")
    elif answered:
        d.rating = "limited"
        d.reasons.append(f"Only {answered} of {total_q} driver questions answered.")
        d.recommendations.append("Finish the Business Value Drivers assessment.")
    else:
        d.rating = "insufficient"
        d.reasons.append("No value-driver information provided.")
        d.recommendations.append("Complete the Business Value Drivers assessment.")
    rep.dimensions.append(d)

    # -- 5. Data completeness ---------------------------------------------
    d = EvidenceDimension(id="completeness", name="Data completeness")
    missing = []
    p = assessment.profile
    if not p.industry:
        missing.append("industry")
    if not assessment.financials:
        missing.append("financial snapshot")
    prim = assessment.primary_period()
    if prim and prim.owner_compensation is None:
        missing.append("owner compensation")
    if answered == 0:
        missing.append("value drivers")
    if len(missing) == 0:
        d.rating = "strong"
        d.reasons.append("Core inputs complete.")
    elif len(missing) <= 2:
        d.rating = "moderate"
        d.reasons.append("Missing: " + ", ".join(missing) + ".")
        d.recommendations.append("Fill the remaining inputs for a fuller picture.")
    else:
        d.rating = "limited"
        d.reasons.append("Missing: " + ", ".join(missing) + ".")
        d.recommendations.append("Complete the sections listed to improve reliability.")
    rep.dimensions.append(d)

    return rep
