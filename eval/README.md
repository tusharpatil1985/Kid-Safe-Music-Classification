# Evaluation harness

Dev tool for measuring how well `core/policy.py`'s thresholds match the
decisions a parent would actually want. Not part of the product pipeline —
nothing here writes to Supabase.

## Workflow

1. Add rows to `labels.json` (see schema below). This is hand labeling — the
   harness never generates or guesses labels. Optionally run
   `python -m eval.harvest` first to pre-fill rows from YouTube playlists (see
   "Harvesting tracks" below). To label in a spreadsheet instead of editing
   JSON by hand, see "Labeling in a spreadsheet" below.
2. Run `python eval/score_corpus.py` to score any new/unlabeled-but-uncached
   tracks. This is the slow, networked part (LLM, ASR, acoustic lookups) and
   writes `eval/scores_cache.json`. Already-cached ids are skipped, so re-runs
   only cost new tracks.
3. Run `python eval/run_eval.py` to compare labels against the cached scores
   and print the metrics report. This is pure/offline and instant — re-run it
   after every `core/policy.py` threshold change.

## `labels.json` schema

A JSON list of objects:

```json
{
  "id": "<YouTube id / ISRC passed to the pipeline>",
  "title": "<track title>",
  "artist": "<artist name>",
  "labels": {
    "toddler_0_4": "approve | block | review",
    "preschool_5_7": "approve | block | review",
    "tween_8_12": "approve | block | review"
  },
  "category": "<tag for slicing, see below>",
  "notes": "<optional free text>"
}
```

Each value in `labels` is the decision YOU want for that band — ground truth,
not a prediction.

## Categories

Use these tags (or add new ones consistently) so misses can be sliced:

- `clear-safe` — obviously fine for all bands
- `clear-unsafe` — obviously not fine for at least one band
- `hard-middle` — borderline / "review" is the right call
- `instrumental` — no vocals, decided on audio affect alone
- `non-english` — lyrics in a language other than English
- `no-captions` — no captions/lyrics available, relies on ASR or goes to review

## Desired spread

Aim for a balanced mix across the categories above. Deliberately include
instrumentals, non-English tracks, and tracks with no captions — these
exercise the no-lyrics fork in `core/orchestrator.py` and are easy to under-
represent if you only label tracks you happen to know the lyrics to.

The example rows in `labels.json` (ids prefixed `EXAMPLE_`) are placeholders
showing the schema — replace or remove them as you add real labels.

## Harvesting tracks

`python -m eval.harvest` saves you from hand-copying `id`/`title`/`artist`.
It reads `eval/sources.json`, a list of public YouTube playlists to pull
from:

```json
[
  {"playlist_id": "<YouTube playlist id>", "category": "clear-safe"}
]
```

`category` is just a source hint (e.g. "this is a kids playlist") — refine it
per track once you've listened. For each new track found, it appends a row to
`labels.json` with `id`/`title`/`artist`/`category` filled in and
`labels: {"toddler_0_4": null, "preschool_5_7": null, "tween_8_12": null}` —
all three left blank for you to fill in.

It uses the same `adapters.youtube_adapter.YouTubeAdapter` and `.env`
credentials as `curate_playlist.py`, so it's subject to YouTube Data API
quota and will prompt for OAuth.

Safe to re-run repeatedly: it dedupes by `id` and never modifies existing
rows, so adding new sources or re-running after you've started labeling won't
touch or duplicate anything you've already done. Rows you add by hand (e.g.
specific known tracks) are likewise left untouched.

`run_eval.py` skips any row where a band's label is still `null`, reporting
it as "unlabeled" for that band, so a partially-labeled `labels.json` works
fine.

## Labeling in a spreadsheet

`labels.json` is awkward to hand-edit directly. To label in Google Sheets
instead:

1. `python -m eval.export_labels` — reads `labels.json`, writes
   `eval/labels.csv` with one row per track and columns `id, title, artist,
   source_category, toddler_0_4, preschool_5_7, tween_8_12, notes`. The three
   band columns are blank wherever the label is still `null`.
2. Open `labels.csv` in Google Sheets (or any spreadsheet app), fill in
   `toddler_0_4`/`preschool_5_7`/`tween_8_12` with `approve`, `block`, or
   `review` (leave blank to keep a band unlabeled), and edit `notes` as
   needed. Export back to CSV, overwriting `eval/labels.csv`.
3. `python -m eval.import_labels` — merges the label and notes columns back
   into `labels.json`, matched by `id`. `id`/`title`/`artist`/`category` are
   never changed. Rows in `labels.json` whose `id` doesn't appear in the CSV
   are left completely untouched. If any label cell is something other than
   `approve`/`block`/`review`/blank, nothing is written — every bad value is
   reported with its row id and column so you can fix it and re-run.

## `results.csv`

Alongside `results.json`, `run_eval.py` also writes `eval/results.csv`: one
row per scored track with `id`, `title`, `artist`, and per band `<band>_label`
(your label), `<band>_decision` (the classifier's decision), and
`<band>_reasons` (the reason strings from `core/policy.py`). Open it next to
`labels.csv` to see your label and the classifier's decision/reasoning side by
side — disagreements jump out.

## Publishing snapshots

By default `run_eval.py` is 100% offline and instant — it only reads
`labels.json`/`scores_cache.json` and writes `results.json`/`results.csv`.
That's the fast loop for tuning thresholds in `core/policy.py`.

`--publish` is opt-in, for runs worth keeping as history:

```
python -m eval.run_eval --publish --notes "tightened toddler sonic_intensity limit to 5"
```

This additionally snapshots the run to Supabase (separate `eval_runs` /
`eval_results` tables — never `music_labels`):

- one `eval_runs` row: a fresh `id` (uuid, append-only — re-publishing never
  overwrites a previous run), `rubric_version` and `bands_hash` (from
  `core/policy.py`, so you know exactly which thresholds produced this run),
  `model_version` (`services.llm_service.MODEL`), your `--notes`, and a
  `metrics` JSONB (the same per-band `unsafe_approval_rate`,
  `over_block_rate`, `escalation_rate`, and confusion-matrix counts printed to
  the terminal).
- one `eval_results` row per scored track per band: `predicted_decision`,
  your `label` (nullable, for unlabeled tracks), `reasons`, `confidence`, and
  `missing_signals`.

A failed publish (network error, missing tables) is logged and does not affect
the local `results.json`/`results.csv`, which are always written first.

### One-time setup

Run once in the Supabase SQL editor:

```sql
create table eval_runs (
  id uuid primary key,
  created_at timestamptz not null default now(),
  rubric_version text not null,
  bands_hash text not null,
  model_version text not null,
  notes text,
  metrics jsonb not null
);

create table eval_results (
  id bigserial primary key,
  run_id uuid not null references eval_runs(id) on delete cascade,
  track_id text not null,
  title text,
  artist text,
  band text not null,
  predicted_decision text not null,
  label text,
  reasons jsonb,
  confidence double precision,
  missing_signals jsonb
);
```
