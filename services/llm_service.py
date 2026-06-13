import httpx
import json
from config import GEMINI_API_KEY

MODEL = "gemini-2.5-flash"

async def analyze_lyrics(lyrics: str) -> dict:
    """Sends lyrics to Gemini for multi-lingual translation and safety evaluation."""
    
    if not GEMINI_API_KEY:
        print("❌ ERROR: GEMINI_API_KEY is missing from your .env file.")
        return _get_fallback_scores("Missing API Key")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    You are an expert content safety classification engine for streaming media.
    Your task is to analyze the provided song lyrics and rate them across specific categories.
    
    CRITICAL INSTRUCTION FOR MULTI-LINGUAL/TRANSLITERATED CONTENT:
    If the lyrics are in a language other than English, or are written in Romanized phonetics (e.g., Hindi/Bollywood lyrics written in English script), you MUST mentally translate or interpret the underlying semantic meaning into English BEFORE performing the safety rating. Evaluate the actual intent, slang, and meaning of the words.

    Rate the following categories from 1 (entirely safe/neutral) to 10 (highly severe/explicit):
    - prosocial_value (Note: 1 is neutral, 10 is highly positive/educational/altruistic)
    - behavioral_defiance (glorifying illegal acts, violence, minor rebellion)
    - substance_reference (drugs, alcohol, smoking, prescription abuse)
    - relational_aggression (bullying, explicit insults, hate speech)
    - romantic_sexual_innuendo (overt sexual references, crude language)
    
    Return ONLY a raw JSON object with this exact structure:
    {{
      "prosocial_value": {{"score": integer, "reasoning": "brief string in English"}},
      "behavioral_defiance": {{"score": integer, "reasoning": "brief string in English"}},
      "substance_reference": {{"score": integer, "reasoning": "brief string in English"}},
      "relational_aggression": {{"score": integer, "reasoning": "brief string in English"}},
      "romantic_sexual_innuendo": {{"score": integer, "reasoning": "brief string in English"}}
    }}
    
    Lyrics:
    {lyrics}
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            res_data = response.json()
            
            if response.status_code != 200:
                err_msg = res_data.get("error", {}).get("message", "Unknown Gemini Error")
                print(f"❌ Gemini API Rejected the Request: {err_msg}")
                return _get_fallback_scores("API Error")

            raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
            
        except Exception as e:
            print(f"❌ Gemini Connection Failed: {str(e)}")
            return _get_fallback_scores("Connection Error")

def _get_fallback_scores(reason: str) -> dict:
    """Returns a safe, neutral fallback mapping if the LLM crashes."""
    categories = [
        "prosocial_value", "behavioral_defiance", 
        "substance_reference", "relational_aggression", "romantic_sexual_innuendo"
    ]
    return {cat: {"score": 1, "reasoning": f"LLM Bypassed: {reason}"} for cat in categories}