from youtube_transcript_api import YouTubeTranscriptApi

video_id = "zjkBMFhNj_g"
CHUNK_SECONDS = 60

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


def format_time(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


print("Total chunks:", len(chunks))
print()

for chunk in chunks[:3]:
    print(f"[{format_time(chunk['start'])}] https://youtu.be/{video_id}?t={chunk['start']}")
    print(chunk["text"][:200], "...")
    print()