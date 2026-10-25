import streamlit as st
from asktube_core import (get_playlist_videos, get_video_id, get_video_title,
                          index_video, answer_question, format_time)

st.set_page_config(page_title="AskTube", page_icon="🎯", layout="wide")

# ---------- Memory that survives reruns ----------
if "videos" not in st.session_state:
    st.session_state.videos = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_video" not in st.session_state:
    st.session_state.current_video = None
if "start_time" not in st.session_state:
    st.session_state.start_time = 0
if "pending" not in st.session_state:
    st.session_state.pending = None


def short_title(title):
    return title.split("|")[0].strip()


def title_of(video_id):
    for video in st.session_state.videos:
        if video["id"] == video_id:
            return video["title"]
    return "Video"


def jump_to(video_id, start):
    st.session_state.current_video = video_id
    st.session_state.start_time = start


def ask_suggested(question):
    st.session_state.pending = question


# ---------- Sidebar: load videos ----------
with st.sidebar:
    st.title("🎯 AskTube")
    st.caption("Ask a whole YouTube course anything, and jump to the exact second.")

    link = st.text_input("YouTube video or playlist link")
    if st.button("Load", type="primary", use_container_width=True) and link:
        try:
            if "list=" in link:
                playlist_title, videos = get_playlist_videos(link)
                videos = videos[:5]
            else:
                video_id = get_video_id(link)
                videos = [{"id": video_id, "title": get_video_title(video_id)}]

            progress = st.progress(0.0, text="Starting...")
            loaded = []
            for i, video in enumerate(videos):
                progress.progress(i / len(videos), text=f"Reading: {short_title(video['title'])[:35]}...")
                try:
                    index_video(video["id"], video["title"])
                    loaded.append(video)
                except Exception:
                    st.warning(f"Skipped (no transcript): {short_title(video['title'])}")
            progress.progress(1.0, text="Ready!")

            st.session_state.videos = loaded
            st.session_state.messages = []
            if loaded:
                jump_to(loaded[0]["id"], 0)
        except Exception as e:
            st.error(f"Couldn't load that link: {e}")

    if st.session_state.videos:
        st.divider()
        st.subheader(f"📚 {len(st.session_state.videos)} videos")
        for video in st.session_state.videos:
            st.button(f"▶ {short_title(video['title'])[:40]}", key="lib_" + video["id"],
                      on_click=jump_to, args=(video["id"], 0), use_container_width=True)

# ---------- Main area ----------
if not st.session_state.videos:
    st.title("🎯 AskTube")
    st.subheader("Stop scrubbing through long lectures.")
    st.write("Paste a YouTube **video** or **playlist** link in the sidebar, then ask anything. "
             "AskTube answers and jumps to the exact second it's explained.")
    st.stop()

left, right = st.columns([3, 2], gap="large")

with left:
    st.video(f"https://www.youtube.com/watch?v={st.session_state.current_video}",
             start_time=st.session_state.start_time)
    st.caption(f"Now playing: **{short_title(title_of(st.session_state.current_video))}** "
               f"from {format_time(st.session_state.start_time)}")

with right:
    st.subheader("💬 Ask AskTube")
    chat_box = st.container(height=480)

    with chat_box:
        if not st.session_state.messages:
            st.write("Try one of these:")
            for suggestion in ["Summarize the main ideas", "What are the key terms explained?",
                               "Explain the hardest concept simply"]:
                st.button(suggestion, key="sug_" + suggestion, on_click=ask_suggested, args=(suggestion,))

        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.write(message["content"])
                for j, source in enumerate(message.get("sources", [])):
                    label = f"⏱ {format_time(source['start'])} · {short_title(title_of(source['video_id']))[:30]}"
                    st.button(label, key=f"ts_{i}_{j}", on_click=jump_to,
                              args=(source["video_id"], source["start"]))

    question = st.chat_input("Ask about these videos...")
    if st.session_state.pending:
        question = st.session_state.pending
        st.session_state.pending = None

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        video_ids = [video["id"] for video in st.session_state.videos]
        with st.spinner("Searching the videos..."):
            try:
                result = answer_question(question, video_ids)
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["answer"], "sources": result["sources"]})
            except Exception as e:
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"⚠️ Something went wrong, please try again. ({e})"})
        st.rerun()