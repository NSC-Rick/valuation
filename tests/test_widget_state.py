"""Regression tests: widget session-state mutations (Section 07 pricing
presets bug + audit fixes for s03 adjustment form and workspace actions).

StreamlitWidgetAlreadyInstantiatedError fires when st.session_state for a
widget key is assigned/deleted after that widget was instantiated in the
same run. All such mutations now happen in on_click callbacks (which run
before instantiation) or are excluded from clearing.
"""
import re
import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sbi_valuation.ui.state import _preserved
from tests.test_integration import _full_assessment


def _app(section, assessment=None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(
        str(Path(__file__).resolve().parent.parent / "app.py"),
        default_timeout=120,
    )
    if assessment is not None:
        at.session_state["assessment"] = assessment
    at.session_state["active_section"] = section
    at.run()
    return at


def _click(at, label):
    for b in at.button:
        if b.label == label:
            b.click()
            at.run()
            return True
    for b in at.sidebar.button:
        if b.label == label:
            b.click()
            at.run()
            return True
    return False


class TestPricingPresets:
    """a = _full_assessment(): SDE 186k x 2.5 mid => midpoint 465,000."""
    MID = 465_000

    def test_competitive_preset(self):
        at = _app("pricing", _full_assessment())
        assert not at.exception
        assert _click(at, "Competitive pricing")
        assert not at.exception  # was StreamlitWidgetAlreadyInstantiatedError
        a = at.session_state["assessment"]
        assert a.asking_price == self.MID * 0.9 == 418_500
        assert at.session_state["in_asking"] == 418_500

    def test_market_and_aspirational_presets(self):
        at = _app("pricing", _full_assessment())
        assert _click(at, "Market-aligned pricing")
        assert at.session_state["in_asking"] == self.MID
        assert _click(at, "Aspirational pricing")
        assert at.session_state["in_asking"] == self.MID * 1.2
        assert not at.exception

    def test_manual_slider_after_preset(self):
        at = _app("pricing", _full_assessment())
        assert _click(at, "Competitive pricing")
        at.slider[0].set_value(500_000.0)
        at.run()
        a = at.session_state["assessment"]
        assert a.asking_price == 500_000.0
        assert not at.exception

    def test_timeframe_preserved_across_presets(self):
        at = _app("pricing", _full_assessment())
        at.radio[0].set_value(24)
        at.run()
        assert _click(at, "Aspirational pricing")
        assert at.session_state["in_timeframe"] == 24
        assert at.session_state["assessment"].sale_timeframe_months == 24

    def test_presets_stay_illustrative(self):
        """Presets change only the asking price — never emit probabilities."""
        from sbi_valuation.engine import marketability as mk
        at = _app("pricing", _full_assessment())
        assert _click(at, "Aspirational pricing")
        a = at.session_state["assessment"]
        pt = mk.point_for_price(a.asking_price, self.MID)
        assert "%" not in pt.band and "probability" not in pt.band.lower()


class TestAdjustmentForm:
    def test_add_adjustment_no_widget_error(self):
        at = _app("earnings", _full_assessment())
        n0 = len(at.session_state["assessment"].adjustments)
        for ni in at.number_input:
            if ni.label == "Amount ($)":
                ni.set_value(7_500.0)
        at.run()
        assert _click(at, "Add to register")
        assert not at.exception  # was post-instantiation key deletion
        assert len(at.session_state["assessment"].adjustments) == n0 + 1


class TestWorkspaceActions:
    def test_new_assessment_no_widget_error(self):
        at = _app("profile", _full_assessment())
        assert _click(at, "✚ New")
        assert not at.exception
        assert at.session_state["assessment"].driver_answers == {}

    def test_delete_no_widget_error(self):
        at = _app("profile", _full_assessment())
        assert _click(at, "🗑 Delete")
        assert not at.exception
        assert at.session_state["assessment"].driver_answers == {}


class TestPreservedKeys:
    def test_workspace_keys_preserved(self):
        assert _preserved("in_upload_0")
        assert _preserved("in_upload_n")
        assert _preserved("in_passphrase")
        assert not _preserved("in_q_od_1")
        assert not _preserved("in_asking")
