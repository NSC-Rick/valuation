"""AI-assisted SDE multiple research tests — all mocked, no network."""
import sys, warnings
from pathlib import Path
import pytest

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sbi_valuation.engine.research import (
    AIResearch, build_research_context, validate_result,
    RESULT_SUFFICIENT, RESULT_INSUFFICIENT, RESULT_ERROR,
)
from sbi_valuation.integrations.openai_research import research_sde_multiples
from tests.test_integration import _full_assessment, _results


GOOD = {"status": "supported", "low": 2.0, "mid": 2.5, "high": 3.0,
        "explanation": "Comparable service businesses transact near this range.",
        "range_rationale": "Stable revenue, moderate owner dependency.",
        "evidence_quality": "moderate",
        "sources": [{"title": "Brokerage market report 2024",
                     "url": "https://example.com/report", "date": "2024"}],
        "limitations": ["Few recent transactions in this market."]}


class TestContext:
    def test_anonymized(self):
        a = _full_assessment()
        ctx = build_research_context(a, 186_000)
        assert ctx["industry"] == "Professional services"
        assert "Green Mountain" not in str(ctx) and "Bakery" not in str(ctx)
        assert "name" not in str(ctx.get("risk_profile", {})).lower()
        assert ctx["normalized_SDE"].startswith("$175,000")

    def test_risk_profile_included(self):
        a = _full_assessment()
        ctx = build_research_context(a, 186_000)
        assert ctx["risk_profile"]["Owner Dependency"]["answered"] == 4


class TestValidation:
    def test_good_response(self):
        r = validate_result(GOOD)
        assert r.status == RESULT_SUFFICIENT
        assert (r.low, r.mid, r.high) == (2.0, 2.5, 3.0)
        assert r.sources[0].title == "Brokerage market report 2024"

    @pytest.mark.parametrize("vals", [(0, 2, 3), (3, 2, 1), (2, 3, 1), (-1, 2, 3)])
    def test_bad_ordering_rejected(self, vals):
        d = dict(GOOD); d["low"], d["mid"], d["high"] = vals
        assert validate_result(d).status == RESULT_ERROR

    def test_missing_numbers(self):
        d = dict(GOOD); del d["mid"]
        assert validate_result(d).status == RESULT_ERROR

    def test_malformed(self):
        assert validate_result("not a dict").status == RESULT_ERROR
        assert validate_result(None).status == RESULT_ERROR

    def test_insufficient_evidence(self):
        r = validate_result({"status": "insufficient_evidence",
                             "explanation": "No comparables found."})
        assert r.status == RESULT_INSUFFICIENT and "No comparables" in r.explanation

    def test_insufficient_with_numbers_is_stripped(self):
        """CONTRADICTION: 'insufficient' + a range → numbers discarded,
        never surfaced as a suggestion."""
        d = dict(GOOD, status="insufficient_evidence",
                 explanation="No comparables.")
        r = validate_result(d)
        assert r.status == RESULT_INSUFFICIENT
        assert r.low is None and r.mid is None and r.high is None
        assert any("discarded" in x for x in r.limitations)

    def test_supported_without_url_downgrades(self):
        """'Supported' claims need at least one verifiable URL."""
        d = dict(GOOD)
        d["sources"] = [{"title": "A report with no link"}]
        r = validate_result(d)
        assert r.status == "limited_benchmark"
        assert not r.appliable
        assert (r.low, r.mid, r.high) == (2.0, 2.5, 3.0)

    def test_supported_requires_url_and_is_appliable(self):
        r = validate_result(GOOD)
        assert r.status == "supported" and r.appliable

    def test_legacy_sufficient_maps_to_supported(self):
        d = dict(GOOD, status="sufficient")
        r = validate_result(d)
        assert r.status == "supported" and r.appliable

    def test_limited_benchmark_not_appliable(self):
        d = dict(GOOD, status="limited_benchmark")
        d["sources"] = [{"title": "commentary only",
                         "evidence_type": "commentary", "metric": "sde"}]
        r = validate_result(d)
        assert r.status == "limited_benchmark" and not r.appliable

    def test_source_classification_fields(self):
        d = dict(GOOD)
        d["sources"] = [{"title": "T", "url": "https://x", "metric": "ebitda",
                         "evidence_type": "asking_price",
                         "comparability": "larger businesses"}]
        r = validate_result(d)
        assert r.sources[0].metric == "ebitda"
        assert r.sources[0].evidence_type == "asking_price"
        assert "larger" in r.sources[0].comparability

    def test_untitled_sources_dropped(self):
        d = dict(GOOD); d["sources"] = [{"url": "http://x"}, {"title": "ok"}]
        r = validate_result(d)
        assert len(r.sources) == 1 and r.sources[0].title == "ok"


