import asyncio
from adapters.youtube_adapter import YouTubeAdapter
from orchestrator import process_track
from services import db_service

async def curate(playlist_id: str, target_profile: str):
    """Executes the end-to-end ingestion, evaluation, and mutation loop."""
    adapter = YouTubeAdapter()
    
    print("🌍 Step 1: Initiating Platform Authentication...")
    await adapter.authenticate()

    print(f"\n📥 Step 2: Fetching source tracks from playlist: {playlist_id}...")
    tracks = await adapter.fetch_playlist(playlist_id)
    print(f"✅ Found {len(tracks)} tracks.")

    safe_vendor_ids = []

    print("\n🧠 Step 3: Engaging Pipeline & Safety Evaluation...")
    for idx, track in enumerate(tracks, 1):
        vid = track["vendor_id"]
        title = track["title"]
        artist = track["artist"]

        print(f"\n[{idx}/{len(tracks)}] Analyzing: {title} by {artist}")
        
        # A: Guarantee the track exists in Supabase. 
        # If missing, this automatically triggers the LLM and Acoustic services.
        # (Using YouTube ID as the ISRC for this PoC)
        await process_track(vid, title, artist)

        # B: Retrieve the final processed label from the database
        label = await db_service.get_label(vid)
        ratings = label.get("calculated_age_ratings", {})

        # C: Evaluate against the specific target child profile requested by the parent
        status = ratings.get(target_profile, "blocked")
        
        if status == "approved":
            print(f"🟢 [APPROVED] Safe for profile: {target_profile}")
            safe_vendor_ids.append(vid)
        else:
            print(f"🔴 [BLOCKED] Restricted for profile: {target_profile}")

    print(f"\n🎉 Curation Complete! {len(safe_vendor_ids)} out of {len(tracks)} tracks approved.")
    
    # Step 4: Final Playlist Mutation
    if safe_vendor_ids:
        print("\n🔨 Step 4: Pushing approved tracks back to YouTube as a new playlist...")
        new_url = await adapter.create_safe_playlist(safe_vendor_ids, "Curated Mix")
        print(f"👉 Your Safe Playlist: {new_url}")
    else:
        print("\n⚠️ No tracks met the safety criteria for this age profile.")

if __name__ == "__main__":
    # Replace with the real YouTube playlist ID you found earlier
    TARGET_PLAYLIST = "PLUxaFuM4aZlRc_Ekjd31rI-T1wLihYI2z"
    
    # Set the target listener profile (e.g., toddler_0_4, preschool_5_7, tween_8_12)
    TARGET_AGE_PROFILE = "toddler_0_4" 
    
    asyncio.run(curate(TARGET_PLAYLIST, TARGET_AGE_PROFILE))