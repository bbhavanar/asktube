import json
import time
import chromadb
from asktube_core import get_playlist_videos, get_chunks, embed_texts

playlist_url = playlist_url = "https://www.youtube.com/watch?v=X0btK9X0Xnk&list=PLKnIA16_Rmva0dRLWEHLznSHKbFD_RJfX"
MAX_VIDEOS = 5

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(name="asktube", metadata={"hnsw:space": "cosine"})

playlist_title, videos = get_playlist_videos(playlist_url)
print(f"Playlist: {playlist_title} ({len(videos)} videos)")
print(f"Storing the first {MAX_VIDEOS} videos...\n")

stored_videos = []

for video in videos[:MAX_VIDEOS]:
    video_id = video["id"]
    title = video["title"]

    already = collection.get(where={"video_id": video_id}, limit=1)
    if already["ids"]:
        print(f"⏭️  Already stored: {title}")
        stored_videos.append(video)
        continue

    try:
        chunks = get_chunks(video_id)
    except Exception:
        print(f"⚠️  Skipped (no transcript available): {title}")
        continue

    texts, ids, metadatas = [], [], []
    for chunk in chunks:
        texts.append(chunk["text"])
        ids.append(f"{video_id}_{chunk['start']}")
        metadatas.append({"video_id": video_id, "title": title, "start": chunk["start"]})

    vectors = []
    for i in range(0, len(texts), 50):
        vectors += embed_texts(texts[i:i + 50], "RETRIEVAL_DOCUMENT")

    collection.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metadatas)
    stored_videos.append(video)
    print(f"✅ Stored {len(chunks)} chunks: {title}")
    time.sleep(1)

with open("playlist.json", "w", encoding="utf-8") as f:
    json.dump({"title": playlist_title, "videos": stored_videos}, f, ensure_ascii=False, indent=2)

print(f"\n🎉 Done! {len(stored_videos)} videos ready to search.")