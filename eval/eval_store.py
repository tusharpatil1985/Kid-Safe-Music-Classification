"""
Optional Supabase snapshots of eval runs. See eval/README.md.

Separate eval_runs / eval_results tables -- never touches the production
music_labels table that services/db_service.py writes to. Only called when
run_eval.py is invoked with --publish; a failed publish here must never lose
the local results.json/results.csv, so every function logs and returns a
failure value instead of raising.
"""

import httpx

from config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def insert_run(run_record: dict) -> str | None:
    """
    Insert one row into eval_runs. run_record must include "id" (a
    caller-generated uuid string). Returns that id on success, or None on
    any failure (logged, never raised).
    """
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/rest/v1/eval_runs", headers=HEADERS, json=run_record, timeout=10.0
        )
    except Exception as e:
        print(f"❌ Failed to publish eval run: {e}")
        return None

    if response.status_code not in (200, 201):
        print(f"❌ Failed to publish eval run (status {response.status_code}): {response.text}")
        return None

    return run_record["id"]


def insert_results(run_id: str, rows: list[dict]) -> bool:
    """
    Insert all eval_results rows (each already includes "run_id") in one
    batch request. Returns True/False; logs and returns False on failure.
    """
    try:
        response = httpx.post(
            f"{SUPABASE_URL}/rest/v1/eval_results", headers=HEADERS, json=rows, timeout=30.0
        )
    except Exception as e:
        print(f"❌ Failed to publish eval results for run {run_id}: {e}")
        return False

    if response.status_code not in (200, 201):
        print(f"❌ Failed to publish eval results for run {run_id} "
              f"(status {response.status_code}): {response.text}")
        return False

    return True
