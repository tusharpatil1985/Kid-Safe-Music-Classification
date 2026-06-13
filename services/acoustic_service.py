import httpx
from config import SOUNDNET_API_KEY

async def get_features(isrc: str) -> dict:
    """Fetches key behavioral acoustic data (BPM, Energy, Valence) via third-party provider."""
    url = "https://soundnet-api.p.rapidapi.com/track/v1/features"
    headers = {"X-RapidAPI-Key": SOUNDNET_API_KEY, "X-RapidAPI-Host": "soundnet-api.p.rapidapi.com"}
    params = {"isrc": isrc}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=5.0)
            data = response.json()
            return {
                "bpm": data.get("tempo", 100),
                "energy": data.get("energy", 0.5),
                "valence": data.get("valence", 0.5)
            }
        except Exception:
            # Safe fallbacks to prevent pipeline stops if an external aggregator times out
            return {"bpm": 100, "energy": 0.5, "valence": 0.5}