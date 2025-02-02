import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Load credentials from environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = r"http://localhost:8888/callback"

# Authenticate using OAuth
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="playlist-modify-public"
))

# Test authentication
user = sp.current_user()
print(f"Authenticated as: {user['display_name']}")
