import os
import json
import openai
import spotipy
from spotipy.oauth2 import SpotifyOAuth


class ClassicalMusicSearch:
    def __init__(self):
        openai.api_key = os.getenv('OPENAI_API_KEY')
        self.spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv('SPOTIFY_CLIENT_ID'),
            client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
            redirect_uri='http://localhost:8888/callback',
            scope='playlist-modify-public'
        ))

    def generate_spotify_search_query(self, user_query):
        """Use OpenAI to refine the user's query into an optimal Spotify search term."""
        prompt = (
            f"Given the user query: '{user_query}', generate a precise and optimal search term for Spotify that will find "
            f"classical music album relevant to this query. Return only the search term in one line with no extra commentary."
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a classical music expert and search query generator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
        except Exception as e:
            print("Error calling OpenAI for search term:", e)
            return user_query  # Fallback to the original query if necessary

        search_term = response.choices[0].message.content.strip()
        return search_term

    def search_spotify(self, search_term):
        """Query Spotify using the refined search term."""
        results = self.spotify_client.search(q=search_term, type='track', limit=50)
        tracks = results.get('tracks', {}).get('items', [])
        return tracks

    def filter_and_order_tracks(self, tracks, query):
        """
        Use OpenAI to pick out the tracks belonging to the specific piece implied by the original query.
        This call will also order the tracks by their correct movement sequence and remove duplicates (one track per movement).
        """
        # Build a prompt listing the tracks in a simple format.
        prompt = (
            f"From the following list of tracks, select only those recordings that belong to the classical work '{query}'.\n"
            f"Then, arrange the selected tracks in the correct movement order, ensuring that only one track per movement is included.\n"
            f"For example, if the work have four movements, include only one track for each of the four movements.\n"
            f"The total number of tracks should be equal to the number of movements in the work. Do not return any additional tracks.\n"
            f"Each track is provided in the format:\n"
            f"'Track Name - Artist (URI: track URI)'.\n"
            f"Return a JSON array of objects. Each object must contain an 'order' (an integer starting at 1 for the first movement), "
            f"'name', and 'uri'. Do not include any commentary or extra text.\n\n"
            f"Tracks:\n"
        )
        for track in tracks:
            prompt += f"- {track['name']} - {track['artists'][0]['name']} (URI: {track['uri']})\n"

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert in classical music."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
        except Exception as e:
            print("Error calling OpenAI for filtering and ordering:", e)
            return tracks  # Fallback to original track list

        content = response.choices[0].message.content.strip()
        try:
            ordered_tracks_data = json.loads(content)
            ordered_tracks_data.sort(key=lambda x: x['order'])
        except Exception as e:
            print("Error parsing OpenAI response:", e)
            return tracks

        # Reconstruct the full track objects by matching URIs.
        track_map = {track['uri']: track for track in tracks}
        final_tracks = []
        for item in ordered_tracks_data:
            uri = item.get('uri')
            if uri in track_map:
                final_tracks.append(track_map[uri])
        return final_tracks

    def create_playlist(self, tracks, query):
        user_id = self.spotify_client.me()['id']
        playlist = self.spotify_client.user_playlist_create(
            user_id,
            f"Classical Search: {query[:30]}...",
            description=f"Generated from search: {query}"
        )
        track_uris = [track['uri'] for track in tracks]
        self.spotify_client.playlist_add_items(playlist['id'], track_uris)
        return playlist['external_urls']['spotify']


def main():
    cms = ClassicalMusicSearch()
    user_query = input("Enter your classical music query: ")

    # 1. Generate an optimal Spotify search term from the user's query.
    search_term = cms.generate_spotify_search_query(user_query)
    print("Generated Spotify search term:", search_term)

    # 2. Query Spotify with the refined search term.
    tracks = cms.search_spotify(search_term)
    if not tracks:
        print("No tracks found.")
        return

    # 3. Use OpenAI to filter the list and order tracks to include only one per movement.
    final_tracks = cms.filter_and_order_tracks(tracks, search_term)

    # Optionally, create a playlist from the final list.
    playlist_url = cms.create_playlist(final_tracks, user_query)
    print(f"\nCreated playlist: {playlist_url}")
    print("\nSelected tracks in order:")
    for i, track in enumerate(final_tracks, 1):
        print(f"{i}. {track['name']} - {track['artists'][0]['name']}")


if __name__ == '__main__':
    main()
