"""
Core assessment data model — pure Python, no Streamlit imports.

Every piece of information in an assessment carries an implicit provenance
class (see docs/ARCHITECTURE.md):

- user-entered facts        -> BusinessProfile, FinancialPeriod fields
- proposed adjustments      -> Adjustment(status="proposed")
- supported adjustments     -> Adjustment(status="supported")
- market-derived assumptions-> MultipleAssumption(kind="supported")
- illustrative assumptions  -> MultipleAssumption(kind="illustrative")
- hypothetical scenarios    -> Scenario (never written back to core inputs)
- calculated outputs        -> produced by sbi_valuation.engine at read time

Calculated outputs are deliberately *not* stored on the Assessment; they are
recomputed from inputs so upstream changes always invalidate downstream
results.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

PROFIT_BASES = ("net_income", "operating_income", "ebitda", "unknown")
PROFIT_BASE_LABELS = {
    "net_income": "Net income (bottom line, after interest and taxes)",
    "operating_income": "Operating income / EBIT (before interest and taxes)",
    "ebitda": "EBITDA (before interest, taxes, depreciation, amortization)",
    "unknown": "I'm not sure which profit figure I have",
}

INFO_SOURCES = ("tax_return", "accountant", "bookkeeping", "estimate")
INFO_SOURCE_LABELS = {
    "tax_return": "Filed tax return",
    "accountant": "Accountant-prepared financial statements",
    "bookkeeping": "Bookkeeping records (e.g. QuickBooks)",
    "estimate": "Owner estimate / memory",
}

PURPOSES = (
    "understand_value",
    "consider_selling",
    "evaluate_acquisition",
    "succession_planning",
    "improve_value",
)
PURPOSE_LABELS = {
    "understand_value": "Understand current business value",
    "consider_selling": "Consider selling the business",
    "evaluate_acquisition": "Evaluate a potential acquisition",
    "succession_planning": "Succession or retirement planning",
    "improve_value": "Improve business value",
}

LEGAL_STRUCTURES = (
    "sole_proprietorship",
    "llc",
    "s_corp",
    "c_corp",
    "partnership",
    "other",
)
LEGAL_STRUCTURE_LABELS = {
    "sole_proprietorship": "Sole proprietorship",
    "llc": "LLC",
    "s_corp": "S corporation",
    "c_corp": "C corporation",
    "partnership": "Partnership",
    "other": "Other / not sure",
}

OWNER_INVOLVEMENT = ("full_time", "part_time", "minimal", "absentee")
OWNER_INVOLVEMENT_LABELS = {
    "full_time": "Full-time, hands-on (business depends on me daily)",
    "part_time": "Part-time, business mostly runs with a manager",
    "minimal": "Minimal involvement, management runs the business",
    "absentee": "Absentee owner",
}

ADJUSTMENT_CATEGORIES = (
    "interest",
    "income_tax",
    "depreciation",
    "amortization",
    "owner_compensation",
    "discretionary",
    "nonrecurring",
    "other_addback",
    "normalization_deduction",
)
ADJUSTMENT_CATEGORY_LABELS = {
    "interest": "Interest expense",
    "income_tax": "Income tax expense",
    "depreciation": "Depreciation",
    "amortization": "Amortization",
    "owner_compensation": "Owner compensation (salary, benefits, perks)",
    "discretionary": "Discretionary / personal expense",
    "nonrecurring": "One-time / nonrecurring expense",
    "other_addback": "Other add-back",
    "normalization_deduction": "Required deduction (e.g. replacement labor)",
}

ADJUSTMENT_STATUSES = ("proposed", "supported", "needs_review", "rejected")
ADJUSTMENT_STATUS_LABELS = {
    "proposed": "Proposed",
    "supported": "Supported",
    "needs_review": "Needs review",
    "rejected": "Rejected / excluded",
}

MULTIPLE_KINDS = ("illustrative", "supported", "ai_suggested")
MULTIPLE_KIND_LABELS = {
    "illustrative": "Illustrative assumption — not market-derived",
    "supported": "Externally supported assumption (source recorded)",
    "ai_suggested": "AI-assisted research — suggested multiple range",
}

VALUATION_METHODS = ("sde_multiple", "ebitda_multiple", "adjusted_net_asset")
VALUATION_METHOD_LABELS = {
    "sde_multiple": "SDE multiple method",
    "ebitda_multiple": "EBITDA multiple method",
    "adjusted_net_asset": "Adjusted net asset method",
}

DRIVER_ANSWERS = ("strong", "partial", "weak", "not_sure")
DRIVER_ANSWER_LABELS = {
    "strong": "Strong / Yes",
    "partial": "Partially / Somewhat",
    "weak": "Weak / No",
    "not_sure": "Not sure",
}

ACTION_PRIORITIES = ("high", "medium", "low")
ACTION_STATUSES = ("not_started", "in_progress", "done")
ACTION_STATUS_LABELS = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "done": "Done",
}

SALE_TIMEFRAMES = (6, 12, 24)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Model classes
# ---------------------------------------------------------------------------


@dataclass
class BusinessProfile:
    business_name: str = ""
    industry: str = ""
    specialization: str = ""
    years_operating: Optional[float] = None
    legal_structure: str = ""
    city: str = ""
    state: str = ""
    owner_involvement: str = ""
    employee_count: Optional[int] = None
    working_owners: int = 1
    purposes: list = field(default_factory=list)
    is_demo: bool = False


@dataclass
class FinancialPeriod:
    """One reporting period of summary financial information.

    ``reported_profit`` is whatever basis the owner actually has; the
    normalization engine decides what may be added back based on
    ``profit_basis``. ``owner_draws`` is informational only — draws and
    distributions are not expenses and are never eligible add-backs.
    """

    label: str = ""
    kind: str = "fiscal_year"  # "fiscal_year" | "ytd"
    months: int = 12
    revenue: Optional[float] = None
    reported_profit: Optional[float] = None
    profit_basis: str = "unknown"
    owner_compensation: Optional[float] = None
    owner_draws: Optional[float] = None
    info_source: str = ""
    statements_available: bool = False

    def is_partial(self) -> bool:
        return self.kind == "ytd" or (self.months or 12) < 12


@dataclass
class Adjustment:
    id: str = field(default_factory=_new_id)
    period_label: str = ""
    description: str = ""
    amount: float = 0.0  # positive = add-back to earnings; negative = deduction
    category: str = "other_addback"
    explanation: str = ""
    evidence_ref: str = ""
    status: str = "proposed"


@dataclass
class MultipleAssumption:
    """A low/mid/high multiple with explicit provenance.

    ``kind="illustrative"`` means the numbers are an educational
    illustration, not a market benchmark. ``kind="supported"`` requires a
    source description and date supplied by the user.
    """

    method: str = "sde_multiple"
    kind: str = "illustrative"
    low: float = 1.5
    mid: float = 2.5
    high: float = 3.5
    source: str = ""
    source_date: str = ""


@dataclass
class AssetMethodInputs:
    """Inputs for the adjusted net asset method (fair market value basis)."""

    equipment_ffe: Optional[float] = None
    inventory: Optional[float] = None
    receivables: Optional[float] = None
    real_estate: Optional[float] = None
    other_assets: Optional[float] = None
    liabilities_transferred: Optional[float] = None
    include_real_estate: bool = False
    notes: str = ""


@dataclass
class ValuationInputs:
    sde_multiple: MultipleAssumption = field(
        default_factory=lambda: MultipleAssumption(method="sde_multiple")
    )
    ebitda_multiple: MultipleAssumption = field(
        default_factory=lambda: MultipleAssumption(
            method="ebitda_multiple", low=2.0, mid=3.0, high=4.5
        )
    )
    # EBITDA basis actually used by the EBITDA method. If None and a method
    # run is requested, the engine derives it from SDE minus the owner
    # replacement cost below (a disclosed assumption, never silent).
    ebitda_override: Optional[float] = None
    owner_replacement_cost: Optional[float] = None
    primary_method: str = "sde_multiple"
    asset_inputs: AssetMethodInputs = field(default_factory=AssetMethodInputs)
    # AI-assisted research result (from engine.research.AIResearch) —
    # stored as a plain dict so it survives export/import.
    ai_research: dict = field(default_factory=dict)
    # Equity reconciliation (optional, disclosed transaction assumptions)
    excess_cash: Optional[float] = None
    debt_assumed: Optional[float] = None
    transaction_note: str = (
        "Illustrative asset-sale framing: seller delivers the business "
        "free of debt and retains cash unless otherwise noted."
    )


@dataclass
class Scenario:
    """A hypothetical what-if scenario.

    Scenarios NEVER modify assessment inputs; they hold optional overrides
    applied on top of the baseline at calculation time.
    """

    id: str = field(default_factory=_new_id)
    name: str = "Scenario"
    description: str = ""
    method: str = "sde_multiple"
    earnings: Optional[float] = None  # None -> use baseline earnings
    multiple: Optional[float] = None  # None -> use baseline mid multiple
    created_from: str = "custom"  # "preset" | "custom"


@dataclass
class ActionItem:
    id: str = field(default_factory=_new_id)
    category: str = ""
    issue: str = ""
    why: str = ""
    action: str = ""
    priority: str = "medium"
    timeframe: str = ""
    status: str = "not_started"
    source: str = "assessment"  # "assessment" | "manual"


@dataclass
class Assessment:
    id: str = field(default_factory=_new_id)
    schema_version: int = SCHEMA_VERSION
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    label: str = ""

    profile: BusinessProfile = field(default_factory=BusinessProfile)
    financials: list = field(default_factory=list)  # list[FinancialPeriod]
    primary_period_label: str = ""
    adjustments: list = field(default_factory=list)  # list[Adjustment]
    driver_answers: dict = field(default_factory=dict)  # qid -> answer key
    valuation: ValuationInputs = field(default_factory=ValuationInputs)
    scenarios: list = field(default_factory=list)  # list[Scenario]
    action_items: list = field(default_factory=list)  # list[ActionItem]
    asking_price: Optional[float] = None
    sale_timeframe_months: int = 12

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Assessment":
        data = dict(data or {})
        data["profile"] = BusinessProfile(**data.get("profile") or {})
        data["financials"] = [
            FinancialPeriod(**p) for p in data.get("financials") or []
        ]
        data["adjustments"] = [
            Adjustment(**a) for a in data.get("adjustments") or []
        ]
        val = dict(data.get("valuation") or {})
        if "sde_multiple" in val:
            val["sde_multiple"] = MultipleAssumption(**val["sde_multiple"])
        if "ebitda_multiple" in val:
            val["ebitda_multiple"] = MultipleAssumption(**val["ebitda_multiple"])
        if "asset_inputs" in val:
            val["asset_inputs"] = AssetMethodInputs(**val["asset_inputs"])
        if "ai_research" in val and val["ai_research"]:
            from ..engine.research import AIResearch
            val["ai_research"] = val["ai_research"] if not isinstance(
                val["ai_research"], dict) else {
                **vars(AIResearch()), **val["ai_research"]}
            val["ai_research"]["sources"] = val["ai_research"].get("sources") or []
        data["valuation"] = ValuationInputs(**val)
        data["scenarios"] = [Scenario(**s) for s in data.get("scenarios") or []]
        data["action_items"] = [
            ActionItem(**a) for a in data.get("action_items") or []
        ]
        data.pop("schema_version", None) if data.get("schema_version") is None else None
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def primary_period(self) -> Optional[FinancialPeriod]:
        if not self.financials:
            return None
        for p in self.financials:
            if p.label == self.primary_period_label:
                return p
        return self.financials[0]
