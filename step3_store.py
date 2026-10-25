import chromadb
from asktube_core import get_chunks, embed_texts

video_id = "zjkBMFhNj_g"

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(
    name="asktube",
    metadata={"hnsw:space": "cosine"}
)

chunks = get_chunks(video_id)
print("Chunks to store:", len(chunks))

texts = []
ids = []
metadatas = []
for chunk in chunks:
    texts.append(chunk["text"])
    ids.append(f"{video_id}_{chunk['start']}")
    metadatas.append({"video_id": video_id, "start": chunk["start"]})

vectors = []
for i in range(0, len(texts), 50):
    batch = texts[i:i + 50]
    vectors += embed_texts(batch, "RETRIEVAL_DOCUMENT")
    print(f"Embedded {len(vectors)} / {len(texts)}")

collection.upsert(
    ids=ids,
    documents=texts,
    embeddings=vectors,
    metadatas=metadatas
)

print("✅ Stored in ChromaDB:", collection.count(), "chunks")