import json
import chromadb
from google.genai import types
from asktube_core import client, embed_texts, format_time

video_id = "zjkBMFhNj_g"
TOP_K = 4
MIN_SIMILARITY = 0.6
CHAT_MODEL = "gemini-3.5-flash"

db = chromadb.PersistentClient(path="chroma_db")
collection = db.get_or_create_collection(name="asktube")


def retrieve(question):
    question_vector = embed_texts([question], "RETRIEVAL_QUERY")[0]
    results = collection.query(
        query_embeddings=[question_vector],
        n_results=TOP_K,
        where={"video_id": video_id}
    )

    found = []
    for doc, meta, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        similarity = 1 - distance
        if similarity >= MIN_SIMILARITY:
            found.append({"text": doc, "start": meta["start"]})
    return found


def build_prompt(question, chunks):
    sources = ""
    for number, chunk in enumerate(chunks, start=1):
        sources += f"[{number}] (at {format_time(chunk['start'])}) {chunk['text']}\n\n"

    return f"""
You are AskTube, a friendly tutor that answers questions about a YouTube video.
Use ONLY the transcript excerpts below. Each excerpt has a number and a timestamp.
The transcript is auto-generated, so it may contain spelling mistakes
(for example "chpt" means ChatGPT). Fix them in your answer.
If the excerpts don't contain the answer, set "answer" to
"This video doesn't cover that." and "sources" to [].

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
        print("AskTube: This video doesn't seem to cover that topic.")
        return

    prompt = build_prompt(question, chunks)
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    result = json.loads(response.text)

    print("AskTube:", result["answer"])
    if result["sources"]:
        print("📍 Watch:")
        for number in sorted(result["sources"], key=lambda n: chunks[n - 1]["start"] if 1 <= n <= len(chunks) else 0):
            if 1 <= number <= len(chunks):
                start = chunks[number - 1]["start"]
                print(f"   {format_time(start)} → https://youtu.be/{video_id}?t={start}")


print("AskTube ready! Ask anything about the video. Type 'exit' to stop.")
while True:
    question = input("\nYou: ")
    if question.lower() == "exit":
        print("Bye!")
        break
    try:
        ask(question)
    except Exception as e:
        print("⚠️ Something went wrong, please try again.", e)