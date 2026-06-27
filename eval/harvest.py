"""
Track harvester for the evaluation harness. See eval/README.md.

Pulls tracks from the YouTube playlists listed in eval/sources.json and
appends new rows to eval/labels.json with id/title/artist/category pre-filled
and labels left null. Existing rows (including hand-labeled ones) are never
modified -- dedup is by id, so this is safe to re-run repeatedly as sources
are added.
"""

import asyncio
import json
import os
from collections import Counter

from adapters.youtube_adapter import YouTubeAdapter

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(EVAL_DIR, "sources.json")
LABELS_PATH = os.path.join(EVAL_DIR, "labels.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


async def main():
    sources = _load_json(SOURCES_PATH, [])
    labels = _load_json(LABELS_PATH, [])
    existing_ids = {t["id"] for t in labels}

    adapter = YouTubeAdapter()
    print("🌍 Authenticating...")
    await adapter.authenticate()

    for source in sources:
        playlist_id, category = source["playlist_id"], source["category"]
        try:
            tracks = await adapter.fetch_playlist(playlist_id)
        except Exception as e:
            print(f"❌ {playlist_id}: {e}")
            continue

        new_count = dup_count = 0
        for track in tracks:
            vid = track["vendor_id"]
            if vid in existing_ids:
                dup_count += 1
                continue

            labels.append({
                "id": vid,
                "title": track["title"],
                "artist": track["artist"],
                "labels": {"toddler_0_4": None, "preschool_5_7": None, "tween_8_12": None},
                "category": category,
                "notes": "",
            })
            existing_ids.add(vid)
            new_count += 1

        print(f"  {playlist_id}: fetched {len(tracks)}, new {new_count}, duplicates skipped {dup_count}")

    _save_json(LABELS_PATH, labels)

    counts = Counter(t["category"] for t in labels)
    print("\nTOTAL category breakdown:")
    for cat, n in sorted(counts.items()):
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    asyncio.run(main())