class TestIntegration:
    def test_success_path(self):
        calls = []
        def fake(prompt, key, model):
            calls.append(prompt); return GOOD
        r = research_sde_multiples({"industry": "X"}, call_fn=fake, api_key="k")
        assert r.status == RESULT_SUFFICIENT and len(calls) == 1

    def test_api_error_graceful(self):
        def boom(p, k, m): raise ConnectionError("down")
        r = research_sde_multiples({}, call_fn=boom, api_key="k")
        assert r.status == RESULT_ERROR and "unavailable" in r.error

    def test_no_key_no_call(self):
        def boom(p, k, m): raise AssertionError("must not call")
        r = research_sde_multiples({}, call_fn=boom, api_key="")
        assert r.status == RESULT_ERROR and "OPENAI_API_KEY" in r.error

    def test_no_call_without_action(self):
        """Rendering with ai_suggested kind must not invoke the API —
        calls only happen inside button callbacks."""
        from streamlit.testing.v1 import AppTest
        a = _full_assessment()
        a.valuation.sde_multiple.kind = "ai_suggested"
        at = AppTest.from_file(
            str(Path(__file__).resolve().parent.parent / "app.py"),
            default_timeout=120)
        at.session_state["assessment"] = a
        at.session_state["active_section"] = "results"
        at.run()
        assert not at.exception
        assert "ai_research" not in a.valuation.__dict__ or \
            not a.valuation.ai_research.get("status")


class TestApplyFlow:
    def test_apply_then_edit_marks_modified(self):
        a = _full_assessment()
        res = AIResearch(status=RESULT_SUFFICIENT, low=2.0, mid=2.5, high=3.0,
                         applied=True)
        a.valuation.ai_research = vars(res)
        m = a.valuation.sde_multiple
        m.low, m.mid, m.high = 2.0, 2.5, 3.0
        assert (m.low, m.mid, m.high) == (res.low, res.mid, res.high)
        m.mid = 2.75  # user edit
        assert (m.low, m.mid, m.high) != (res.low, res.mid, res.high)

    def test_export_import_research(self):
        from sbi_valuation.storage.portfolio import export_assessment, import_assessment
        a = _full_assessment()
        a.valuation.sde_multiple.kind = "ai_suggested"
        a.valuation.ai_research = vars(AIResearch(
            status=RESULT_SUFFICIENT, low=2.0, mid=2.5, high=3.0,
            applied=True, applied_at="2026-11-07"))
        a2 = import_assessment(export_assessment(a, "pw"), "pw")
        assert a2.valuation.ai_research["low"] == 2.0
        assert a2.valuation.ai_research["applied"] is True
        assert a2.valuation.sde_multiple.kind == "ai_suggested"

    def test_ai_suggested_not_supported(self):
        r = _results(_full_assessment())
        ind = r.valuations["sde_multiple"]
        assert ind.illustrative  # ai_suggested treated as non-supported

    def test_no_secrets_in_code(self):
        src = Path("sbi_valuation").rglob("*.py")
        for f in src:
            assert "sk-" not in f.read_text(encoding="utf-8")
