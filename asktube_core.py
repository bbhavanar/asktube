from urllib.parse import urlparse, parse_qs
import time
from google.genai import errors
import yt_dlp
from dotenv import load_dotenv
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
client = genai.Client()

CHUNK_SECONDS = 60
EMBED_MODEL = "gemini-embedding-001"

def to_playlist_url(link):
    query = parse_qs(urlparse(link).query)
    if "list" not in query:
        raise ValueError("This link has no playlist in it. Look for 'list=' in the link.")
    return "https://www.youtube.com/playlist?list=" + query["list"][0]
def get_playlist_videos(playlist_url):
    playlist_url = to_playlist_url(playlist_url)
    options = {"extract_flat": True, "quiet": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    if "entries" not in info:
        raise ValueError("This link is not a playlist. Use a link with 'playlist?list='")

    videos = []
    for entry in info["entries"]:
        videos.append({"id": entry["id"], "title": entry.get("title") or "Untitled"})

    return info.get("title", "Playlist"), videos

def get_chunks(video_id):
    ytt = YouTubeTranscriptApi()
    transcript = ytt.fetch(video_id, languages=["en", "hi"])

    chunks = []
    current_text = ""
    current_start = None

    for snippet in transcript:
        if current_start is None:
            current_start = snippet.start

        current_text += " " + snippet.text.replace("\n", " ")

        if snippet.start - current_start >= CHUNK_SECONDS:
            chunks.append({"start": int(current_start), "text": current_text.strip()})
            current_text = ""
            current_start = None

    if current_text:
        chunks.append({"start": int(current_start), "text": current_text.strip()})

    return chunks


def embed_texts(texts, task_type):
    for attempt in range(5):
        try:
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type)
            )
            break
        except errors.ClientError as e:
            if e.code == 429:
                print("⏳ Free-tier limit reached, waiting 60 seconds...")
                time.sleep(60)
            else:
                raise
    else:
        raise RuntimeError("Still rate limited after 5 tries. Try again later.")

    vectors = []
    for embedding in result.embeddings:
        vectors.append(embedding.values)
    return vectors


def format_time(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"

