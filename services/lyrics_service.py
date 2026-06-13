import httpx
import asyncio
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

def _clean_title(title: str) -> str:
    """Strips YouTube-specific noise from track titles for accurate API matching."""
    if not title: return ""
    clean = re.sub(r'[\(\[].*?[\)\]]', '', title)
    if " - " in clean:
        clean = clean.split(" - ")[-1]
    return clean.strip()

async def fetch_by_youtube_id(video_id: str) -> str:
    """Pulls captions in any language and auto-translates them to English."""
    def _fetch():
        try:
            # 1. Fetch the master list of all available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            try:
                # 2. Try to find a native English transcript first
                transcript = transcript_list.find_transcript(['en'])
            except:
                # 3. If English is missing, grab the very first available language 
                #    and force YouTube's engine to translate it to English on the fly.
                transcript = next(iter(transcript_list)).translate('en')
                
            # Fetch the actual text payload and format it
            fetched_data = transcript.fetch()
            formatter = TextFormatter()
            return formatter.format_transcript(fetched_data)
            
        except Exception as e:
            # Fails silently if the video physically has no captions available
            return ""
            
    # Run the synchronous Google SDK request inside an executor pool
    return await asyncio.to_thread(_fetch)

async def fetch_by_search_query(title: str, artist: str) -> str:
    """Falls back to a public lyrics API using the sanitized track title and artist name."""
    clean_title = _clean_title(title)
    url_artist = artist.strip().replace(" ", "%20")
    url_title = clean_title.replace(" ", "%20")
    
    url = f"https://api.lyrics.ovh/v1/{url_artist}/{url_title}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("lyrics", "")
            else:
                print(f"   ↳ Fallback API also returned 404 for '{clean_title}'")
                return ""
        except Exception:
            return ""

async def get_text(track_id: str, title: str = None, artist: str = None) -> str:
    """Fetches lyrics via native YouTube CC, falling back to text search if needed."""
    
    print(f"   ↳ Attempting to extract native YouTube captions...")
    lyrics = await fetch_by_youtube_id(track_id)
    
    if not lyrics and title and artist:
        print(f"   ↳ No captions found. Falling back to external database...")
        lyrics = await fetch_by_search_query(title, artist)
        
    return lyrics