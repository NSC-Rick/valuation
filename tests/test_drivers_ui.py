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


def _category_counts(app):
    """Per-category 'n/4 answered' caption counts, in category order."""
    counts = []
    for cap in app.caption:
        m = re.match(r"^(\d+)/4 answered", cap.value)
        if m:
            counts.append(int(m.group(1)))
    return counts


class TestCompletionCounter:
    """Bug: counters showed '3/4' with all four questions answered — the
    analysis was computed before radio write-backs, so counters lagged a
    rerun behind. Answers now sync into the model at the top of
    results(), so counters update in the same run as the selection."""

    # radios are in document order: indices 0-3 = owner_dependency,
    # 4-7 = customer_stability, 8-11 = financial_stability, etc.

    @pytest.mark.parametrize("answer", ["strong", "partial", "weak", "not_sure"])
    def test_every_answer_type_counts(self, app, answer):
        app.radio[0].set_value(answer)
        app.run()
        a = app.session_state["assessment"]
        assert a.driver_answers.get("od_1") == answer
        assert _category_counts(app)[0] == 1

    def test_all_four_count_immediately(self, app):
        """Financial Stability must show 4/4 in the SAME run the last
        question is answered — no extra rerun needed."""
        for i in range(4):
            app.radio[8 + i].set_value("strong")
            app.run()
        counts = _category_counts(app)
        assert counts[2] == 4  # financial_stability

    def test_changing_answer_keeps_count(self, app):
        app.radio[0].set_value("strong")
        app.run()
        app.radio[0].set_value("weak")
        app.run()
        assert _category_counts(app)[0] == 1
        app.radio[0].set_value("not_sure")
        app.run()
        assert _category_counts(app)[0] == 1

    def test_unselected_initially(self, app):
        """Radios start unselected (index=None); unanswered = incomplete."""
        assert app.radio[0].value is None
        assert _category_counts(app)[0] == 0

    def test_cleared_selection_decrements(self, app):
        """Clearing the widget's selection returns the question to
        unanswered/incomplete."""
        app.radio[0].set_value("strong")
        app.run()
        assert _category_counts(app)[0] == 1
        app.session_state["in_q_od_1"] = None
        app.run()
        a = app.session_state["assessment"]
        assert "od_1" not in a.driver_answers
        assert _category_counts(app)[0] == 0

    def test_no_placeholder_option(self, app):
        """Only the four valid response options are offered."""
        for radio in app.radio:
            assert "—" not in radio.options
            assert len(radio.options) == 4

    def test_progress_matches_category_counts(self, app):
        for i in range(4):
            app.radio[8 + i].set_value("partial")
            app.run()
        app.radio[0].set_value("strong")
        app.run()
        counts = _category_counts(app)
        total = sum(counts)
        assert total == 5
        a = app.session_state["assessment"]
        assert len(a.driver_answers) == total

    def test_export_preserves_all_responses(self, app):
        answers = {"strong": 0, "partial": 1, "weak": 2, "not_sure": 3}
        for ans, i in answers.items():
            app.radio[8 + i].set_value(ans)
            app.run()
        a = app.session_state["assessment"]
        from sbi_valuation.storage.portfolio import (
            export_assessment,
            import_assessment,
        )
        a2 = import_assessment(export_assessment(a, "pw"), "pw")
        assert a2.driver_answers == a.driver_answers
        assert len(a2.driver_answers) == 4
