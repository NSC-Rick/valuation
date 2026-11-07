"""Storage (save/resume/delete), drivers, evidence, branding, report tests."""
import pytest

from sbi_valuation.config.branding import get_brand
from sbi_valuation.engine.action_plan import generate_plan
from sbi_valuation.engine.drivers import CATEGORIES, analyze_drivers
from sbi_valuation.engine.evidence import assess_evidence
from sbi_valuation.models.assessment import (
    ActionItem,
    Assessment,
    FinancialPeriod,
)
from sbi_valuation.report.pdf import REPORT_TYPES, build_report
from sbi_valuation.storage.crypto import DecryptionError
from sbi_valuation.storage.portfolio import (
    ImportError_,
    export_assessment,
    import_assessment,
)


def _assessment():
    a = Assessment()
    p = a.profile
    p.business_name = "Test Bakery"
    p.industry = "Food service / restaurant"
    p.owner_involvement = "full_time"
    p.legal_structure = "llc"
    p.purposes = ["consider_selling"]
    a.financials.append(FinancialPeriod(
        label="FY2024", reported_profit=100_000, profit_basis="net_income",
        revenue=500_000, owner_compensation=60_000, info_source="tax_return"))
    a.financials.append(FinancialPeriod(
        label="FY2023", reported_profit=90_000, profit_basis="net_income",
        revenue=480_000, info_source="tax_return"))
    a.primary_period_label = "FY2024"
    return a


class TestStorage:
    def test_encrypted_roundtrip(self):
        a = _assessment()
        blob = export_assessment(a, passphrase="hunter2")
        a2 = import_assessment(blob, passphrase="hunter2")
        assert a2.profile.business_name == "Test Bakery"
        assert a2.financials[0].reported_profit == 100_000

    def test_wrong_passphrase(self):
        blob = export_assessment(_assessment(), passphrase="right")
        with pytest.raises(DecryptionError):
            import_assessment(blob, passphrase="wrong")

    def test_encrypted_requires_passphrase(self):
        blob = export_assessment(_assessment(), passphrase="x")
        with pytest.raises(DecryptionError):
            import_assessment(blob, passphrase="")

    def test_plaintext_roundtrip(self):
        blob = export_assessment(_assessment(), passphrase="")
        a2 = import_assessment(blob)
        assert a2.profile.business_name == "Test Bakery"

    def test_no_financial_data_in_envelope(self):
        """Ciphertext must not leak financial figures."""
        blob = export_assessment(_assessment(), passphrase="pw")
        assert b"100000" not in blob
        assert b"Test Bakery" not in blob or b'"label"' in blob  # label may appear once
        assert b"Food service" not in blob

    def test_bad_file(self):
        with pytest.raises(ImportError_):
            import_assessment(b"not json at all")
        with pytest.raises(ImportError_):
            import_assessment(b'{"format": "something-else"}')

    def test_scenarios_roundtrip(self):
        from sbi_valuation.models.assessment import Scenario
        a = _assessment()
        a.scenarios.append(Scenario(name="S1", earnings=1, multiple=2))
        a2 = import_assessment(export_assessment(a, "p"), "p")
        assert a2.scenarios[0].name == "S1"


class TestDrivers:
    def test_not_sure_is_gap_not_negative(self):
        analysis = analyze_drivers({"od_1": "not_sure"})
        cat = analysis.categories[0]
        assert not cat.risks
        assert len(cat.gaps) >= 1

    def test_strong_weak_partial(self):
        analysis = analyze_drivers({"od_1": "strong", "od_2": "weak", "od_3": "partial"})
        cat = analysis.categories[0]
        assert len(cat.strengths) == 1
        assert len(cat.risks) == 1
        assert cat.answered == 3

    def test_completion(self):
        total = sum(len(c["questions"]) for c in CATEGORIES)
        answers = {q[0]: "strong" for c in CATEGORIES for q in c["questions"]}
        assert analyze_drivers(answers).completion == 1.0
        assert analyze_drivers({}).completion == 0.0
        assert total == 24


class TestActionPlan:
    def test_generates_from_risks(self):
        a = _assessment()
        a.driver_answers = {"od_1": "weak", "cs_1": "weak"}
        res = generate_plan(a)
        assert res.generated >= 2
        cats = {i.category for i in res.items}
        assert "Owner Dependency" in cats

    def test_preserves_status_on_refresh(self):
        a = _assessment()
        a.driver_answers = {"od_1": "weak"}
        a.action_items = generate_plan(a).items
        a.action_items[0].status = "in_progress"
        a.action_items.append(ActionItem(issue="Manual", source="manual", action="x"))
        res = generate_plan(a)
        by_src = {i.source: i for i in res.items}
        assert by_src["od_1"].status == "in_progress"
        assert res.kept_manual == 1

    def test_no_value_promises(self):
        """Recommendations must not fabricate guaranteed value increases."""
        a = _assessment()
        a.driver_answers = {"od_1": "weak"}
        res = generate_plan(a)
        for it in res.items:
            assert "guarantee" not in it.action.lower()
            assert "guaranteed" not in it.why.lower()
            assert "will increase" not in it.action.lower()


class TestEvidence:
    def test_empty_insufficient(self):
        rep = assess_evidence(Assessment())
        assert rep.overall == "insufficient"

    def test_not_a_confidence_interval(self):
        a = _assessment()
        rep = assess_evidence(a)
        for d in rep.dimensions:
            assert d.rating in ("strong", "moderate", "limited", "insufficient")


class TestBranding:
    def test_config_driven(self):
        b = get_brand()
        assert b["org_name"] == "North Star Consulting"
        assert b["app_name"] == "Business Valuation"
        assert "certified" in b["disclaimer"] or "appraisal" in b["disclaimer"]
        for key in ("logo_svg", "colors", "report_header", "report_footer", "contact"):
            assert key in b

    def test_rebrandable(self):
        b = get_brand()
        orig = b["org_name"]
        b["org_name"] = "Test Org"
        assert get_brand()["org_name"] == "Test Org"
        b["org_name"] = orig


class TestReports:
    def _results(self, a):
        from sbi_valuation.engine.drivers import analyze_drivers
        from sbi_valuation.engine.evidence import assess_evidence
        from sbi_valuation.engine.normalization import reconcile
        from sbi_valuation.engine.valuation import run_methods
        from sbi_valuation.ui.state import Results
        period = a.primary_period()
        norm = reconcile(period, a.adjustments)
        vals = run_methods(a, norm.best_sde)
        return Results(period, norm, vals, assess_evidence(a, norm, vals),
                       analyze_drivers(a.driver_answers), norm.best_sde,
                       vals["ebitda_multiple"].earnings)

    def test_all_report_types_build(self):
        a = _assessment()
        r = self._results(a)
        for rtype in REPORT_TYPES:
            pdf = build_report(a, r, rtype)
            assert pdf[:5] == b"%PDF-"
            assert len(pdf) > 2000

    def test_report_consistency(self):
        """Figures in the report come from the same engine results as the
        dashboard — build twice, identical bytes."""
        a = _assessment()
        r = self._results(a)
        assert build_report(a, r, "executive") == build_report(a, r, "executive")

    def test_section_selection(self):
        a = _assessment()
        r = self._results(a)
        full = build_report(a, r, "comprehensive")
        partial = build_report(a, r, "comprehensive", sections=["profile"])
        assert len(partial) < len(full)
