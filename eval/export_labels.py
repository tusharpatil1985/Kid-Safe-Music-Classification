"""
Export eval/labels.json to eval/labels.csv for hand-labeling in a spreadsheet.
See eval/README.md.
"""

import csv
import json
import os

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH = os.path.join(EVAL_DIR, "labels.json")
CSV_PATH = os.path.join(EVAL_DIR, "labels.csv")

BAND_NAMES = ["toddler_0_4", "preschool_5_7", "tween_8_12"]
FIELDNAMES = ["id", "title", "artist", "source_category"] + BAND_NAMES + ["notes"]


def main():
    with open(LABELS_PATH) as f:
        tracks = json.load(f)

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for track in tracks:
            row = {
                "id": track["id"],
                "title": track["title"],
                "artist": track["artist"],
                "source_category": track["category"],
                "notes": track["notes"],
            }
            for band in BAND_NAMES:
                value = track["labels"][band]
                row[band] = "" if value is None else value
            writer.writerow(row)

    print(f"Wrote {len(tracks)} track(s) to {CSV_PATH}")


if __name__ == "__main__":
    main()
