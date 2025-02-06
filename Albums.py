import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import openai
import time

# Set up authentication using environment variables
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIRECT_URI = "http://localhost:8888/callback"  # Required for user authentication

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Spotify API credentials are missing! Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET.")

# Authenticate with Spotify
sp = None


def get_spotify_client():
    global sp
    if sp is None:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))
    return sp


def get_spotify_auth_client():
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI,
                                  scope="playlist-modify-public"))


def safe_openai_request(prompt, retries=3):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in classical music and Spotify searches."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {e}")
            time.sleep(2)
    return None


def search_tracks(track_query, limit=5):
    print("Doing track query:", track_query)
    spotify_client = get_spotify_client()
    return spotify_client.search(q=track_query, type='track', limit=limit)


def get_album_from_track(track):
    return track["album"] if track else None


def get_album_tracks(album_id):
    spotify_client = get_spotify_client()
    return spotify_client.album_tracks(album_id)


def match_tracks_with_openai(user_request, album_tracks):
    track_names = [track["name"] for track in album_tracks["items"]]
    if not track_names:
        return []

    prompt = (
            f"Given the following album track list, identify the tracks that belong to the requested classical piece: '{user_request}'.\n"
            "Ensure that the opus number matches if applicable.\n"
            "Return only the exact track names, separated by new lines.\n\n"
            "Track list:\n" + "\n".join(track_names)
    )

    filtered_tracks_text = safe_openai_request(prompt)
    if not filtered_tracks_text:
        return []

    filtered_tracks = [line.strip() for line in filtered_tracks_text.split("\n") if line.strip()]
    return [track for track in album_tracks["items"] if track["name"] in filtered_tracks]


def create_spotify_playlist(user_id, playlist_name, track_uris):
    if not track_uris:
        print("No valid tracks found to create a playlist.")
        return

    spotify_auth_client = get_spotify_auth_client()
    playlists = spotify_auth_client.user_playlists(user_id)
    existing_playlist = next((p for p in playlists["items"] if p["name"] == playlist_name), None)

    if existing_playlist:
        playlist_id = existing_playlist["id"]
        print(f"Updating existing playlist: {playlist_name}")
    else:
        playlist = spotify_auth_client.user_playlist_create(user=user_id, name=playlist_name, public=True)
        playlist_id = playlist["id"]
        print(f"Created new playlist: {playlist_name}")

    spotify_auth_client.playlist_add_items(playlist_id=playlist_id, items=track_uris)
    print(
        f"Playlist updated: {playlist_name}, URL: {spotify_auth_client.playlist(playlist_id)['external_urls']['spotify']}")


# Get user input for the classical piece
user_request = input("Enter the name of a classical piece: ")
query = safe_openai_request(
    f"Provide a search query for Spotify for: '{user_request}'. Be sure to include the opus number if available.")

if not query:
    print("Using fallback user input as query.")
    query = user_request

tracks = search_tracks(query)

for track in tracks["tracks"]["items"]:
    album = get_album_from_track(track)
    if album:
        print(f"Album: {album['name']}, URL: {album['external_urls']['spotify']}")
        album_tracks = get_album_tracks(album['id'])
        selected_tracks = match_tracks_with_openai(user_request, album_tracks)

        if len(selected_tracks) >= 3:
            print(f"Selected Tracks for '{user_request}':")
            track_uris = [track['uri'] for track in selected_tracks]
            for track in selected_tracks:
                print(f"- {track['name']}")

            user_id = get_spotify_auth_client().current_user()["id"]
            create_spotify_playlist(user_id, f"Classical Piece - {user_request}", track_uris)
            break
        else:
            print("Not enough movements found, trying next track...")


def cleanup():
    global sp
    if sp:
        sp = None


import atexit

atexit.register(cleanup)
