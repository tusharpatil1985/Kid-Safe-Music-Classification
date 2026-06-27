"""Offline checks for the decision layer. No network: feeds mock scores to
policy.evaluate and prints the per-band decision for each scenario, plus a few
assertions on the audio-affect derivation."""

from core import policy
from services import acoustic_service as ac

BANDS = ["toddler_0_4", "preschool_5_7", "tween_8_12"]


def show(name, scores, confidence, missing):
    print(f"\n{name}")
    print(f"  scores={scores} conf={confidence} missing={sorted(missing)}")
    for b in BANDS:
        d = policy.evaluate(scores, confidence, missing, b)
        reasons = "; ".join(d["reasons"]) or "clear"
        print(f"    {b:>13}: {d['decision'].upper():7} ({reasons})")


def affect_for(features):
    return ac.derive_affect(features)


print("=" * 70)
print("AUDIO AFFECT DERIVATION")
calm = {"available": True, "energy": 0.15, "valence": 0.78, "bpm": 75, "loudness": -25}
harsh = {"available": True, "energy": 0.95, "valence": 0.1, "bpm": 175, "loudness": -3}
print("  calm  ->", affect_for(calm))
print("  harsh ->", affect_for(harsh))

print("\n" + "=" * 70)
print("ROUTING SCENARIOS")

# 1. Calm, confirmed instrumental, audio available.
show("1. Calm instrumental (lullaby)",
     {**{d: 1 for d in policy.SEMANTIC_DIMS}, **affect_for(calm)}, 1.0, set())

# 2. Aggressive instrumental (e.g. metal track, no words).
show("2. Aggressive instrumental",
     {**{d: 1 for d in policy.SEMANTIC_DIMS}, **affect_for(harsh)}, 0.8, set())

# 3. Vocals present, lyrics + ASR failed -> semantic unverified.
show("3. Unverified vocals (no lyrics, ASR empty)",
     {**affect_for(calm)}, 0.8, {"semantic"})

# 4. Explicit lyrics (overt sexual content), calm audio.
show("4. Explicit lyrics",
     {"behavioral_defiance": 2, "substance_reference": 3, "relational_aggression": 2,
      "romantic_sexual_innuendo": 8, **affect_for(calm)}, 0.9, set())

# 5. Mild romantic theme, calm audio -> gradient across bands.
show("5. Mild romantic theme (innuendo 3)",
     {"behavioral_defiance": 1, "substance_reference": 1, "relational_aggression": 1,
      "romantic_sexual_innuendo": 3, **affect_for(calm)}, 0.9, set())

# 6. Clean lyrics but the model wasn't sure.
show("6. Clean but low confidence (0.6)",
     {"behavioral_defiance": 1, "substance_reference": 1, "relational_aggression": 1,
      "romantic_sexual_innuendo": 1, **affect_for(calm)}, 0.6, set())

# 7. Clean lyrics, high confidence, but audio lookup failed.
show("7. Clean lyrics, audio unavailable",
     {"behavioral_defiance": 1, "substance_reference": 1, "relational_aggression": 1,
      "romantic_sexual_innuendo": 1}, 0.9, {"acoustic"})

print("\n" + "=" * 70)
print("ASSERTIONS")
checks = [
    ("calm instrumental approves for toddler",
     policy.evaluate({**{d: 1 for d in policy.SEMANTIC_DIMS}, **affect_for(calm)}, 1.0, set(), "toddler_0_4")["decision"] == "approve"),
    ("aggressive instrumental blocks for toddler",
     policy.evaluate({**{d: 1 for d in policy.SEMANTIC_DIMS}, **affect_for(harsh)}, 0.8, set(), "toddler_0_4")["decision"] == "block"),
    ("aggressive instrumental approves for tween (affect not gated)",
     policy.evaluate({**{d: 1 for d in policy.SEMANTIC_DIMS}, **affect_for(harsh)}, 0.8, set(), "tween_8_12")["decision"] == "approve"),
    ("unverified vocals review for tween",
     policy.evaluate({**affect_for(calm)}, 0.8, {"semantic"}, "tween_8_12")["decision"] == "review"),
    ("explicit lyrics block for tween",
     policy.evaluate({"romantic_sexual_innuendo": 8, **affect_for(calm)}, 0.9, set(), "tween_8_12")["decision"] == "block"),
    ("missing audio does NOT stall a clean tween decision",
     policy.evaluate({d: 1 for d in policy.SEMANTIC_DIMS}, 0.9, {"acoustic"}, "tween_8_12")["decision"] == "approve"),
    ("missing audio DOES stall a toddler decision",
     policy.evaluate({d: 1 for d in policy.SEMANTIC_DIMS}, 0.9, {"acoustic"}, "toddler_0_4")["decision"] == "review"),
]
ok = True
for label, passed in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    ok = ok and passed
print("\nALL PASS" if ok else "\nSOME FAILED")
