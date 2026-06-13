import asyncio
from adapters.youtube_adapter import YouTubeAdapter

async def run_test():
    adapter = YouTubeAdapter()
    
    print("🌍 Step 1: Initiating Google OAuth Login via Browser...")
    await adapter.authenticate()
    
    # Use a known public YouTube Music playlist ID or your own
    # This ID is a generic reference playlist. Replace it with your own if desired.
    test_playlist_id = "PLUxaFuM4aZlRc_Ekjd31rI-T1wLihYI2z" 
    
    print(f"\n📥 Step 2: Fetching tracks from playlist: {test_playlist_id}...")
    tracks = await adapter.fetch_playlist(test_playlist_id)
    
    print(f"✅ Successfully fetched {len(tracks)} tracks from YouTube:")
    for idx, track in enumerate(tracks[:3], 1):
        print(f"   {idx}. {track['title']} by {track['artist']} (ID: {track['vendor_id']})")
        
    print("\n🔨 Step 3: Testing safe playlist creation with the first song...")
    sample_ids = [tracks[0]['vendor_id']] if tracks else []
    if sample_ids:
        new_url = await adapter.create_safe_playlist(sample_ids, "Test Run")
        print(f"🎉 Success! Check your new safe playlist here:\n👉 {new_url}")

if __name__ == "__main__":
    asyncio.run(run_test())