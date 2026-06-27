"""
Import a hand-edited eval/labels.csv back into eval/labels.json. See
eval/README.md.

Only the label columns and notes are merged, matched by id. id/title/artist/
category are never changed. Blank label cells become null (still unlabeled).
Rows in labels.json whose id is missing from the CSV are left untouched. If
any label cell has a value other than approve/block/review/blank, nothing is
written and every bad value is reported.
"""

import csv
import json
import os
import sys

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH = os.path.join(EVAL_DIR, "labels.json")
CSV_PATH = os.path.join(EVAL_DIR, "labels.csv")

BAND_NAMES = ["toddler_0_4", "preschool_5_7", "tween_8_12"]
VALID_LABELS = {"approve", "block", "review"}


def main():
    with open(LABELS_PATH) as f:
        tracks = json.load(f)
    by_id = {t["id"]: t for t in tracks}

    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    errors = []
    updates = []  # (track, new_labels, new_notes)

    for row in rows:
        track_id = row["id"]
        if track_id not in by_id:
            print(f"⚠️  skipping row with unknown id {track_id!r} (not in labels.json)")
            continue

        new_labels = {}
        for band in BAND_NAMES:
            value = row[band].strip()
            if value == "":
                new_labels[band] = None
            elif value in VALID_LABELS:
                new_labels[band] = value
            else:
                errors.append((track_id, band, row[band]))

        updates.append((by_id[track_id], new_labels, row["notes"]))

    if errors:
        print(f"❌ {len(errors)} invalid label value(s), labels.json NOT written:")
        for track_id, band, value in errors:
            print(f"  id={track_id} band={band} bad value={value!r} (expected approve/block/review or blank)")
        sys.exit(1)

    for track, new_labels, notes in updates:
        track["labels"].update(new_labels)
        track["notes"] = notes

    with open(LABELS_PATH, "w") as f:
        json.dump(tracks, f, indent=2, ensure_ascii=False)

    print(f"Merged {len(updates)} row(s) from {CSV_PATH} into {LABELS_PATH}")


if __name__ == "__main__":
    main()
