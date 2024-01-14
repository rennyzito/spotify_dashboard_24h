import pandas as pd
import streamlit as st
import openpyxl
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

SPOTIFY_CLIENT_ID = "07c10b44ed23440a8dceff6029aba691"
SPOTIFY_SECRET = "e11dbd6e61f042d6b425057c38c7ca71"
REDIRECT_URL = "http://rennysplaylist.com"

# st.set_page_config(layout="wide", page_title="Spotify Dashboard")

# Function to check if the local data needs an update
def needs_update(local_file="spotify_data.xlsx", update_interval_hours=24):
    if not os.path.exists(local_file):
        return True  # File doesn't exist, needs update
    last_modified_time = os.path.getmtime(local_file)
    last_update_time = datetime.fromtimestamp(last_modified_time)
    time_difference = datetime.now() - last_update_time
    return time_difference.total_seconds() > (update_interval_hours * 3600)

def load_data():
    if needs_update():
        update_data()
    return pd.read_excel("spotify_data.xlsx")


def update_data():
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope="playlist-read-private",
            redirect_uri=REDIRECT_URL,
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_SECRET,
            cache_path="cache.txt"
        )
    )

    results = sp.current_user()
    user_id = results['id']

    playlist_link = "https://open.spotify.com/playlist/0HlGmWlrmgKVepCAmPBPIF?si=22a0612ebd414024"
    playlist_URI = playlist_link.split("/")[-1].split("?")[0]

    complete_audio_data = []
    complete_song_name_data = []
    complete_artist_name_data = []
    complete_artist_genre_data = []
    complete_album_data = []
    complete_track_pop = []

    ##### Extração de Dados daqui para baixo
    def get_playlist_tracks(username, playlist_id):
        results = sp.user_playlist_tracks(username, playlist_id)
        tracks = results['items']
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        return tracks

    tracks = get_playlist_tracks(user_id, playlist_URI)

    for track in tracks:
        # URI
        track_uri = track["track"]["uri"]

        # Track name
        track_name = track["track"]["name"]
        complete_song_name_data.append(track_name)

        # Main Artist
        artist_uri = track["track"]["artists"][0]["uri"]
        artist_info = sp.artist(artist_uri)

        # Name, popularity, genre
        artist_name = track["track"]["artists"][0]["name"]
        complete_artist_name_data.append(artist_name)

        artist_pop = artist_info["popularity"]

        artist_genres = artist_info["genres"]
        complete_artist_genre_data.append(artist_genres)

        # Album
        album = track["track"]["album"]["name"]
        complete_album_data.append(album)

        # Popularity of the track
        track_pop = track["track"]["popularity"]
        complete_track_pop.append(track_pop)

        # Audio Data
        audio_data = sp.audio_features(track_uri)[0]
        complete_audio_data.append(audio_data)
    #
    danceability_list = [dance["danceability"] for dance in complete_audio_data]
    energy_list = [dance["energy"] for dance in complete_audio_data]
    valence_list = [dance["valence"] for dance in complete_audio_data]
    duration_list = [dance["duration_ms"] for dance in complete_audio_data]

    data = {
        "Song Name": complete_song_name_data,
        "Artist Name": complete_artist_name_data,
        "Artist Genre": complete_artist_genre_data,
        "Album": complete_album_data,
        "Track Popularity": complete_track_pop,
        "Dancebility": danceability_list,
        "Energy": energy_list,
        "Valence": valence_list,
        "Duration (ms)": duration_list
    }

    df = pd.DataFrame(data)
    df.to_excel("spotify_data.xlsx", index=False)

