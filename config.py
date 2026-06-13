import os
from dotenv import load_dotenv

# Automatically look for a .env file and load its variables
load_dotenv()

# Centralized configuration management pulling from the environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SOUNDNET_API_KEY = os.getenv("SOUNDNET_API_KEY")

# YouTube API Credentials
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI")

# Gemini Key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")