"""
Decision layer.

Scoring (what is in a track) lives in the services and the orchestrator.
Deciding (whether a track is allowed for a given child) lives here, on its own.
Keeping the two apart is what lets the bands be reconfigured per family without
retraining anything, and lets one cached score be read by any policy.

All scores are on a 1-10 scale where 10 is most concerning, to match the LLM
rubric. `prosocial_value` is scored elsewhere for the label but is NOT gated
here (on that field 10 means "very positive", so it is not a risk signal).
"""

from enum import Enum


class Decision(str, Enum):
    APPROVE = "approve"   # confident and clearly within limits -> silent
    BLOCK = "block"       # confident and clearly over a limit   -> silent
    REVIEW = "review"     # uncertain or borderline              -> ask the parent


SEMANTIC_DIMS = [
    "behavioral_defiance",
    "substance_reference",
    "relational_aggression",
    "romantic_sexual_innuendo",
]

ACOUSTIC_DIMS = [
    "sonic_intensity",      # loud / energetic / frantic
    "affective_darkness",   # dark / aggressive / scary
]

_LABELS = {
    "behavioral_defiance": "defiance/violence",
    "substance_reference": "substances",
    "relational_aggression": "aggression/insults",
    "romantic_sexual_innuendo": "sexual content",
    "sonic_intensity": "sonic intensity",
    "affective_darkness": "dark/aggressive tone",
}

# Per-band configuration.
#   limits        : max acceptable score per dimension; a track BLOCKS above it.
#                   A dimension ABSENT from a band's limits is simply not gated
#                   for that band (its weight is effectively zero). This is how
#                   the affect dimensions matter for toddlers but not tweens.
#   review_margin : how far below the limit still counts as "borderline" and is
#                   sent to the parent instead of being auto-approved.
#   min_confidence: below this, abstain to the parent rather than guess.
#
# These numbers are deliberate starting points, not truths. They are exactly
# what an eval set should calibrate, and exactly what a parent's sliders nudge.
BANDS = {
    # Early childhood: affect-dominated. Words are barely parsed; tone frightens.
    # Strict on everything, and the audio dimensions are gated hard.
    "toddler_0_4": {
        "limits": {
            "behavioral_defiance": 3,
            "substance_reference": 2,
            "relational_aggression": 2,
            "romantic_sexual_innuendo": 2,
            "sonic_intensity": 5,
            "affective_darkness": 4,
        },
        "review_margin": 2,
        "min_confidence": 0.75,
    },
    # Middle childhood: language and themes are landing now; affect matters less.
    "preschool_5_7": {
        "limits": {
            "behavioral_defiance": 5,
            "substance_reference": 3,
            "relational_aggression": 4,
            "romantic_sexual_innuendo": 4,
            "sonic_intensity": 7,
            "affective_darkness": 6,
        },
        "review_margin": 2,
        "min_confidence": 0.70,
    },
    # Tween: theme-tolerant. Only genuinely mature content gates; affect is not
    # gated at all (no acoustic dims in limits), so a track with unavailable
    # audio features can still be decided here on lyrics alone.
    "tween_8_12": {
        "limits": {
            "behavioral_defiance": 7,
            "substance_reference": 6,
            "relational_aggression": 7,
            "romantic_sexual_innuendo": 6,
        },
        "review_margin": 2,
        "min_confidence": 0.65,
    },
}


def evaluate(scores: dict, confidence: float, missing_signals: set, band_name: str) -> dict:
    """
    Turn a scored verdict into a decision for one age band.

    scores          : {dimension: 1-10}. May omit dims whose signal is missing.
    confidence      : overall 0.0-1.0 certainty of the scored verdict.
    missing_signals : subset of {"semantic", "acoustic"} that did not resolve.
    band_name       : key into BANDS.

    Precedence is BLOCK > REVIEW > APPROVE. A clearly disqualifying signal blocks
    even when another signal is missing (e.g. screaming audio blocks for toddlers
    even if the lyrics could not be read).
    """
    band = BANDS[band_name]
    limits = band["limits"]
    margin = band["review_margin"]

    block_reasons = []
    review_reasons = []

    # 1. Confidence gate: don't auto-decide what the scorer wasn't sure about.
    if confidence < band["min_confidence"]:
        review_reasons.append(f"low confidence ({confidence:.0%})")

    # 2. Completeness gate, per signal. A missing signal only forces a review if
    #    THIS band actually gates a dimension that depends on it. Tween ignores
    #    audio, so missing audio never stalls a tween decision.
    if "semantic" in missing_signals and any(d in limits for d in SEMANTIC_DIMS):
        review_reasons.append("lyrics unverified")
    if "acoustic" in missing_signals and any(d in limits for d in ACOUSTIC_DIMS):
        review_reasons.append("audio features unavailable")

    # 3. Per-dimension thresholds, for gated dimensions only.
    for dim, limit in limits.items():
        score = scores.get(dim)
        if score is None:
            continue  # absence is handled by the completeness gate above
        if score > limit:
            block_reasons.append(f"{_LABELS[dim]} {score}/10 (limit {limit})")
        elif score > 1 and score > limit - margin:
            # A score of 1 is "entirely safe" by the rubric and is never
            # borderline, even when a tight limit makes the margin band reach
            # down to it. Only genuinely elevated scores get sent to review.
            review_reasons.append(f"{_LABELS[dim]} {score}/10 near limit {limit}")

    if block_reasons:
        return {"decision": Decision.BLOCK.value, "reasons": block_reasons}
    if review_reasons:
        return {"decision": Decision.REVIEW.value, "reasons": review_reasons}
    return {"decision": Decision.APPROVE.value, "reasons": []}


def evaluate_all_bands(scores: dict, confidence: float, missing_signals: set) -> dict:
    """Convenience: run every band at once for the stored label."""
    return {
        band: evaluate(scores, confidence, missing_signals, band)
        for band in BANDS
    }
