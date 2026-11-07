"""
Business value improvement plan generator.

Converts assessment findings (driver risks, information gaps, evidence
weaknesses) into prioritized, plain-English recommendations. Each item is
a suggestion grounded in the owner's own answers — never a fabricated
promise of increased value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models.assessment import ActionItem
from .drivers import CATEGORIES, analyze_drivers

# Recommended action per question id (keyed to the question bank).
_ACTIONS = {
    "od_1": ("Document a delegation plan and train a key employee to cover daily operations.",
             "Reduce owner dependency so the business runs without you.", "high", "3–6 months"),
    "od_2": ("Introduce key customers to other staff and transition relationships gradually.",
             "Spread customer relationships beyond the owner.", "high", "3–9 months"),
    "od_3": ("Write down core processes — an operations manual covering critical tasks.",
             "Documented processes make the business transferable.", "medium", "2–4 months"),
    "od_4": ("Identify which licenses/knowledge transfer and plan staff credentialing early.",
             "Ensure a buyer can legally and practically operate the business.", "medium", "6–12 months"),
    "cs_1": ("Diversify the customer base or secure written contracts with the largest customer.",
             "Reduce customer concentration — a top buyer concern.", "high", "6–12 months"),
    "cs_2": ("Build recurring revenue: service agreements, retainers, or loyalty programs.",
             "Predictable revenue supports stronger valuations.", "medium", "6–12 months"),
    "cs_3": ("Diagnose revenue volatility causes and document a stabilization plan.",
             "Stable trends make earnings easier to underwrite.", "medium", "3–9 months"),
    "cs_4": ("Plan customer communication and retention incentives for an ownership transition.",
             "Customer continuity protects post-sale earnings.", "medium", "Before sale"),
    "fs_1": ("Bring books current and reconcile monthly; consider accountant review.",
             "Verifiable records are the foundation of any credible valuation.", "high", "1–3 months"),
    "fs_2": ("Analyze margin swings; stabilize pricing and cost structure.",
             "Consistent margins increase buyer confidence in earnings.", "medium", "3–6 months"),
    "fs_3": ("Review debt obligations against cash flow; restructure if coverage is tight.",
             "Cash-flow coverage affects both value and buyer financing.", "medium", "1–6 months"),
    "fs_4": ("Separate personal and business expenses going forward.",
             "Clean separation makes normalized earnings defensible.", "high", "Immediate–3 months"),
    "em_1": ("Develop or hire a manager capable of running daily operations.",
             "A second-in-command materially lowers transition risk.", "high", "6–12 months"),
    "em_2": ("Address turnover causes; document retention plans for key roles.",
             "Workforce stability reassures buyers.", "medium", "3–9 months"),
    "em_3": ("Discuss transition plans with key employees; consider stay incentives.",
             "Key-person retention is often a deal condition.", "medium", "Before sale"),
    "em_4": ("Document roles, responsibilities, and compensation structure.",
             "Clarity helps buyers evaluate the team they're acquiring.", "low", "1–3 months"),
    "mp_1": ("Sharpen and communicate what differentiates the business.",
             "Differentiation supports pricing power and buyer interest.", "medium", "3–6 months"),
    "mp_2": ("Document market demand trends; diversify into growing segments if declining.",
             "Buyers pay for durable demand.", "medium", "6–12 months"),
    "mp_3": ("Strengthen barriers: exclusive arrangements, reputation, proprietary know-how.",
             "Harder-to-copy businesses hold value better.", "low", "Ongoing"),
    "mp_4": ("Invest in reviews, referrals, and local reputation — and document it.",
             "Reputation is intangible but real value.", "low", "Ongoing"),
    "ot_1": ("Put key supplier relationships in writing; qualify backup suppliers.",
             "Transferable supply arrangements reduce transition risk.", "medium", "1–6 months"),
    "ot_2": ("Review leases and contracts for assignability; fix gaps before going to market.",
             "Non-assignable agreements can stop a sale.", "high", "1–3 months"),
    "ot_3": ("Address deferred maintenance and document equipment condition.",
             "Removes a common price-negotiation lever.", "low", "Before sale"),
    "ot_4": ("Resolve pending legal, tax, or regulatory items before marketing the business.",
             "Unresolved liabilities scare buyers and stall deals.", "high", "Immediate"),
}

_QTEXT = {q[0]: q[1] for cat in CATEGORIES for q in cat["questions"]}
_QCAT = {q[0]: cat["name"] for cat in CATEGORIES for q in cat["questions"]}
_QWHY = {q[0]: q[2] for cat in CATEGORIES for q in cat["questions"]}


@dataclass
class PlanResult:
    items: list = field(default_factory=list)  # list[ActionItem]
    generated: int = 0
    kept_manual: int = 0


def generate_plan(assessment, evidence=None) -> PlanResult:
    """Generate/refresh recommendations from current findings.

    Preserves manual items and the status of existing generated items
    (matched by question id stored in ``source``), so refreshing after
    reassessment doesn't wipe the user's progress tracking.
    """
    analysis = analyze_drivers(assessment.driver_answers)
    existing_by_src = {
        a.source: a for a in assessment.action_items if a.source not in ("assessment", "manual")
    }
    items: list = []
    manual = [a for a in assessment.action_items if a.source == "manual"]
    generated = 0

    for cat in analysis.categories:
        for text, why in cat.risks:
            # find the question id for this risk text
            qid = next((k for k, v in _QTEXT.items() if v == text), None)
            if qid is None or qid not in _ACTIONS:
                continue
            action, issue, prio, tf = _ACTIONS[qid]
            prev = existing_by_src.get(qid)
            items.append(ActionItem(
                id=prev.id if prev else ActionItem().id,
                category=_QCAT.get(qid, cat.name),
                issue=issue,
                why=why,
                action=action,
                priority=prev.priority if prev else prio,
                timeframe=prev.timeframe if prev else tf,
                status=prev.status if prev else "not_started",
                source=qid,
            ))
            generated += 1

    for cat in analysis.categories:
        for gap in cat.gaps:
            text = gap.split(": ", 1)[-1]
            qid = next((k for k, v in _QTEXT.items() if v == text), None)
            if qid is None:
                continue
            prev = existing_by_src.get(f"gap_{qid}")
            items.append(ActionItem(
                id=prev.id if prev else ActionItem().id,
                category=_QCAT.get(qid, cat.name),
                issue="Information gap to resolve",
                why=_QWHY.get(qid, "Unknowns become buyer concerns during due diligence."),
                action=f"Investigate and document an answer to: {text}",
                priority=prev.priority if prev else "low",
                timeframe=prev.timeframe if prev else "1–3 months",
                status=prev.status if prev else "not_started",
                source=f"gap_{qid}",
            ))
            generated += 1

    items.extend(manual)
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda a: (order.get(a.priority, 3), a.category))
    return PlanResult(items=items, generated=generated, kept_manual=len(manual))
