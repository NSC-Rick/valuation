"""Regression tests: Section 04 expander stability + question orientation.

Bug: expandable categories collapsed when answering questions, caused by
(a) a dynamic `expanded` argument that flipped after the first answer and
(b) answer counts embedded in expander labels (changing labels recreate
the widget). These tests lock the invariants Streamlit requires for
expander-state preservation: static labels, constant `expanded` arg,
stable radio keys, and persistent answers.
"""
import re
import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sbi_valuation.engine.drivers import CATEGORIES, analyze_drivers
from sbi_valuation.ui.sections import s04_drivers  # noqa: F401  (import check)

ALL_QIDS = [q[0] for c in CATEGORIES for q in c["questions"]]
QTEXT = {q[0]: q[1] for c in CATEGORIES for q in c["questions"]}


class TestQuestionOrientation:
    def test_cs1_revised_wording(self):
        assert QTEXT["cs_1"] == (
            "No single customer accounts for more than 20% of annual revenue."
        )
        assert "Is any single customer more than 20%" not in QTEXT["cs_1"]

    def test_strong_always_favorable(self):
        """'Strong / Yes' must classify as a strength for EVERY question —
        never a risk. Locks orientation consistency across all 24."""
        for qid in ALL_QIDS:
            analysis = analyze_drivers({qid: "strong"})
            cat = next(c for c in analysis.categories if c.answered == 1)
            risk_texts = [t for t, _w in cat.risks]
            assert QTEXT[qid] in cat.strengths, f"{qid} not a strength"
            assert QTEXT[qid] not in risk_texts, f"{qid} miscast as risk"

    def test_weak_always_unfavorable(self):
        for qid in ALL_QIDS:
            analysis = analyze_drivers({qid: "weak"})
            cat = next(c for c in analysis.categories if c.answered == 1)
            risk_texts = [t for t, _w in cat.risks]
            assert QTEXT[qid] in risk_texts, f"{qid} not a risk"
            assert QTEXT[qid] not in cat.strengths

    def test_six_category_structure_unchanged(self):
        assert [c["id"] for c in CATEGORIES] == [
            "owner_dependency", "customer_stability", "financial_stability",
            "employees_management", "market_position", "operational_transition",
        ]
        assert len(ALL_QIDS) == 24


@pytest.fixture()
def app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(
        str(Path(__file__).resolve().parent.parent / "app.py"),
        default_timeout=120,
    )
    at.session_state["active_section"] = "drivers"
    at.run()
    return at


def _category_expanders(at):
    return [e for e in at.expander if re.match(r"^\d\. ", e.label)]


class TestExpanderStability:
    def test_labels_static_across_answers(self, app):
        """Category expander labels must not change when answers change."""
        before = [e.label for e in _category_expanders(app)]
        assert len(before) == 6
        app.radio[0].set_value("strong")
        app.run()
        after = [e.label for e in _category_expanders(app)]
        assert after == before

    def test_expanded_args_constant(self, app):
        """The seeded `expanded` session values must not flip on answer."""
        keys = [k for k in app.session_state if str(k).startswith("in_exp_")]
        assert len(keys) == 6
        before = {k: app.session_state[k] for k in keys}
        app.radio[0].set_value("weak")
        app.run()
        app.radio[1].set_value("strong")
        app.run()
        assert {k: app.session_state[k] for k in keys} == before

    def test_answers_persist_across_reruns(self, app):
        app.radio[0].set_value("strong")
        app.run()
        app.radio[1].set_value("not_sure")
        app.run()
        a = app.session_state["assessment"]
        assert a.driver_answers.get("od_1") == "strong"
        assert a.driver_answers.get("od_2") == "not_sure"

    def test_all_six_categories_render(self, app):
        labels = [e.label for e in _category_expanders(app)]
        expected = [f"{i+1}. {c['name']}" for i, c in enumerate(CATEGORIES)]
        assert labels == expected

    def test_first_category_initially_expanded(self, app):
        """Only the first (unanswered) category starts expanded."""
        assert app.session_state["in_exp_owner_dependency"] is True
        for c in CATEGORIES[1:]:
            assert app.session_state[f"in_exp_{c['id']}"] is False
