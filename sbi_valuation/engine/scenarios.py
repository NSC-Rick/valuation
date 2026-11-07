"""
Value Explorer scenario engine.

Scenarios are strictly hypothetical: they carry optional overrides of
earnings and multiple that are applied ON TOP of the baseline at read
time. They never write back to the assessment's financial inputs or
official valuation assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models.assessment import Scenario


@dataclass
class ScenarioResult:
    scenario: Scenario
    earnings: float
    multiple: float
    value: float
    baseline_value: float
    delta_abs: float
    delta_pct: Optional[float]


def baseline_value(sde: Optional[float], mid_multiple: float) -> Optional[float]:
    if sde is None or sde < 0:
        return None
    return sde * mid_multiple


def evaluate_scenario(
    scenario: Scenario,
    baseline_sde: Optional[float],
    baseline_multiple: float,
) -> Optional[ScenarioResult]:
    """Evaluate one scenario against the baseline.

    ``earnings=None`` inherits the baseline SDE; ``multiple=None``
    inherits the baseline mid multiple.
    """
    earnings = scenario.earnings if scenario.earnings is not None else baseline_sde
    multiple = scenario.multiple if scenario.multiple is not None else baseline_multiple
    if earnings is None or earnings < 0 or multiple is None:
        return None
    value = earnings * multiple
    base = (baseline_sde or 0.0) * baseline_multiple
    delta = value - base
    pct = (delta / base * 100.0) if base else None
    return ScenarioResult(
        scenario=scenario,
        earnings=earnings,
        multiple=multiple,
        value=value,
        baseline_value=base,
        delta_abs=delta,
        delta_pct=pct,
    )


def preset_scenarios() -> list:
    """Factory presets. Returned as templates — callers instantiate."""
    return [
        Scenario(
            name="Current Business",
            description="Baseline — no changes to earnings or assumptions.",
            created_from="preset",
        ),
        Scenario(
            name="Improve Earnings",
            description="Hypothetical: earnings improve (e.g. +20% SDE).",
            created_from="preset",
        ),
        Scenario(
            name="Reduce Business Risk",
            description="Hypothetical: stronger value-driver profile supports "
            "a higher multiple assumption.",
            created_from="preset",
        ),
    ]
