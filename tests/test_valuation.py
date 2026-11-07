"""Valuation method tests."""
import pytest

from sbi_valuation.engine.valuation import (
    reconcile_equity,
    run_methods,
    value_by_ebitda_multiple,
    value_by_net_assets,
    value_by_sde_multiple,
)
from sbi_valuation.models.assessment import (
    Assessment,
    AssetMethodInputs,
    MultipleAssumption,
)


def mult(low=1.5, mid=2.5, high=3.5, kind="illustrative", method="sde_multiple"):
    return MultipleAssumption(method=method, kind=kind, low=low, mid=mid, high=high)


class TestSDEMultiple:
    def test_range(self):
        ind = value_by_sde_multiple(200_000, mult())
        assert ind.runnable
        assert (ind.value_low, ind.value_mid, ind.value_high) == (300_000, 500_000, 700_000)

    def test_illustrative_flagged(self):
        ind = value_by_sde_multiple(200_000, mult(kind="illustrative"))
        assert ind.illustrative
        assert any("illustrative" in n.lower() for n in ind.notes)

    def test_supported_records_source(self):
        m = mult(kind="supported")
        m.source = "Broker opinion"
        m.source_date = "2025-06"
        ind = value_by_sde_multiple(200_000, m)
        assert not ind.illustrative
        assert any("Broker opinion" in n for n in ind.notes)

    def test_negative_sde_not_runnable(self):
        ind = value_by_sde_multiple(-50_000, mult())
        assert not ind.runnable

    def test_missing_sde(self):
        ind = value_by_sde_multiple(None, mult())
        assert not ind.runnable


class TestEBITDAMultiple:
    def test_applies_to_ebitda_only(self):
        ind = value_by_ebitda_multiple(150_000, mult(2, 3, 4.5, method="ebitda_multiple"))
        assert (ind.value_low, ind.value_mid, ind.value_high) == (300_000, 450_000, 675_000)
        assert ind.earnings_basis == "EBITDA"
        assert any("do not apply" in n.lower() or "not apply" in n.lower() or "SDE" in n for n in ind.notes)


class TestNetAsset:
    def test_sum_less_liabilities(self):
        ai = AssetMethodInputs(
            equipment_ffe=100_000, inventory=50_000, receivables=20_000,
            real_estate=300_000, other_assets=10_000,
            liabilities_transferred=40_000, include_real_estate=False,
        )
        ind = value_by_net_assets(ai)
        # 100+50+20+10 = 180 - 40 = 140 (real estate excluded)
        assert ind.value_mid == 140_000

    def test_real_estate_included(self):
        ai = AssetMethodInputs(equipment_ffe=100_000, real_estate=300_000,
                               include_real_estate=True)
        ind = value_by_net_assets(ai)
        assert ind.value_mid == 400_000

    def test_empty_not_runnable(self):
        ind = value_by_net_assets(AssetMethodInputs())
        assert not ind.runnable


class TestRunMethods:
    def test_methods_independent(self):
        """Each method produces its own indication — never averaged."""
        a = Assessment()
        a.valuation.sde_multiple = mult()
        a.valuation.ebitda_multiple = mult(2, 3, 4.5, method="ebitda_multiple")
        a.valuation.owner_replacement_cost = 50_000
        inds = run_methods(a, sde=200_000)
        assert inds["sde_multiple"].value_mid == 500_000
        # EBITDA = 200 - 50 = 150 → 450
        assert inds["ebitda_multiple"].earnings == 150_000
        assert inds["ebitda_multiple"].value_mid == 450_000

    def test_ebitda_override(self):
        a = Assessment()
        a.valuation.ebitda_override = 180_000
        inds = run_methods(a, sde=200_000)
        assert inds["ebitda_multiple"].earnings == 180_000


class TestEquityReconciliation:
    def test_bridge(self):
        eq = reconcile_equity(500_000, excess_cash=30_000, debt_assumed=120_000)
        assert eq.equity_value == 410_000

    def test_none_enterprise(self):
        eq = reconcile_equity(None, 10_000, 5_000)
        assert eq.equity_value is None
