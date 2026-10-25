import json
import chromadb
from google.genai import types
from asktube_core import client, embed_texts, format_time

TOP_K = 5
MIN_SIMILARITY = 0.6
CHAT_MODEL = "gemini-3.5-flash"

with open("playlist.json", "r", encoding="utf-8") as f:
    playlist = json.load(f)

video_ids = []
for video in playlist["videos"]:
    video_ids.append(video["id"])

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(name="asktube")


def retrieve(question):
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
You are AskTube, a friendly tutor that answers questions about a YouTube course.
Use ONLY the transcript excerpts below. Each excerpt has a number, a video title and a timestamp.
The transcripts are auto-generated, so they may contain spelling mistakes. Fix them in your answer.
If the excerpts don't contain the answer, set "answer" to
"This course doesn't cover that." and "sources" to [].

Reply in JSON with these keys:
- "answer": a clear, simple answer in 3 to 6 sentences
- "sources": a list of the excerpt numbers you used, like [1, 3]

Transcript excerpts:
{sources}
Question: {question}
"""


def ask(question):
    chunks = retrieve(question)
    if not chunks:
        print("AskTube: This course doesn't seem to cover that topic.")
        return

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=build_prompt(question, chunks),
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    result = json.loads(response.text)

    print("AskTube:", result["answer"])
    if result["sources"]:
        print("📍 Watch:")
        for number in result["sources"]:
            if 1 <= number <= len(chunks):
                chunk = chunks[number - 1]
                link = f"https://youtu.be/{chunk['video_id']}?t={chunk['start']}"
                print(f"   🎬 {chunk['title']} — {format_time(chunk['start'])} → {link}")


print(f"AskTube ready for: {playlist['title']} ({len(video_ids)} videos)")
print("Ask anything about the course. Type 'exit' to stop.")
while True:
    question = input("\nYou: ")
    if question.lower() == "exit":
        print("Bye!")
        break
    try:
        ask(question)
    except Exception as e:
        print("⚠️ Something went wrong, please try again.", e)