"""AI-assisted SDE multiple research — inputs, validation, results.

Pure python, no OpenAI/Streamlit imports. The anonymized request is built
from the assessment; the response is strictly validated before anything
reaches the valuation engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .drivers import CATEGORIES

RESULT_SUFFICIENT = "supported"
RESULT_LIMITED = "limited_benchmark"
RESULT_INSUFFICIENT = "insufficient_evidence"
RESULT_ERROR = "error"


def _band(v: Optional[float], step: float = 25000.0) -> str:
    if v is None:
        return "not provided"
    lo = int(v // step * step)
    return f"${lo:,.0f}–${lo + step:,.0f}"


def build_research_context(assessment, sde: Optional[float]) -> dict:
    """Anonymized research inputs — no business name, owner info,
    customers, or document contents."""
    p = assessment.profile
    period = assessment.primary_period()
    ctx = {
        "industry": p.industry or "not specified",
        "specialization": p.specialization or "",
        "location": ", ".join(x for x in [p.city, p.state] if x) or "not specified",
        "years_in_business": p.years_operating,
        "annual_revenue": _band(period.revenue if period else None),
        "normalized_SDE": _band(sde),
        "employees": p.employee_count,
        "owner_involvement": p.owner_involvement or "not specified",
        "legal_structure": p.legal_structure or "not specified",
    }
    # Qualitative risk profile from driver answers (counts only)
    from .drivers import analyze_drivers
    dr = analyze_drivers(assessment.driver_answers)
    ctx["risk_profile"] = {
        c.name: {"strengths": len(c.strengths), "risks": len(c.risks),
                 "unsure": len(c.unsure), "answered": c.answered}
        for c in dr.categories
    }
    return ctx


@dataclass
class ResearchSource:
    title: str = ""
    url: str = ""
    date: str = ""
    metric: str = ""           # "sde" | "ebitda" | "revenue" | "unknown"
    evidence_type: str = ""    # "transaction" | "asking_price" | "commentary" | "unknown"
    comparability: str = ""    # why comparable or not


@dataclass
class AIResearch:
    """Stored on the assessment — survives save/export/import."""
    status: str = ""                 # sufficient | insufficient_evidence | error
    requested_at: str = ""
    context_summary: str = ""
    low: Optional[float] = None
    mid: Optional[float] = None
    high: Optional[float] = None
    explanation: str = ""
    range_rationale: str = ""
    sources: list = field(default_factory=list)  # list[ResearchSource]
    evidence_quality: str = ""
    limitations: list = field(default_factory=list)
    appliable: bool = False    # only True for supported results
    applied: bool = False
    applied_at: str = ""
    user_modified: bool = False
    error: str = ""


def validate_result(data: dict) -> AIResearch:
    """Validate a raw AI response dict → AIResearch. Never raises on
    malformed input — returns an insufficient/error result instead."""
    res = AIResearch(requested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if not isinstance(data, dict):
        res.status = RESULT_ERROR
        res.error = "Malformed research response."
        return res
    status = data.get("status")
    if status == "sufficient":  # legacy label
        status = RESULT_SUFFICIENT
    if status not in (RESULT_SUFFICIENT, RESULT_LIMITED, RESULT_INSUFFICIENT):
        res.status = RESULT_INSUFFICIENT
        res.explanation = str(data.get("explanation") or
                              "The research did not find enough comparable "
                              "evidence to suggest a range.")
        res.limitations = [str(x) for x in data.get("limitations") or []][:8]
        return res

    res.status = status
    res.sources = [
        ResearchSource(
            title=str(s["title"])[:200],
            url=str(s.get("url") or "")[:500],
            date=str(s.get("date") or "")[:40],
            metric=str(s.get("metric") or "unknown"),
            evidence_type=str(s.get("evidence_type") or "unknown"),
            comparability=str(s.get("comparability") or "")[:500],
        )
        for s in data.get("sources") or []
        if isinstance(s, dict) and s.get("title")
    ][:8]
    res.limitations = [str(x) for x in data.get("limitations") or []][:8]
    res.explanation = str(data.get("explanation") or "")
    res.range_rationale = str(data.get("range_rationale") or "")
    res.evidence_quality = str(data.get("evidence_quality") or "")

    nums = None
    try:
        if data.get("low") is not None:
            nums = (float(data["low"]), float(data["mid"]), float(data["high"]))
    except (KeyError, TypeError, ValueError):
        nums = None

    if status == RESULT_INSUFFICIENT:
        # Contradiction guard: numbers offered under an insufficient finding
        # are stripped — never surfaced as a suggested range.
        if nums is not None:
            res.limitations.append(
                "A numerical range was returned despite insufficient "
                "evidence — it was discarded.")
        res.explanation = res.explanation or (
            "The research did not find enough comparable evidence to "
            "suggest a range.")
        return res

    if nums is None or not (0 < nums[0] <= nums[1] <= nums[2]):
        res.status = RESULT_ERROR
        res.error = ("Research returned an invalid or missing numerical "
                     "range (must be positive, low ≤ mid ≤ high).")
        return res

    if status == RESULT_SUFFICIENT:
        # "Supported" demands at least one source with a verifiable URL.
        if not any(s.url.startswith("http") for s in res.sources):
            res.status = RESULT_LIMITED
            res.limitations.insert(
                0, "No verifiable source URL was provided — downgraded to "
                   "limited-evidence benchmark.")
            res.low, res.mid, res.high = nums
            return res
        res.low, res.mid, res.high = nums
        res.appliable = True
        return res

    # limited_benchmark: numbers surfaced as context only, never appliable.
    res.low, res.mid, res.high = nums
    return res
