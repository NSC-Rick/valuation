"""End-to-end integration tests: full assessment lifecycle (no Streamlit)."""
import pytest

from sbi_valuation.engine.action_plan import generate_plan
from sbi_valuation.engine.drivers import analyze_drivers
from sbi_valuation.engine.evidence import assess_evidence
from sbi_valuation.engine.marketability import point_for_price
from sbi_valuation.engine.normalization import reconcile
from sbi_valuation.engine.scenarios import evaluate_scenario
from sbi_valuation.engine.valuation import run_methods
from sbi_valuation.models.assessment import (
    Adjustment,
    Assessment,
    FinancialPeriod,
    Scenario,
)
from sbi_valuation.report.pdf import build_report
from sbi_valuation.storage.portfolio import export_assessment, import_assessment
from sbi_valuation.ui.state import Results


def _results(a) -> Results:
    period = a.primary_period()
    norm = reconcile(period, a.adjustments) if period else None
    sde = norm.best_sde if norm else None
    vals = run_methods(a, sde)
    return Results(period, norm, vals, assess_evidence(a, norm, vals),
                   analyze_drivers(a.driver_answers), sde,
                   vals["ebitda_multiple"].earnings)


def _full_assessment() -> Assessment:
    a = Assessment()
    p = a.profile
    p.business_name = "Green Mountain Landscaping"
    p.industry = "Professional services"
    p.years_operating = 8
    p.legal_structure = "llc"
    p.owner_involvement = "full_time"
    p.employee_count = 6
    p.purposes = ["consider_selling"]
    for label, rev, profit in [("FY2022", 620_000, 82_000),
                               ("FY2023", 660_000, 91_000),
                               ("FY2024", 700_000, 95_000)]:
        a.financials.append(FinancialPeriod(
            label=label, revenue=rev, reported_profit=profit,
            profit_basis="net_income", owner_compensation=75_000,
            info_source="tax_return", statements_available=True))
    a.primary_period_label = "FY2024"
    a.adjustments = [
        Adjustment(period_label="FY2024", description="Owner salary",
                   amount=75_000, category="owner_compensation",
                   status="supported", evidence_ref="2024 W-2"),
        Adjustment(period_label="FY2024", description="Interest",
                   amount=4_000, category="interest", status="supported"),
        Adjustment(period_label="FY2024", description="Depreciation",
                   amount=12_000, category="depreciation", status="supported"),
        Adjustment(period_label="FY2024", description="One-time legal dispute",
                   amount=9_000, category="nonrecurring", status="proposed"),
    ]
    a.driver_answers = {
        "od_1": "weak", "od_2": "partial", "od_3": "weak", "od_4": "partial",
        "cs_1": "strong", "cs_2": "partial", "cs_3": "strong", "cs_4": "partial",
        "fs_1": "strong", "fs_2": "strong", "fs_3": "strong", "fs_4": "partial",
        "em_1": "weak", "em_2": "strong", "em_3": "partial", "em_4": "partial",
        "mp_1": "strong", "mp_2": "strong", "mp_3": "partial", "mp_4": "strong",
        "ot_1": "partial", "ot_2": "strong", "ot_3": "strong", "ot_4": "strong",
    }
    return a


def test_full_pipeline():
    a = _full_assessment()
    r = _results(a)

    # Normalization: 95 + 75 + 4 + 12 = 186 supported; +9 provisional
    assert r.sde == 186_000
    assert r.normalization.provisional_sde == 195_000

    # Valuation: SDE mid 2.5 → 465,000
    prim = r.valuations["sde_multiple"]
    assert prim.runnable and prim.value_mid == 465_000
    assert prim.illustrative

    # Evidence has content
    assert r.evidence.overall in ("moderate", "limited", "strong")
    assert r.evidence.all_recommendations

    # Action plan generates
    plan = generate_plan(a, r.evidence)
    assert plan.generated > 0
    a.action_items = plan.items

    # Scenario isolation + evaluation
    s = Scenario(name="Growth", earnings=r.sde * 1.1, multiple=2.5)
    res = evaluate_scenario(s, r.sde, a.valuation.sde_multiple.mid)
    assert res.value == pytest.approx(186_000 * 1.1 * 2.5)

    # Marketability point is descriptive
    pt = point_for_price(520_000, prim.value_mid)
    assert "probability" not in pt.band.lower()

    # Reports build
    for rtype in ("executive", "comprehensive", "improvement"):
        assert build_report(a, r, rtype)[:5] == b"%PDF-"

    # Save → resume → identical
    blob = export_assessment(a, passphrase="pw123")
    a2 = import_assessment(blob, "pw123")
    r2 = _results(a2)
    assert r2.sde == r.sde
    assert r2.valuations["sde_multiple"].value_mid == prim.value_mid
    assert len(a2.action_items) == len(a.action_items)


def test_upstream_change_invalidates_results():
    """Editing the financial snapshot must change downstream results on
    recompute — no stale caching."""
    a = _full_assessment()
    r1 = _results(a)
    a.primary_period().reported_profit = 150_000
    r2 = _results(a)
    assert r2.sde != r1.sde
    assert r2.valuations["sde_multiple"].value_mid != \
        r1.valuations["sde_multiple"].value_mid


def test_historical_periods_scoped():
    """Adjustments only apply to their tagged period."""
    a = _full_assessment()
    fy23 = next(p for p in a.financials if p.label == "FY2023")
    norm23 = reconcile(fy23, a.adjustments)
    # Only FY2023-tagged or untagged adjustments apply — none here
    assert norm23.supported_sde == 91_000
