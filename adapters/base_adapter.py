from abc import ABC, abstractmethod
from typing import List, Dict

class StreamingAdapter(ABC):
    """
    The universal contract for all walled-garden streaming platforms.
    Every platform adapter must implement these exact asynchronous methods.
    """

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Handles OAuth 2.0, token generation, or key validation for the platform.
        Returns True if the connection is successfully established.
        """
        pass

    @abstractmethod
    async def fetch_playlist(self, playlist_id: str) -> List[Dict]:
        """
        Pulls a vendor playlist and normalizes it for the core engine.
        
        Must return a list of dictionaries with standard keys to bridge the gap 
        between ISRC-based platforms (Spotify/Apple) and Video ID platforms (YouTube):
        [
            {
                "vendor_id": "xyz123", # The platform's native track identifier
                "title": "Watermelon Sugar",
                "artist": "Harry Styles",
                "isrc": "USUM71900123" # Optional: Nullable if the platform doesn't support it
            }
        ]
        """
        pass

    @abstractmethod
    async def create_safe_playlist(self, safe_vendor_ids: List[str], original_name: str) -> str:
        """
        Takes the array of approved vendor IDs and commands the platform to create a new list.
        Returns the URL or ID of the newly generated "[Safe]" playlist.
        """
        pass