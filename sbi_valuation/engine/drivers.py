"""
Business value-driver assessment.

Six categories of plain-English questions. Answers are qualitative —
"strong" / "partial" / "weak" / "not_sure" / unanswered. "Not sure" is
treated as an information gap, never as a negative.

Driver analysis produces strengths, risks, and improvement opportunities
with educational explanations. It does NOT apply numerical valuation
adjustments — any effect on valuation assumptions must come from the user,
transparently.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# question: (id, text, why_it_matters)
CATEGORIES = [
    {
        "id": "owner_dependency",
        "name": "Owner Dependency",
        "intro": (
            "How much does the business rely on you personally? Buyers pay "
            "more for businesses that keep running when the owner steps away."
        ),
        "questions": [
            ("od_1", "Could the business run normally for 30+ days without you?",
             "Businesses that depend on the owner's daily presence are harder "
             "to sell and usually attract lower offers."),
            ("od_2", "Do customers have relationships with staff other than you?",
             "If customers only know the owner, they may leave after a sale — "
             "a key risk buyers discount for."),
            ("od_3", "Are your key decisions and processes written down?",
             "Documented processes make the business transferable and reduce "
             "the perceived risk of the transition."),
            ("od_4", "Is your industry knowledge or licensing easily handed to a buyer?",
             "Personal licenses, certifications, or relationships that can't "
             "transfer reduce what a buyer is actually acquiring."),
        ],
    },
    {
        "id": "customer_stability",
        "name": "Customer Stability",
        "intro": (
            "Predictable, diversified revenue is one of the strongest value "
            "drivers."
        ),
        "questions": [
            ("cs_1", "No single customer accounts for more than 20% of annual revenue.",
             "Heavy customer concentration is one of the most common reasons "
             "buyers lower offers or walk away."),
            ("cs_2", "Does revenue repeat — contracts, subscriptions, or loyal returning customers?",
             "Recurring revenue is more predictable, and predictability is "
             "what buyers pay for."),
            ("cs_3", "Has revenue been stable or growing over the past few years?",
             "Stable or growing revenue supports higher confidence in future "
             "earnings."),
            ("cs_4", "Would most customers stay if the business changed hands?",
             "Transferability of the customer base directly affects what the "
             "business is worth to a buyer."),
        ],
    },
    {
        "id": "financial_stability",
        "name": "Financial Stability",
        "intro": (
            "Clean, consistent financial records build buyer confidence and "
            "support your asking price."
        ),
        "questions": [
            ("fs_1", "Are your financial records complete and up to date?",
             "Buyers and lenders verify everything — missing or messy books "
             "delay deals and lower trust."),
            ("fs_2", "Are profit margins stable or improving?",
             "Consistent margins suggest durable earnings; volatile margins "
             "raise questions."),
            ("fs_3", "Could the business comfortably cover its debts from cash flow?",
             "Cash flow that covers obligations is fundamental to both value "
             "and a buyer's financing."),
            ("fs_4", "Are personal and business expenses clearly separated?",
             "Mixed expenses make earnings harder to verify and slow due "
             "diligence."),
        ],
    },
    {
        "id": "employees_management",
        "name": "Employees & Management",
        "intro": (
            "A capable team that stays through a transition reduces buyer "
            "risk."
        ),
        "questions": [
            ("em_1", "Is there a manager or key employee who could run daily operations?",
             "A second-in-command materially reduces owner-dependency risk."),
            ("em_2", "Is employee turnover low in key roles?",
             "Losing key people during a sale can damage the business the "
             "buyer thought they were getting."),
            ("em_3", "Are key employees likely to stay after a sale?",
             "Buyers often ask for retention commitments; uncertainty here "
             "reduces value."),
            ("em_4", "Are roles, responsibilities, and pay documented?",
             "Clear structure makes the workforce easier to evaluate and "
             "transition."),
        ],
    },
    {
        "id": "market_position",
        "name": "Market Position",
        "intro": (
            "A defensible position in your market supports pricing power "
            "and durability."
        ),
        "questions": [
            ("mp_1", "Does the business have a clear specialty or advantage over competitors?",
             "Differentiation protects margins and makes the business harder "
             "to replace."),
            ("mp_2", "Is demand in your market stable or growing?",
             "Buyers discount businesses in shrinking markets."),
            ("mp_3", "Would it be hard for a competitor to copy what you do?",
             "Barriers to imitation — reputation, location, expertise — "
             "support value."),
            ("mp_4", "Does the business have a strong local reputation (reviews, referrals)?",
             "Reputation is a real, if intangible, asset that influences "
             "buyer interest."),
        ],
    },
    {
        "id": "operational_transition",
        "name": "Operational & Transition Risk",
        "intro": (
            "Practical risks that affect how smoothly a sale — and the "
            "business itself — could proceed."
        ),
        "questions": [
            ("ot_1", "Are key supplier or vendor relationships stable and transferable?",
             "Businesses dependent on one supplier or informal arrangements "
             "carry transition risk."),
            ("ot_2", "Are leases, licenses, and contracts in writing and assignable?",
             "A lease that can't transfer can stop a sale entirely."),
            ("ot_3", "Is equipment and infrastructure in good working condition?",
             "Deferred maintenance becomes a price negotiation point."),
            ("ot_4", "Is the business free of major pending legal, tax, or regulatory issues?",
             "Unresolved liabilities scare buyers and can kill deals."),
        ],
    },
]

ALL_QUESTIONS = {q[0]: (cat, q) for cat in CATEGORIES for q in cat["questions"]}


@dataclass
class CategoryAnalysis:
    id: str
    name: str
    answered: int = 0
    total: int = 0
    strengths: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    gaps: list = field(default_factory=list)   # "not sure" responses only
    unsure: list = field(default_factory=list)  # qids answered "not_sure"

    @property
    def completion(self) -> float:
        return self.answered / self.total if self.total else 0.0


@dataclass
class DriverAnalysis:
    categories: list = field(default_factory=list)  # list[CategoryAnalysis]

    @property
    def completion(self) -> float:
        tot = sum(c.total for c in self.categories)
        ans = sum(c.answered for c in self.categories)
        return ans / tot if tot else 0.0

    @property
    def all_strengths(self) -> list:
        return [s for c in self.categories for s in c.strengths]

    @property
    def all_risks(self) -> list:
        return [r for c in self.categories for r in c.risks]

    @property
    def all_gaps(self) -> list:
        return [g for c in self.categories for g in c.gaps]


def analyze_drivers(answers: dict) -> DriverAnalysis:
    """Produce a qualitative analysis from owner-reported answers."""
    out = DriverAnalysis()
    for cat in CATEGORIES:
        ca = CategoryAnalysis(id=cat["id"], name=cat["name"], total=len(cat["questions"]))
        for qid, text, why in cat["questions"]:
            ans = answers.get(qid)
            if ans is None:
                # Genuinely unanswered — counts toward incompletion only,
                # never becomes a finding or recommendation.
                continue
            ca.answered += 1
            if ans == "strong":
                ca.strengths.append(text)
            elif ans == "weak":
                ca.risks.append((text, why))
            elif ans == "not_sure":
                ca.unsure.append(qid)
                ca.gaps.append(f"Not sure: {text}")
            # "partial" is neutral — neither strength nor red flag, but a
            # mild opportunity; surfaced via improvement planning instead.
        out.categories.append(ca)
    return out


def completion_pct(answers: dict) -> float:
    return analyze_drivers(answers).completion
