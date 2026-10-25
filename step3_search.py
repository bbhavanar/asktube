import chromadb
from asktube_core import embed_texts, format_time

video_id = "zjkBMFhNj_g"

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(name="asktube")

question = "What is fine-tuning and how is it different from pre-training?"

question_vector = embed_texts([question], "RETRIEVAL_QUERY")[0]

results = collection.query(
    query_embeddings=[question_vector],
    n_results=3,
    where={"video_id": video_id}
)

print("Question:", question)
print()

docs = results["documents"][0]
metas = results["metadatas"][0]
distances = results["distances"][0]

for doc, meta, distance in zip(docs, metas, distances):
    similarity = 1 - distance
    print(f"[{format_time(meta['start'])}] similarity {similarity:.2f}")
    print(f"https://youtu.be/{video_id}?t={meta['start']}")
    print(doc[:200], "...")
    print()