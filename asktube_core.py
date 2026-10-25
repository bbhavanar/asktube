import json
import time
from urllib.parse import urlparse, parse_qs

import chromadb
import yt_dlp
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
client = genai.Client()

CHUNK_SECONDS = 60
EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-3.5-flash"
TOP_K = 5
MIN_SIMILARITY = 0.6

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(name="asktube", metadata={"hnsw:space": "cosine"})


# ---------- Links ----------

def to_playlist_url(link):
    query = parse_qs(urlparse(link).query)
    if "list" not in query:
        raise ValueError("This link has no playlist in it. Look for 'list=' in the link.")
    return "https://www.youtube.com/playlist?list=" + query["list"][0]


def get_video_id(link):
    parsed = urlparse(link)
    if parsed.hostname and "youtu.be" in parsed.hostname:
        return parsed.path.lstrip("/")
    query = parse_qs(parsed.query)
    if "v" in query:
        return query["v"][0]
    raise ValueError("Couldn't find a video in this link.")


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


def get_video_title(video_id):
    options = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    return info.get("title", "Untitled")


# ---------- Transcripts & embeddings ----------

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


# ---------- Indexing ----------

def index_video(video_id, title):
    already = collection.get(where={"video_id": video_id}, limit=1)
    if already["ids"]:
        return "skipped"

    chunks = get_chunks(video_id)

    texts, ids, metadatas = [], [], []
    for chunk in chunks:
        texts.append(chunk["text"])
        ids.append(f"{video_id}_{chunk['start']}")
        metadatas.append({"video_id": video_id, "title": title, "start": chunk["start"]})

    vectors = []
    for i in range(0, len(texts), 50):
        vectors += embed_texts(texts[i:i + 50], "RETRIEVAL_DOCUMENT")

    collection.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metadatas)
    return "stored"


# ---------- Answering ----------

def retrieve(question, video_ids):
    question_vector = embed_texts([question], "RETRIEVAL_QUERY")[0]
    results = collection.query(
        query_embeddings=[question_vector],
        n_results=TOP_K,
        where={"video_id": {"$in": video_ids}}
    )

    found = []
    for doc, meta, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        if 1 - distance >= MIN_SIMILARITY:
            found.append({
                "text": doc,
                "start": meta["start"],
                "video_id": meta["video_id"],
                "title": meta.get("title", "Video")
            })
    return found


def build_prompt(question, chunks):
    sources = ""
    for number, chunk in enumerate(chunks, start=1):
        sources += f"[{number}] (Video: {chunk['title']}, at {format_time(chunk['start'])}) {chunk['text']}\n\n"

    return f"""
You are AskTube, a friendly tutor that answers questions about YouTube lectures.
Use ONLY the transcript excerpts below. Each excerpt has a number, a video title and a timestamp.
The transcripts are auto-generated, so they may contain spelling mistakes. Fix them in your answer.
If the excerpts don't contain the answer, set "answer" to
"These videos don't cover that." and "sources" to [].

Reply in JSON with these keys:
- "answer": a clear, simple answer in 3 to 6 sentences
- "sources": a list of the excerpt numbers you used, like [1, 3]

Transcript excerpts:
{sources}
Question: {question}
"""


def answer_question(question, video_ids):
    chunks = retrieve(question, video_ids)
    if not chunks:
        return {"answer": "These videos don't seem to cover that topic.", "sources": []}

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=build_prompt(question, chunks),
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    result = json.loads(response.text)

    sources = []
    for number in result.get("sources", []):
        if 1 <= number <= len(chunks):
            chunk = chunks[number - 1]
            sources.append({"video_id": chunk["video_id"], "start": chunk["start"]})
    sources.sort(key=lambda s: (s["video_id"], s["start"]))

    return {"answer": result.get("answer", ""), "sources": sources}