def create_dashboard():
    st.set_page_config(layout="wide", page_title="Spotify Dashboard")
    table = load_data()

    def convert_ms_to_minutes(ms):
        return ms / (1000 * 60)  # Convert milliseconds to minutes

    def create_pie(df):
        artist_counts = df["Artist Name"].value_counts().sort_index()
        pie_chart = go.Figure(data=[go.Pie(labels=artist_counts.index, values=artist_counts, textinfo="none")])
        pie_chart.update_layout(title="% Artists in the Playlist")
        return pie_chart

    def create_lollipop_chart(df, top_n=10):
        artist_counts = df["Artist Name"].value_counts().sort_values(ascending=False).head(top_n)

        lollipop_chart = go.Figure()

        lollipop_chart.add_trace(go.Scatter(
            x=artist_counts.index,
            y=artist_counts.values,
            mode='markers',
            marker=dict(
                size=artist_counts.values,
                sizemode='diameter',
                sizeref=0.5,
                sizemin=2
            ),
            text=artist_counts.values,
            textposition='bottom center'
        ))

        # Draw lines below each marker
        for index, value in zip(artist_counts.index, artist_counts.values):
            lollipop_chart.add_shape(
                go.layout.Shape(
                    type="line",
                    x0=index,
                    x1=index,
                    y0=0,
                    y1=value,
                    line=dict(color="rgba(76,149,217,255)", width=1),
                )
            )

        lollipop_chart.update_layout(title="Top 10 Most Frequent Artists",
                                     xaxis=dict(title="Artist"),
                                     yaxis=dict(title="Frequency"))

        return lollipop_chart

    def create_linechart(df, x, y1, y2):
        line_chart = px.line(df, x=x, y=[y1, y2], labels={y1: "Danceability", y2: "Energy"})
        line_chart.update_layout(title="Danceability and Energy over Songs",
                                 yaxis=dict(title=""),
                                 yaxis2=dict(title="Energy", overlaying="y", side="right"))
        return line_chart

    def create_bar_chart(df, top_n=10):
        df["Duration (min)"] = df["Duration (ms)"].apply(convert_ms_to_minutes)
        total_duration_by_artist = df.groupby("Artist Name")["Duration (min)"].sum().reset_index()
        top_10_artists = total_duration_by_artist.nlargest(top_n, "Duration (min)")
        bar_chart = px.bar(top_10_artists,
                           x="Artist Name", y="Duration (min)", orientation="v",
                           title=f"Top {top_n} Artists by Total Duration (min)")
        return bar_chart

    def create_popular_songs_chart(df):
        top_songs = df.nlargest(10, "Track Popularity")
        bar_chart = px.bar(top_songs.sort_values(by="Track Popularity", ascending=True), x="Track Popularity",
                           y="Song Name", orientation="h", text="Track Popularity")
        bar_chart.update_layout(title="Top 10 Most Popular Songs")
        return bar_chart

    def create_donut_chart(df):
        average_energy = df["Energy"].mean()
        donut_chart = go.Figure(go.Pie(labels=["Average Energy", "Remaining"],
                                       values=[average_energy, 1 - average_energy],
                                       hole=0.5,
                                       marker=dict(colors=["#FFA07A", "white"]),
                                       textinfo="none"))

        donut_chart.update_layout(title=f"Average Energy: {average_energy * 100:.2f}%",
                                  annotations=[
                                      dict(text=f"{average_energy * 100:.2f}%", showarrow=False, font_size=20)],
                                  showlegend=False)
        return donut_chart

    ###### Montagem do Dashboard daqui para baixo
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}<style/>", unsafe_allow_html=True)

    st.sidebar.image("images/Spotify_Logo_RGB_White.png")

    table = load_data()

    with st.container():
        selected_artists = st.sidebar.multiselect("Select Artists", table["Artist Name"].unique(),
                                                  table["Artist Name"].unique())
        if not selected_artists:  # If none selected, show all artists
            df_filtered = table
        else:
            df_filtered = table[table["Artist Name"].isin(selected_artists)]

    with st.container():
        st.subheader("Spotify API Dashboard")
        st.title("Dashboard com análise de dados da minha playlist de Kpop")
        st.write(
            "Esse dashboard possui integração direta com o Spotify, o que significa que ele está sempre atualizado.")

    with st.container():
        col1, col2, col3 = st.columns(3)

        bar_chart = create_bar_chart(df_filtered)
        col2.plotly_chart(bar_chart)

        lollipop_chart = create_lollipop_chart(df_filtered, top_n=10)
        col1.plotly_chart(lollipop_chart)

        donut_chart = create_donut_chart(df_filtered)
        col3.plotly_chart(donut_chart, use_container_width=True)

        st.write("---")

    with st.container():
        col1, col2 = st.columns([1.5, 2])

        popular_songs_chart = create_popular_songs_chart(df_filtered)
        col1.plotly_chart(popular_songs_chart, use_container_width=True)

        line_chart = create_linechart(df_filtered, "Song Name", "Dancebility", "Energy")
        col2.plotly_chart(line_chart, use_container_width=True)

        st.write("---")

    with st.container():
        st.write(df_filtered)

create_dashboard()


