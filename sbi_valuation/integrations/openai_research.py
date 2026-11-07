"""Server-side OpenAI research integration (spec V1.1 §4).

- API key comes ONLY from env var ``OPENAI_API_KEY`` — never logged,
  never sent to the browser, never committed.
- One call per explicit user action; no automatic retries on reruns.
- Output is parsed strictly and validated by engine.research.
- ``call_fn`` is injectable so tests never touch the network.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from ..engine.research import (
    RESULT_ERROR,
    AIResearch,
    validate_result,
)

ENV_KEY = "OPENAI_API_KEY"
ENV_MODEL = "OPENAI_MODEL"
DEFAULT_MODEL = "gpt-4.1-mini"
TIMEOUT_SECONDS = 60

_SYSTEM = """You are a cautious small-business valuation research assistant.
Research what a reasonable SDE (Seller's Discretionary Earnings) valuation
multiple range might be for the business described. SDE = pre-tax profit
plus one working owner's compensation plus discretionary/nonrecurring
add-backs. NEVER confuse SDE multiples with EBITDA, revenue, or other
multiples, and never convert bases.

Prioritize: (1) completed transactions with known SDE multiples,
(2) credible published transaction databases / brokerage research,
(3) industry-specific valuation studies, (4) broader benchmarks only if
directly comparable evidence is unavailable. Expand geography
progressively: state-level comparables first, then regional, then
national when local data is thin. Evaluate comparability on industry,
size, geography, period, owner involvement, and risk — and say WHY each
source is or isn't comparable.

Classify your evidence honestly:
- "supported": a numerical range backed by at least one source with a
  REAL verifiable URL (transaction data or identifiable methodology).
- "limited_benchmark": only directional industry context found —
  numbers may be suggested as context but are NOT verified.
- "insufficient_evidence": no usable comparables — DO NOT include
  low/mid/high numbers at all.

Do NOT fabricate sources, URLs, transactions, dates, or ranges. The
business is anonymized — never guess or name the business or its owner.
For each
source state: the valuation metric used (sde/ebitda/revenue/unknown),
the evidence type (transaction = completed sale data; asking_price =
broker listing ask; commentary = general industry discussion), and a
one-line comparability note.

Respond with ONLY a JSON object:
{"status": "supported" | "limited_benchmark" | "insufficient_evidence",
 "low": <number|null>, "mid": <number|null>, "high": <number|null>,
 "explanation": "...", "range_rationale": "...",
 "evidence_quality": "limited|moderate|strong",
 "sources": [{"title": "...", "url": "...", "date": "...",
              "metric": "sde|ebitda|revenue|unknown",
              "evidence_type": "transaction|asking_price|commentary|unknown",
              "comparability": "..."}],
 "limitations": ["..."]}
Numbers are SDE multiples of annual SDE (e.g. 2.5). Never include numbers
under "insufficient_evidence"."""


def _prompt(ctx: dict) -> str:
    risks = "; ".join(
        f"{k}: {v['strengths']} strengths/{v['risks']} risks" if v["answered"]
        else f"{k}: not assessed"
        for k, v in ctx.get("risk_profile", {}).items()
    )
    return (
        "Research a suggested SDE multiple range for this business "
        "(anonymized):\n"
        f"- Industry: {ctx.get('industry')}\n"
        f"- Specialization: {ctx.get('specialization')}\n"
        f"- Location: {ctx.get('location')}\n"
        f"- Years in business: {ctx.get('years_in_business')}\n"
        f"- Annual revenue: {ctx.get('annual_revenue')}\n"
        f"- Normalized SDE: {ctx.get('normalized_SDE')}\n"
        f"- Employees: {ctx.get('employees')}\n"
        f"- Owner involvement: {ctx.get('owner_involvement')}\n"
        f"- Legal structure: {ctx.get('legal_structure')}\n"
        f"- Risk profile: {risks}\n"
        "Return only the JSON object described."
    )


def _default_call(prompt: str, api_key: str, model: str) -> dict:
    """Real OpenAI call — Responses API with web search tool."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0)
    resp = client.responses.create(
        model=model,
        instructions=_SYSTEM,
        input=prompt,
        tools=[{"type": "web_search_preview"}],
    )
    text = getattr(resp, "output_text", "") or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in response")
    return json.loads(m.group(0))


def research_sde_multiples(
    ctx: dict,
    call_fn=None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> AIResearch:
    """Run one research request; always returns an AIResearch (never
    raises — errors become status='error' results)."""
    key = api_key if api_key is not None else os.environ.get(ENV_KEY, "")
    if not key:
        res = AIResearch()
        res.status = RESULT_ERROR
        res.error = ("AI research isn't configured on this deployment "
                     f"(missing {ENV_KEY}).")
        return res
    call = call_fn or _default_call
    try:
        raw = call(_prompt(ctx), key, model or os.environ.get(ENV_MODEL, DEFAULT_MODEL))
    except Exception as e:  # noqa: BLE001 — any provider/network error
        res = AIResearch()
        res.status = RESULT_ERROR
        res.error = f"Research service unavailable: {type(e).__name__}"
        return res
    res = validate_result(raw)
    res.context_summary = (
        f"{ctx.get('industry')} · {ctx.get('location')} · "
        f"revenue {ctx.get('annual_revenue')} · SDE {ctx.get('normalized_SDE')}"
    )
    return res
