import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import openai

# Set up authentication using environment variables
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDIRECT_URI = "http://localhost:8888/callback"  # Required for user authentication

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


def get_spotify_query(user_request):
    prompt = f"Given the user request '{user_request}', provide an appropriate search query for finding a track on Spotify that contains a high-quality performance of the requested classical piece, ensuring to include the correct opus number if applicable. Return only the query string."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in classical music and Spotify searches."},
                {"role": "user", "content": prompt}
            ]
        )

        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("Error with OpenAI query generation:", e)
        return user_request  # Fallback to user input


def search_tracks(track_query, limit=5):
    print("Doing track query:", track_query)
    spotify_client = get_spotify_client()
    results = spotify_client.search(q=track_query, type='track', limit=limit)  # Retrieve multiple tracks
    return results


def get_album_from_track(track):
    return track["album"] if track else None


def get_album_tracks(album_id):
    spotify_client = get_spotify_client()
    tracks = spotify_client.album_tracks(album_id)
    return tracks


def filter_tracks_with_openai(tracks, user_request):
    track_names = [track["name"] for track in tracks["items"]]
    if not track_names:
        return []

    prompt = (
            f"Here is a list of tracks from a classical music album:\n"
            + "\n".join(track_names) +
            f"\n\nIdentify and return only the tracks that belong to the requested piece: '{user_request}', ensuring the opus number matches if applicable."
            " Please return only the exact track names, separated by new lines."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a music expert trained in classical compositions."},
                {"role": "user", "content": prompt}
            ]
        )

        filtered_tracks_text = response["choices"][0]["message"].get("content", "").strip()
        print("OpenAI Response:\n", filtered_tracks_text)  # Debugging output

        # Convert OpenAI response into a list of track names
        filtered_tracks = [line.strip() for line in filtered_tracks_text.split("\n") if line.strip()]
        return [track for track in tracks["items"] if track["name"] in filtered_tracks]

    except Exception as e:
        print("Error with OpenAI filtering:", e)
        return []  # Return empty if OpenAI filtering fails


def create_spotify_playlist(user_id, playlist_name, track_uris):
    if not track_uris:
        print("No valid tracks found to create a playlist.")
        return

    spotify_auth_client = get_spotify_auth_client()
    playlist = spotify_auth_client.user_playlist_create(user=user_id, name=playlist_name, public=True)
    spotify_auth_client.playlist_add_items(playlist_id=playlist["id"], items=track_uris)
    print(f"Playlist created: {playlist['name']}, URL: {playlist['external_urls']['spotify']}")


# Get user input for the classical piece
user_request = input("Enter the name of a classical piece: ")
query = get_spotify_query(user_request)

tracks = search_tracks(query)

for track in tracks["tracks"]["items"]:
    album = get_album_from_track(track)
    if album:
        print(f"Album: {album['name']}, URL: {album['external_urls']['spotify']}")

        # Retrieve and filter tracks using OpenAI
        album_tracks = get_album_tracks(album['id'])
        selected_tracks = filter_tracks_with_openai(album_tracks, user_request)

        # Fallback: If OpenAI doesn't return results, use keyword matching
        if not selected_tracks:
            print("OpenAI filtering failed; using fallback matching...")
            selected_tracks = [track for track in album_tracks["items"] if
                               user_request.lower() in track["name"].lower()]

        if len(selected_tracks) >= 3:
            print(f"Selected Tracks for '{user_request}':")
            track_uris = [track['uri'] for track in selected_tracks]
            for track in selected_tracks:
                print(f"- {track['name']}")

            # Create Spotify playlist only if tracks are found
            if track_uris:
                user_id = get_spotify_auth_client().current_user()["id"]
                create_spotify_playlist(user_id, f"Classical Piece - {user_request}", track_uris)
            else:
                print("No valid tracks found for playlist creation.")
            break
        else:
            print("Not enough movements found, trying next track...")


# Ensure proper cleanup
def cleanup():
    global sp
    if sp:
        sp = None


import atexit

atexit.register(cleanup)