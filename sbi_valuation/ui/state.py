"""
Session-state glue between Streamlit widgets and the Assessment model.

Conventions:
- ``st.session_state["assessment"]`` holds the authoritative Assessment.
- Widget keys are namespaced ``in_*``; ``seed()`` initializes a widget key
  from the model only when the key doesn't exist, so navigation never
  loses in-progress input. ``pull()`` copies widget values back into the
  model after each section renders.
- Loading/replacing an assessment clears all ``in_*`` keys so widgets
  re-seed from the new model.
- ``results()`` computes the engine bundle fresh each run — calculated
  outputs are never cached on the model, so upstream edits always
  invalidate downstream results.
"""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ..engine.drivers import analyze_drivers
from ..engine.evidence import assess_evidence
from ..engine.normalization import NormalizationResult, reconcile
from ..engine.valuation import run_methods
from ..models.assessment import Assessment, FinancialPeriod

INPUT_PREFIX = "in_"


def get_assessment() -> Assessment:
    a = st.session_state.get("assessment")
    if a is None:
        a = Assessment()
        st.session_state["assessment"] = a
    return a


def set_assessment(a: Assessment) -> None:
    for k in [k for k in st.session_state if str(k).startswith(INPUT_PREFIX)]:
        del st.session_state[k]
    st.session_state["assessment"] = a


def new_assessment() -> Assessment:
    a = Assessment()
    set_assessment(a)
    return a


def seed(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def pull(key: str):
    return st.session_state.get(key)


@dataclass
class Results:
    period: FinancialPeriod | None
    normalization: NormalizationResult | None
    valuations: dict
    evidence: object
    drivers: object
    sde: float | None
    ebitda: float | None


def results() -> Results:
    """Compute the current results bundle from the assessment."""
    a = get_assessment()
    period = a.primary_period()
    norm = reconcile(period, a.adjustments) if period else None
    sde = norm.best_sde if norm else None
    vals = run_methods(a, sde)
    ebitda = vals["ebitda_multiple"].earnings
    ev = assess_evidence(a, norm, vals)
    dr = analyze_drivers(a.driver_answers)
    return Results(period, norm, vals, ev, dr, sde, ebitda)


def clear_session() -> None:
    """Delete the working assessment and all widget state (in-app delete)."""
    for k in list(st.session_state.keys()):
        del st.session_state[k]
