"""
Scoring phase of the evaluation harness. See eval/README.md.

Calls core.orchestrator.build_verdict() (NOT process_track — no Supabase
writes) for every track in labels.json that isn't already in
scores_cache.json, and caches the raw {scores, confidence, missing_signals}.

This is the slow, networked part (LLM, ASR, acoustic lookups). Re-running it
only scores new/uncached tracks. The fast offline pass is run_eval.py.
"""

import asyncio
import json
import os

from core.orchestrator import build_verdict

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH = os.path.join(EVAL_DIR, "labels.json")
CACHE_PATH = os.path.join(EVAL_DIR, "scores_cache.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _save_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


async def main():
    tracks = _load_json(LABELS_PATH, [])
    cache = _load_json(CACHE_PATH, {})

    todo = [t for t in tracks if t["id"] not in cache]
    print(f"📋 {len(tracks)} labeled tracks, {len(cache)} cached, {len(todo)} to score.")

    for idx, track in enumerate(todo, 1):
        track_id, title, artist = track["id"], track["title"], track["artist"]
        print(f"\n[{idx}/{len(todo)}] {title} — {artist} ({track_id})")
        try:
            verdict = await build_verdict(track_id, title, artist)
        except Exception as e:
            print(f"   ❌ scoring failed: {e}")
            continue

        cache[track_id] = {
            "scores": verdict["scores"],
            "confidence": verdict["confidence"],
            "missing_signals": sorted(verdict["missing_signals"]),
        }
        _save_cache(cache)

    print(f"\n✅ Done. {len(cache)} tracks cached -> {CACHE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
