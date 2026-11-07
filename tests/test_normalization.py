"""Earnings normalization tests — the core accounting rules."""
import pytest

from sbi_valuation.engine.normalization import (
    derive_buyer_ebitda,
    reconcile,
    validate_adjustment,
)
from sbi_valuation.models.assessment import Adjustment, FinancialPeriod


def period(basis="net_income", profit=100_000.0, label="FY2024", comp=60_000.0):
    return FinancialPeriod(
        label=label, profit_basis=basis, reported_profit=profit,
        owner_compensation=comp, revenue=500_000.0,
    )


def adj(desc, amount, cat="discretionary", status="supported", period_label="FY2024"):
    return Adjustment(description=desc, amount=amount, category=cat,
                      status=status, period_label=period_label)


class TestNetIncomeToSDE:
    def test_full_reconciliation(self):
        p = period("net_income", 100_000)
        adjs = [
            adj("Interest", 5_000, "interest"),
            adj("Income tax", 12_000, "income_tax"),
            adj("Depreciation", 8_000, "depreciation"),
            adj("Owner comp", 60_000, "owner_compensation"),
            adj("Personal vehicle", 3_000, "discretionary"),
            adj("Replacement labor", -20_000, "normalization_deduction"),
        ]
        res = reconcile(p, adjs)
        # 100k + 5 + 12 + 8 + 60 + 3 - 20 = 168k
        assert res.supported_sde == pytest.approx(168_000)
        assert res.basis_established

    def test_supported_vs_provisional(self):
        p = period("net_income", 100_000)
        adjs = [
            adj("Interest", 5_000, "interest", status="supported"),
            adj("Discretionary", 10_000, "discretionary", status="proposed"),
        ]
        res = reconcile(p, adjs)
        assert res.supported_sde == pytest.approx(105_000)
        assert res.provisional_sde == pytest.approx(115_000)

    def test_rejected_excluded(self):
        p = period("net_income", 100_000)
        res = reconcile(p, [adj("Discretionary", 10_000, "discretionary", status="rejected")])
        assert res.supported_sde == pytest.approx(100_000)


class TestBasisGuards:
    def test_operating_income_blocks_interest_tax(self):
        """Interest and taxes were NOT deducted to reach EBIT — adding them
        back double-counts."""
        p = period("operating_income", 100_000)
        res = reconcile(p, [
            adj("Interest", 5_000, "interest"),
            adj("Tax", 12_000, "income_tax"),
            adj("Depreciation", 8_000, "depreciation"),
            adj("Owner comp", 60_000, "owner_compensation"),
        ])
        # Only D&A and owner comp are eligible: 100 + 8 + 60 = 168
        assert res.supported_sde == pytest.approx(168_000)
        assert any("double-count" in f for f in res.flags)

    def test_ebitda_blocks_all_noncash_and_financing(self):
        p = period("ebitda", 100_000)
        res = reconcile(p, [
            adj("Interest", 5_000, "interest"),
            adj("Tax", 12_000, "income_tax"),
            adj("Depreciation", 8_000, "depreciation"),
            adj("Amortization", 2_000, "amortization"),
            adj("Owner comp", 60_000, "owner_compensation"),
        ])
        # Only operating-expense add-backs (owner comp): 160k
        assert res.supported_sde == pytest.approx(160_000)
        assert sum("double-count" in f for f in res.flags) == 4

    def test_unknown_basis_blocks_addbacks(self):
        p = period("unknown", 100_000)
        res = reconcile(p, [adj("Interest", 5_000, "interest")])
        assert not res.basis_established
        assert res.supported_sde == pytest.approx(100_000)
        assert any("basis" in f.lower() for f in res.flags)

    def test_validate_adjustment_deduction_sign(self):
        bad = adj("Replacement", +15_000, "normalization_deduction")
        assert not validate_adjustment(bad, "net_income").eligible
        good = adj("Replacement", -15_000, "normalization_deduction")
        assert validate_adjustment(good, "net_income").eligible


class TestOwnerCompensation:
    def test_multiple_owner_comp_flagged(self):
        p = period("net_income", 100_000)
        res = reconcile(p, [
            adj("Owner 1 comp", 60_000, "owner_compensation"),
            adj("Owner 2 comp", 45_000, "owner_compensation"),
        ])
        assert any("ONE working owner" in f for f in res.flags)

    def test_draws_are_never_an_adjustment(self):
        """Owner draws live on the period as informational data; the
        adjustment vocabulary has no 'draws' category, so they can't be
        added back."""
        p = period("net_income", 100_000)
        p.owner_draws = 40_000
        res = reconcile(p, [adj("Owner comp (salary)", 60_000, "owner_compensation")])
        assert res.supported_sde == pytest.approx(160_000)
        # draws never enter the reconciliation
        assert all("draw" not in ln.label.lower() for ln in res.lines)


class TestEdgeCases:
    def test_negative_earnings_flagged(self):
        p = period("net_income", -30_000)
        res = reconcile(p, [adj("Owner comp", 10_000, "owner_compensation")])
        assert res.supported_sde == pytest.approx(-20_000)
        assert any("negative" in f.lower() for f in res.flags)

    def test_missing_profit(self):
        p = period("net_income", None)
        res = reconcile(p, [])
        assert res.supported_sde is None
        assert res.flags

    def test_period_scoping(self):
        """Adjustments tagged to a different period don't leak in."""
        p = period("net_income", 100_000, label="FY2024")
        res = reconcile(p, [
            adj("Old interest", 5_000, "interest", period_label="FY2023"),
            adj("Current interest", 5_000, "interest", period_label="FY2024"),
            adj("Untagged", 1_000, "discretionary", period_label=""),
        ])
        assert res.supported_sde == pytest.approx(106_000)

    def test_double_count_prevention_same_expense(self):
        """Two adjustments describing the same expense: statuses/categories
        are tracked per-line; reviewers mark one rejected — engine respects it."""
        p = period("net_income", 100_000)
        res = reconcile(p, [
            adj("Interest (card)", 5_000, "interest", status="supported"),
            adj("Interest (card duplicate)", 5_000, "interest", status="rejected"),
        ])
        assert res.supported_sde == pytest.approx(105_000)


class TestBuyerEBITDA:
    def test_derive(self):
        assert derive_buyer_ebitda(200_000, 60_000) == 140_000
        assert derive_buyer_ebitda(None, 60_000) is None
        assert derive_buyer_ebitda(200_000, None) == 200_000
