from dotenv import load_dotenv
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
client = genai.Client()

CHUNK_SECONDS = 60
EMBED_MODEL = "gemini-embedding-001"


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
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type)
    )
    vectors = []
    for embedding in result.embeddings:
        vectors.append(embedding.values)
    return vectors


def format_time(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"