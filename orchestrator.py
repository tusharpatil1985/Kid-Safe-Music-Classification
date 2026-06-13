import asyncio
from services import db_service, acoustic_service, lyrics_service, llm_service

def calculate_age_ratings(acoustics: dict, semantics: dict) -> dict:
    """Translates raw safety scores into flat boolean controls across early development stages."""
    toddler_safe = (
        semantics.get("romantic_sexual_innuendo", {}).get("score", 1) <= 2 and
        acoustics["bpm"] <= 115 and 
        acoustics["valence"] >= 0.25
    )
    
    preschool_safe = (
        semantics.get("romantic_sexual_innuendo", {}).get("score", 1) <= 4 and
        semantics.get("substance_reference", {}).get("score", 1) <= 2
    )

    return {
        "toddler_0_4": "approved" if toddler_safe else "blocked",
        "preschool_5_7": "approved" if preschool_safe else "blocked",
        "tween_8_12": "approved"
    }

async def process_track(isrc: str, name: str, artist: str):
    """Orchestrates ingestion tasks for an isolated tracking signature."""
    print(f"🔄 Starting pipeline for: {name} by {artist} (ISRC: {isrc})...")
    
    print("🔍 Checking database for existing records...")
    track_exists = await db_service.exists(isrc)
    if track_exists:
        print(f"⏭️ Skipping {isrc}: Track already processed and registered.")
        return

    print("🌐 Pulling acoustic signatures and lyric files concurrently...")
    acoustics, lyrics = await asyncio.gather(
        acoustic_service.get_features(isrc),
        lyrics_service.get_text(isrc, name, artist)
    )
    print(f"📊 Acoustics captured: BPM={acoustics['bpm']}, Valence={acoustics['valence']}")

    has_lyrics = bool(lyrics)
    if has_lyrics:
        print("🧠 Lyrics found. Dispatching payload to LLM classification brain...")
        semantics = await llm_service.analyze_lyrics(lyrics)
    else:
        print("🎵 No lyrics found. Treating track as pure instrumental...")
        semantics = {cat: {"score": 1, "reasoning": "Instrumental track"} for cat in [
            "relational_aggression", "behavioral_defiance", 
            "romantic_sexual_innuendo", "substance_reference", "prosocial_value"
        ]}

    print("🧮 Calculating developmental safety control mappings...")
    age_ratings = calculate_age_ratings(acoustics, semantics)

    payload = {
        "isrc": isrc,
        "track_name": name,
        "artist": artist,
        "has_lyrics": has_lyrics,
        "nutritional_label": {
            "acoustic_profile": acoustics,
            "semantic_profile": semantics,
            "calculated_age_ratings": age_ratings
        }
    }
    
    print("💾 Committing final structural payload to Supabase storage...")
    await db_service.save_label(payload)

if __name__ == "__main__":
    # Execute the explicit trace pipeline
    asyncio.run(process_track("USUM71900123", "Watermelon Sugar", "Harry Styles"))