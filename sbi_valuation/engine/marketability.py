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

    A smooth bell shape centered near the estimated midpoint — interest is
    assumed strongest when the ask sits inside the estimated range and fades
    as it climbs above it, with a softer decline below it (a low price does
    not reduce buyer interest the way an excessive price does). Purely
    pedagogical; the constants are chosen for shape, not calibration.
    """
    if price_ratio <= 0:
        return 0.0
    x = math.log(price_ratio)
    if x <= 0:
        # Below midpoint: gentle ramp up (cheap attracts, but far below
        # range can signal problems).
        return math.exp(-((x / 0.55) ** 2))
    # Above midpoint: steeper decline.
    return math.exp(-((x / 0.30) ** 2))


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
        6: "A shorter target timeframe generally calls for pricing at or "
           "below the estimated range and strong deal preparation.",
        12: "A typical planning horizon for a well-prepared small-business "
            "sale process.",
        24: "A longer horizon gives room for aspirational pricing or for "
            "improving the business before going to market.",
    }.get(months, "")
    tilt = {
        "Higher relative marketability": "Illustratively, pricing in this zone is consistent with more buyer interest.",
        "Moderate relative marketability": "Illustratively, buyer interest may be mixed at this price level.",
        "Lower relative marketability": "Illustratively, this pricing level suggests limited buyer interest — a longer timeframe may not fully compensate.",
    }.get(band, "")
    return f"{base} {tilt}".strip()
