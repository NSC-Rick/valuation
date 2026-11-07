"""Scenario isolation/reset and marketability labeling tests."""
import pytest

from sbi_valuation.engine import marketability as mk
from sbi_valuation.engine.normalization import reconcile
from sbi_valuation.engine.scenarios import (
    evaluate_scenario,
    preset_scenarios,
)
from sbi_valuation.models.assessment import (
    Assessment,
    FinancialPeriod,
    Scenario,
)


def _assessment():
    a = Assessment()
    a.financials.append(FinancialPeriod(
        label="FY2024", reported_profit=100_000, profit_basis="net_income",
        owner_compensation=60_000))
    return a


class TestScenarios:
    def test_evaluate(self):
        s = Scenario(name="x", earnings=240_000, multiple=3.0)
        res = evaluate_scenario(s, baseline_sde=200_000, baseline_multiple=2.5)
        assert res.value == 720_000
        assert res.delta_abs == 220_000
        assert res.delta_pct == pytest.approx(44.0)

    def test_inherits_baseline(self):
        s = Scenario(name="x")
        res = evaluate_scenario(s, 200_000, 2.5)
        assert res.value == 500_000

    def test_scenario_isolation(self):
        """Scenario edits must never mutate assessment inputs or the
        official valuation recomputes identically."""
        a = _assessment()
        norm_before = reconcile(a.primary_period(), a.adjustments)
        a.scenarios.append(Scenario(name="wild", earnings=999_999, multiple=99))
        res = evaluate_scenario(a.scenarios[0], 160_000, 2.5)
        assert res.value == 999_999 * 99
        # Assessment untouched
        norm_after = reconcile(a.primary_period(), a.adjustments)
        assert norm_before.supported_sde == norm_after.supported_sde
        assert a.financials[0].reported_profit == 100_000
        assert a.valuation.sde_multiple.mid == 2.5

    def test_reset_to_baseline(self):
        a = _assessment()
        a.scenarios = [Scenario(name="a"), Scenario(name="b")]
        a.scenarios.clear()  # reset behavior used by the UI
        assert a.scenarios == []

    def test_presets(self):
        names = [s.name for s in preset_scenarios()]
        assert names == ["Current Business", "Improve Earnings", "Reduce Business Risk"]
        assert all(s.created_from == "preset" for s in preset_scenarios())

    def test_negative_earnings_scenario_blocked(self):
        s = Scenario(earnings=-10_000, multiple=2.0)
        assert evaluate_scenario(s, 200_000, 2.5) is None


class TestMarketability:
    def test_label_constants(self):
        assert "Illustrative" in mk.ILLUSTRATIVE_LABEL
        assert "Educational Simulation" in mk.ILLUSTRATIVE_LABEL
        assert "illustrative" in mk.ILLUSTRATIVE_AXIS.lower()

    def test_no_probability_vocabulary(self):
        """Bands must be descriptive — never percentage probabilities."""
        for idx in (0.0, 0.3, 0.5, 0.7, 1.0):
            band = mk.descriptive_band(idx)
            assert "%" not in band
            assert "marketability" in band.lower()

    def test_index_shape(self):
        at_mid = mk.marketability_index(1.0)
        above = mk.marketability_index(1.5)
        far_above = mk.marketability_index(2.5)
        assert at_mid > above > far_above >= 0
        assert all(0 <= mk.marketability_index(r) <= 1 for r in
                   (0.2, 0.5, 0.8, 1.0, 1.3, 2.0, 5.0))

    def test_presets_ratios(self):
        assert mk.PRICING_PRESETS["competitive"]["ratio"] < 1.0
        assert mk.PRICING_PRESETS["market"]["ratio"] == 1.0
        assert mk.PRICING_PRESETS["aspirational"]["ratio"] > 1.0

    def test_timeframe_no_numbers(self):
        """Timeframe guidance is descriptive only — spec forbids it
        generating numerical probabilities."""
        for months in (6, 12, 24):
            g = mk.timeframe_guidance(months, "Moderate relative marketability")
            assert "%" not in g and "probability" not in g.lower()

    def test_curve_and_point(self):
        pts = mk.curve(500_000)
        assert len(pts) == 60
        assert pts[0].price_ratio == pytest.approx(0.5)
        pt = mk.point_for_price(600_000, 500_000)
        assert pt.price_ratio == pytest.approx(1.2)
        assert mk.point_for_price(0, 500_000) is None
