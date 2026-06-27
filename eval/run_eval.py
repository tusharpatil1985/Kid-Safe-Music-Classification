"""
Evaluate phase of the evaluation harness. See eval/README.md.

Loads labels.json and scores_cache.json, re-applies
core.policy.evaluate_all_bands() to the cached scores, and reports per-band
metrics. Pure/offline and instant -- re-run after every core/policy.py
threshold change.
"""

import argparse
import csv
import json
import os
import uuid

from core import policy
from core.policy import BANDS, evaluate_all_bands
from eval import eval_store
from services import llm_service

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH = os.path.join(EVAL_DIR, "labels.json")
CACHE_PATH = os.path.join(EVAL_DIR, "scores_cache.json")
RESULTS_PATH = os.path.join(EVAL_DIR, "results.json")
RESULTS_CSV_PATH = os.path.join(EVAL_DIR, "results.csv")

BAND_NAMES = list(BANDS.keys())
DECISIONS = ["approve", "block", "review"]


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def _fmt_rate(rate):
    return "n/a" if rate is None else f"{rate:.1%}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true",
                         help="Snapshot this run's metrics/results to Supabase")
    parser.add_argument("--notes", default="", help="Free-text note for this snapshot")
    args = parser.parse_args()

    tracks = _load_json(LABELS_PATH, [])
    cache = _load_json(CACHE_PATH, {})

    missing = []
    predictions = []  # list of (track, predicted_decisions_per_band)

    for track in tracks:
        track_id = track["id"]
        if track_id not in cache:
            missing.append(track_id)
            continue

        entry = cache[track_id]
        missing_signals = set(entry["missing_signals"])
        decisions = evaluate_all_bands(entry["scores"], entry["confidence"], missing_signals)
        predictions.append((track, decisions))

    results = {"missing": missing, "bands": {}, "unsafe_approval_by_category": {}}

    print("=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)
    if missing:
        print(f"\n⚠️  {len(missing)} labeled track(s) have no cached scores "
              f"(run score_corpus.py): {', '.join(missing)}")

    for band in BAND_NAMES:
        confusion = {label: {pred: 0 for pred in DECISIONS} for label in DECISIONS}
        n_total = 0
        n_unlabeled = 0
        n_blocked_labels = 0
        n_blocked_approved = 0
        n_approve_labels = 0
        n_approve_friction = 0
        n_review_preds = 0

        for track, decisions in predictions:
            label = track["labels"][band]
            if label is None:
                n_unlabeled += 1
                continue

            pred = decisions[band]["decision"]
            confusion[label][pred] += 1
            n_total += 1

            if label == "block":
                n_blocked_labels += 1
                if pred == "approve":
                    n_blocked_approved += 1
            if label == "approve":
                n_approve_labels += 1
                if pred in ("block", "review"):
                    n_approve_friction += 1
            if pred == "review":
                n_review_preds += 1

        unsafe_approval_rate = _rate(n_blocked_approved, n_blocked_labels)
        over_block_rate = _rate(n_approve_friction, n_approve_labels)
        escalation_rate = _rate(n_review_preds, n_total)

        results["bands"][band] = {
            "n_tracks": n_total,
            "n_unlabeled": n_unlabeled,
            "unsafe_approval_rate": unsafe_approval_rate,
            "over_block_rate": over_block_rate,
            "escalation_rate": escalation_rate,
            "confusion_matrix": confusion,
        }

        print(f"\n--- {band} (n={n_total}, unlabeled skipped={n_unlabeled}) ---")
        print(f"  UNSAFE-APPROVAL RATE: {_fmt_rate(unsafe_approval_rate)} "
              f"({n_blocked_approved}/{n_blocked_labels} labeled 'block' tracks were approved)")
        print(f"  OVER-BLOCK RATE:      {_fmt_rate(over_block_rate)} "
              f"({n_approve_friction}/{n_approve_labels} labeled 'approve' tracks got block/review)")
        print(f"  ESCALATION RATE:      {_fmt_rate(escalation_rate)} "
              f"({n_review_preds}/{n_total} tracks routed to review)")
        print(f"  Confusion matrix (label x prediction):")
        header = f"    {'label':<10}" + "".join(f"{p:>10}" for p in DECISIONS)
        print(header)
        for label in DECISIONS:
            row = f"    {label:<10}" + "".join(f"{confusion[label][p]:>10}" for p in DECISIONS)
            print(row)

    # Unsafe-approval rate sliced by category.
    print("\n" + "=" * 70)
    print("UNSAFE-APPROVAL RATE BY CATEGORY")
    print("=" * 70)

    categories = sorted({track["category"] for track, _ in predictions})
    for band in BAND_NAMES:
        results["unsafe_approval_by_category"][band] = {}
        print(f"\n--- {band} ---")
        any_printed = False
        for category in categories:
            n_blocked = 0
            n_approved = 0
            for track, decisions in predictions:
                if track["category"] != category or track["labels"][band] != "block":
                    continue
                n_blocked += 1
                if decisions[band]["decision"] == "approve":
                    n_approved += 1

            if n_blocked == 0:
                continue
            rate = _rate(n_approved, n_blocked)
            results["unsafe_approval_by_category"][band][category] = {
                "unsafe_approval_rate": rate,
                "n_blocked_labels": n_blocked,
                "n_approved": n_approved,
            }
            print(f"  {category:<20} {_fmt_rate(rate)} ({n_approved}/{n_blocked})")
            any_printed = True

        if not any_printed:
            print("  (no tracks labeled 'block' for this band)")

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    print(f"\n✅ Full results written to {RESULTS_PATH}")

    # Per-track CSV: my label vs. the classifier's decision and reasons, side
    # by side, so disagreements jump out.
    csv_fieldnames = ["id", "title", "artist"]
    for band in BAND_NAMES:
        csv_fieldnames += [f"{band}_label", f"{band}_decision", f"{band}_reasons"]

    with open(RESULTS_CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        for track, decisions in predictions:
            row = {"id": track["id"], "title": track["title"], "artist": track["artist"]}
            for band in BAND_NAMES:
                label = track["labels"][band]
                row[f"{band}_label"] = "" if label is None else label
                row[f"{band}_decision"] = decisions[band]["decision"]
                row[f"{band}_reasons"] = "; ".join(decisions[band]["reasons"])
            writer.writerow(row)

    print(f"✅ Per-track results written to {RESULTS_CSV_PATH}")

    # --- Optional Supabase snapshot --------------------------------------
    if not args.publish:
        return

    run_id = str(uuid.uuid4())
    run_record = {
        "id": run_id,
        "rubric_version": policy.RUBRIC_VERSION,
        "bands_hash": policy.bands_hash(),
        "model_version": llm_service.MODEL,
        "notes": args.notes,
        "metrics": results["bands"],
    }
    if eval_store.insert_run(run_record) is None:
        print("⚠️  Skipping eval_results publish (eval_runs insert failed).")
        return

    result_rows = []
    for track, decisions in predictions:
        entry = cache[track["id"]]
        for band in BAND_NAMES:
            result_rows.append({
                "run_id": run_id,
                "track_id": track["id"],
                "title": track["title"],
                "artist": track["artist"],
                "band": band,
                "predicted_decision": decisions[band]["decision"],
                "label": track["labels"][band],
                "reasons": decisions[band]["reasons"],
                "confidence": entry["confidence"],
                "missing_signals": sorted(entry["missing_signals"]),
            })

    if eval_store.insert_results(run_id, result_rows):
        print(f"✅ Published eval run {run_id} ({len(result_rows)} result rows) to Supabase")
    else:
        print(f"⚠️  eval_runs row {run_id} was published, but eval_results failed")


if __name__ == "__main__":
    main()
