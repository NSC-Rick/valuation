"""
Price-to-Sale Explorer: illustrative relative marketability.

MANDATORY SAFEGUARD (spec §11): Version 1 contains NO validated
transaction or unsold-listing data, so this module must never emit a
numerical probability of sale. The curve below is a conceptual teaching
shape — an unlabeled-index illustration of the general idea that buyer
interest tends to decline as asking price rises above an estimated value
range. It is not a calibrated statistical prediction, and the UI must
label it "Illustrative Relative Marketability — Educational Simulation".

The sale-timeframe control (6/12/24 months) adjusts descriptive guidance
only; it never changes numerical outputs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

ILLUSTRATIVE_LABEL = "Illustrative Relative Marketability — Educational Simulation"
ILLUSTRATIVE_AXIS = "Relative marketability index (illustrative)"

# Descriptive bands — never percentages.
def descriptive_band(index: float) -> str:
    if index >= 0.66:
        return "Higher relative marketability"
    if index >= 0.33:
        return "Moderate relative marketability"
    return "Lower relative marketability"


def marketability_index(price_ratio: float) -> float:
    """Conceptual index in [0, 1] for price_ratio = asking_price / midpoint.

    Monotonically declining logistic shape: lower asking prices correspond
    to higher relative buyer interest, higher prices to lower interest.
    Centered slightly above the midpoint so a market-aligned ask sits in
    the "higher" band. Purely pedagogical; constants chosen for shape,
    not calibration.
    """
    if price_ratio <= 0:
        return 0.0
    return 1.0 / (1.0 + math.exp(6.0 * (price_ratio - 1.15)))


# Illustrative pricing-strategy zones per desired timeframe — price ratios
# of the estimate midpoint. These are educational positioning zones, NOT
# empirical sale windows or probability estimates. The curve itself never
# changes with timeframe.
TIMEFRAME_ZONES = {
    6: {"lo": 0.70, "hi": 0.95, "label": "Competitive strategy zone",
        "note": "Shorter horizon — competitive pricing and strong deal "
                "readiness; little room for a pricing premium."},
    12: {"lo": 0.88, "hi": 1.15, "label": "Balanced market position",
         "note": "Typical planning horizon — pricing near the estimated "
                 "range balances interest and proceeds."},
    24: {"lo": 0.95, "hi": 1.40, "label": "Extended preparation zone",
         "note": "Longer horizon — flexibility to prepare the business, "
                 "market broadly, and evaluate offers."},
}
ZONE_LABEL = "Illustrative pricing-strategy zone — not an empirical estimate"


PRICING_PRESETS = {
    "competitive": {"label": "Competitive pricing", "ratio": 0.90,
                    "note": "Priced below the estimate midpoint — typically "
                            "aims to attract buyer interest quickly."},
    "market": {"label": "Market-aligned pricing", "ratio": 1.00,
               "note": "Priced at the estimate midpoint."},
    "aspirational": {"label": "Aspirational pricing", "ratio": 1.20,
                     "note": "Priced above the estimate midpoint — aims "
                             "higher, usually with longer expected time to "
                             "sell."},
}


@dataclass
class MarketabilityPoint:
    price_ratio: float
    index: float
    band: str


def curve(midpoint: float, n: int = 60, lo: float = 0.5, hi: float = 1.8) -> list:
    """Illustrative curve across a price range around the midpoint."""
    if midpoint <= 0:
        return []
    step = (hi - lo) / max(n - 1, 1)
    out = []
    for i in range(n):
        r = lo + i * step
        idx = marketability_index(r)
        out.append(MarketabilityPoint(r, idx, descriptive_band(idx)))
    return out


def point_for_price(asking_price: float, midpoint: float) -> Optional[MarketabilityPoint]:
    if midpoint <= 0 or asking_price <= 0:
        return None
    r = asking_price / midpoint
    idx = marketability_index(r)
    return MarketabilityPoint(r, idx, descriptive_band(idx))


def timeframe_guidance(months: int, band: str) -> str:
    """Descriptive-only guidance — deliberately non-numeric (spec §11)."""
    base = {
        6: "Short horizon: competitive pricing and strong deal readiness "
           "matter most — expect less room for a pricing premium.",
        12: "Balanced positioning: pricing near the estimated range "
            "typically balances buyer interest with potential proceeds.",
        24: "Longer horizon: more flexibility to prepare the business, "
            "market it broadly, and evaluate offers before accepting.",
    }.get(months, "")
    tilt = {
        "Higher relative marketability": "Illustratively, pricing in this zone is consistent with more buyer interest.",
        "Moderate relative marketability": "Illustratively, buyer interest may be mixed at this price level.",
        "Lower relative marketability": "Illustratively, this pricing level suggests limited buyer interest — a longer timeframe may not fully compensate.",
    }.get(band, "")
    return f"{base} {tilt}".strip()
