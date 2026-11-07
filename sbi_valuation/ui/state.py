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

from ..engine.drivers import CATEGORIES, analyze_drivers
from ..engine.evidence import assess_evidence
from ..engine.normalization import NormalizationResult, reconcile
from ..engine.valuation import run_methods
from ..models.assessment import DRIVER_ANSWERS, Assessment, FinancialPeriod

INPUT_PREFIX = "in_"


def get_assessment() -> Assessment:
    a = st.session_state.get("assessment")
    if a is None:
        a = Assessment()
        st.session_state["assessment"] = a
    return a


# Sidebar workspace widget keys that must never be cleared — they are
# instantiated before any save/resume/new/delete action runs, so deleting
# them raises StreamlitWidgetAlreadyInstantiatedError (file-uploader keys
# also can't be programmatically modified at all).
_PRESERVE_PREFIXES = ("in_upload", "in_passphrase")


def _preserved(key) -> bool:
    return str(key).startswith(_PRESERVE_PREFIXES)


def set_assessment(a: Assessment) -> None:
    for k in [k for k in st.session_state
              if str(k).startswith(INPUT_PREFIX) and not _preserved(k)]:
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


def record_driver_answer(qid: str) -> None:
    """on_change callback: write one radio selection straight into the
    assessment model — the authoritative write, at the exact moment of
    selection, independent of widget lifetime or sync timing."""
    a = get_assessment()
    val = st.session_state.get(f"in_q_{qid}")
    if val in DRIVER_ANSWERS:
        a.driver_answers[qid] = val
        a.touch()


def sync_driver_answers(a) -> None:
    """Reconcile driver widget keys with the model — NON-DESTRUCTIVE.

    - Missing/GC'd widget keys are re-seeded from the model (restore).
    - A valid session selection is copied into the model (belt-and-
      suspenders alongside the on_change write).
    - An absent/None/invalid widget value NEVER removes a stored answer:
      the model is authoritative and radios offer no un-answer path, so
      a missing widget value means "not rendered yet", not "unanswered" —
      instead the widget value is healed from the model.
    """
    for cat in CATEGORIES:
        for qid, _text, _why in cat["questions"]:
            key = f"in_q_{qid}"
            val = st.session_state.get(key)
            model_val = a.driver_answers.get(qid)
            if val in DRIVER_ANSWERS:
                a.driver_answers[qid] = val
            elif model_val in DRIVER_ANSWERS:
                st.session_state[key] = model_val
            elif key not in st.session_state:
                st.session_state[key] = None


def results() -> Results:
    """Compute the current results bundle from the assessment."""
    a = get_assessment()
    sync_driver_answers(a)
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
    for k in [k for k in st.session_state.keys() if not _preserved(k)]:
        del st.session_state[k]
