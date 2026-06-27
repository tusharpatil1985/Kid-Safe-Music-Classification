import asyncio

from adapters.youtube_adapter import YouTubeAdapter
from core.orchestrator import process_track
from services import db_service


async def curate(playlist_id: str, target_profile: str):
    """Ingest a playlist, then sort each track into approve / review / block
    for the chosen child profile. Approved tracks flow to the safe playlist;
    review tracks are surfaced for a quick parent call, never silently dropped."""
    adapter = YouTubeAdapter()

    print("🌍 Authenticating...")
    await adapter.authenticate()

    print(f"📥 Fetching tracks from playlist: {playlist_id}")
    tracks = await adapter.fetch_playlist(playlist_id)
    print(f"✅ Found {len(tracks)} tracks.")

    approved, needs_review, blocked = [], [], []

    for idx, track in enumerate(tracks, 1):
        vid, title, artist = track["vendor_id"], track["title"], track["artist"]
        print(f"\n[{idx}/{len(tracks)}] {title} — {artist}")

        # NOTE: still passing the YouTube id as the ISRC for this PoC. Real ISRC
        # resolution is the next step; until then the acoustic lookup will often
        # mark audio unavailable, which (correctly) sends affect-gated bands to
        # review rather than guessing.
        await process_track(vid, title, artist)

        label = await db_service.get_label(vid)
        result = label.get("decisions", {}).get(target_profile, {"decision": "review", "reasons": ["no label"]})
        decision = result["decision"]

        if decision == "approve":
            print(f"🟢 APPROVED for {target_profile}")
            approved.append(vid)
        elif decision == "block":
            print(f"🔴 BLOCKED — {'; '.join(result['reasons'])}")
            blocked.append((title, result["reasons"]))
        else:
            print(f"🟡 NEEDS REVIEW — {'; '.join(result['reasons'])}")
            needs_review.append((title, result["reasons"]))

    print(f"\n🎉 Done: {len(approved)} approved, {len(needs_review)} to review, {len(blocked)} blocked.")

    if needs_review:
        print("\n🟡 Waiting on your call:")
        for title, reasons in needs_review:
            print(f"   • {title}  ({'; '.join(reasons)})")

    if approved:
        print("\n🔨 Pushing approved tracks to a new YouTube playlist...")
        new_url = await adapter.create_safe_playlist(approved, "Curated Mix")
        print(f"👉 Safe playlist: {new_url}")
    else:
        print("\n⚠️  Nothing auto-approved yet for this profile.")


if __name__ == "__main__":
    TARGET_PLAYLIST = "PLUxaFuM4aZlRc_Ekjd31rI-T1wLihYI2z"
    TARGET_AGE_PROFILE = "toddler_0_4"
    asyncio.run(curate(TARGET_PLAYLIST, TARGET_AGE_PROFILE))
