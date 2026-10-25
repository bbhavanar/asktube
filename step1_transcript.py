from youtube_transcript_api import YouTubeTranscriptApi

video_id = "zjkBMFhNj_g"

ytt = YouTubeTranscriptApi()
transcript = ytt.fetch(video_id, languages=["en", "hi"])

for snippet in transcript:
    minutes = int(snippet.start // 60)
    seconds = int(snippet.start % 60)
    print(f"[{minutes:02d}:{seconds:02d}] {snippet.text}")