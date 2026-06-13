import httpx
from config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

async def exists(isrc: str) -> bool:
    """Queries the database to verify if an ISRC has already been processed."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/music_labels?isrc=eq.{isrc}&select=isrc", 
            headers=HEADERS
        )
        
        # If the database returns an error code, report it and stop the execution
        if response.status_code != 200:
            print(f"❌ Database connection error in exists() check (Status {response.status_code})")
            print(f"Details: {response.text}")
            return False
            
        data = response.json()
        # Ensure the response is a valid list matching database records
        if isinstance(data, list):
            return len(data) > 0
        return False

async def save_label(data: dict) -> bool:
    """Inserts a fully formatted developmental nutritional label into Postgres."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/music_labels", 
            headers=HEADERS, 
            json=data
        )
        
        if response.status_code in (200, 201):
            print("🚀 Successfully saved payload to Supabase!")
            return True
        else:
            print(f"❌ Supabase Insertion Failed (Status Code: {response.status_code})")
            print(f"Error Details: {response.text}")
            return False
        
async def get_label(isrc: str) -> dict:
    """Retrieves the fully processed nutritional label for a given track."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/music_labels?isrc=eq.{isrc}&select=nutritional_label",
            headers=HEADERS
        )
        if response.status_code == 200:
            data = response.json()
            # If the track exists, extract and return just the nested label JSON
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("nutritional_label", {})
        return {}