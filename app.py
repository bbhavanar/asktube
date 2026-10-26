import time

import streamlit as st
from asktube_core import (get_playlist_videos, get_video_id, get_video_title,
                          index_video, answer_question, format_time)

SAMPLE_COURSE = "https://www.youtube.com/playlist?list=PLKnIA16_Rmva0dRLWEHLznSHKbFD_RJfX"

st.set_page_config(page_title="AskTube", page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")

# ---------- Custom styling ----------
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 4rem; max-width: 1300px;}
iframe {border-radius: 16px;}

.brand {font-size: 1.8rem; font-weight: 800; line-height: 1.3; margin-bottom: 4px;}
.brand .grad, .hero-title {
    background: linear-gradient(90deg, #7C5CFF, #FF5C8A);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-kicker {
    display: inline-block; background: rgba(124,92,255,.15); color: #C9BCFF;
    border: 1px solid rgba(124,92,255,.4); border-radius: 999px;
    padding: 4px 12px; font-size: .85rem; font-weight: 600;
}
.hero-title {
    font-size: clamp(2.2rem, 5vw, 3.6rem); font-weight: 800; line-height: 1.2;
    margin: 18px 0 12px; padding-bottom: 0.1em;
}
.hero-sub {color: #A9A9B8; font-size: 1.15rem; line-height: 1.6; max-width: 720px; margin-bottom: 32px;}
.muted {color: #A9A9B8; font-size: 0.9rem; line-height: 1.5; margin-bottom: 12px;}

.feature-card {
    background: #171A23; border: 1px solid #262A36; border-radius: 16px;
    padding: 20px; min-height: 175px; box-shadow: 0 1px 3px rgba(0,0,0,.3);
    transition: transform .15s, border-color .15s, box-shadow .15s;
}
.feature-card:hover {transform: translateY(-3px); border-color: #7C5CFF; box-shadow: 0 8px 24px rgba(124,92,255,.2);}
.feature-card .icon {font-size: 1.6rem;}
.feature-card .title {font-size: 1.1rem; font-weight: 700; margin: 10px 0 6px;}
.feature-card .text {color: #A9A9B8; font-size: 0.92rem; line-height: 1.5;}

.section-label {color: #A9A9B8; font-size: .8rem; font-weight: 700; letter-spacing: .1em;
                text-transform: uppercase; margin: 40px 0 14px;}
.steps {display: flex; gap: 12px; flex-wrap: wrap;}
.step {flex: 1; min-width: 200px; display: flex; gap: 12px; align-items: center;
       background: #131620; border: 1px solid #262A36; border-radius: 14px; padding: 14px 16px;}
.step .num {flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center;
            background: linear-gradient(135deg, #7C5CFF, #FF5C8A); color: #fff; font-weight: 800;}
.step .label {font-weight: 600;}
.step .hint {color: #A9A9B8; font-size: .85rem;}

.tip {margin-top: 28px; padding: 14px 18px; border-radius: 14px; color: #E9E9F0;
      background: linear-gradient(90deg, rgba(124,92,255,.18), rgba(255,92,138,.10));
      border: 1px solid rgba(124,92,255,.35);}

.now-playing {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: #171A23; border: 1px solid #262A36; border-radius: 12px;
    padding: 10px 14px; margin-top: 10px;
}
.badge {
    background: rgba(124,92,255,.15); color: #B9A8FF; border-radius: 999px;
    padding: 3px 10px; font-size: .8rem; font-weight: 600; white-space: nowrap;
}

/* Timestamp chips under answers */
div[class*="st-key-ts_"] button {
    border-radius: 999px; padding: 2px 12px; min-height: 0; font-size: .82rem;
    background: rgba(124,92,255,.12); border: 1px solid rgba(124,92,255,.45); color: #C9BCFF;
}
div[class*="st-key-ts_"] button:hover {background: #7C5CFF; color: #fff; border-color: #7C5CFF;}

/* Suggested questions */
div[class*="st-key-sug_"] button {border-radius: 12px; border: 1px dashed #3A3F50;}
div[class*="st-key-sug_"] button:hover {border-color: #7C5CFF;}
</style>
""", unsafe_allow_html=True)

# ---------- Memory that survives reruns ----------
defaults = {"videos": [], "messages": [], "current_video": None,
            "start_time": 0, "pending": None, "course_title": ""}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


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


def use_sample():
    st.session_state.link_input = SAMPLE_COURSE


def clear_chat():
    st.session_state.messages = []


def typewriter(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="brand">🎯 <span class="grad">AskTube</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="muted">Ask a whole YouTube course anything, and jump to the exact second.</div>',
                unsafe_allow_html=True)

    link = st.text_input("YouTube video or playlist link", key="link_input",
                         placeholder="Paste a link…")
    max_videos = st.slider("Videos to read from a playlist", 1, 10, 5)

    load_clicked = st.button("✨ Load", type="primary", use_container_width=True)
    st.button("Try a sample course", on_click=use_sample, use_container_width=True)

    if load_clicked and link:
        try:
            if "list=" in link:
                course_title, videos = get_playlist_videos(link)
                videos = videos[:max_videos]
            else:
                video_id = get_video_id(link)
                course_title = get_video_title(video_id)
                videos = [{"id": video_id, "title": course_title}]

            progress = st.progress(0.0, text="Starting…")
            loaded = []
            for i, video in enumerate(videos):
                progress.progress(i / len(videos), text=f"Reading: {short_title(video['title'])[:32]}…")
                try:
                    index_video(video["id"], video["title"])
                    loaded.append(video)
                except Exception:
                    st.warning(f"Skipped (no transcript): {short_title(video['title'])}")
            progress.empty()

            st.session_state.videos = loaded
            st.session_state.course_title = course_title
            st.session_state.messages = []
            if loaded:
                jump_to(loaded[0]["id"], 0)
                st.toast(f"Ready! {len(loaded)} video(s) loaded", icon="🎉")
        except Exception as e:
            st.error(f"Couldn't load that link: {e}")

    if st.session_state.videos:
        st.divider()
        st.segmented_control("Answer language", ["English", "Hindi", "Telugu"],
                             default="English", key="language")
        st.divider()
        st.markdown(f"**📚 {short_title(st.session_state.course_title)}**")
        st.caption(f"{len(st.session_state.videos)} videos")
        for video in st.session_state.videos:
            thumb, button = st.columns([1, 2], vertical_alignment="center")
            thumb.image(f"https://i.ytimg.com/vi/{video['id']}/mqdefault.jpg")
            is_current = video["id"] == st.session_state.current_video
            button.button(short_title(video["title"])[:38], key="lib_" + video["id"],
                          type="primary" if is_current else "secondary",
                          on_click=jump_to, args=(video["id"], 0), use_container_width=True)

# ---------- Welcome screen ----------
if not st.session_state.videos:
    st.markdown('<span class="hero-kicker">🎓 Your AI study companion for YouTube</span>'
                '<div class="hero-title">Stop scrubbing through<br>long lectures.</div>'
                '<div class="hero-sub">Paste a YouTube video or a whole playlist in the sidebar. '
                'Ask anything, and AskTube jumps straight to the second it\'s explained.</div>',
                unsafe_allow_html=True)

    features = [
        ("🧠", "Search a whole course", "One question, answered across every video in a playlist."),
        ("⏱️", "Jump to the moment", "Every answer links to the exact second it's explained."),
        ("🌐", "Your language", "Get answers in English, Hindi or Telugu."),
        ("🛡️", "No made-up answers", "If the videos don't cover it, AskTube tells you."),
    ]
    for column, (icon, title, text) in zip(st.columns(4), features):
        column.markdown(f'<div class="feature-card"><div class="icon">{icon}</div>'
                        f'<div class="title">{title}</div><div class="text">{text}</div></div>',
                        unsafe_allow_html=True)

    steps = [
        ("1", "Paste a link", "A video or a whole playlist"),
        ("2", "Ask a question", "In plain English, Hindi or Telugu"),
        ("3", "Jump to the answer", "Click a timestamp to watch it explained"),
    ]
    steps_html = "".join(
        f'<div class="step"><div class="num">{num}</div>'
        f'<div><div class="label">{label}</div><div class="hint">{hint}</div></div></div>'
        for num, label, hint in steps)
    st.markdown(f'<div class="section-label">How it works</div><div class="steps">{steps_html}</div>'
                '<div class="tip">👈 New here? Click <b>Try a sample course</b>, then <b>✨ Load</b>.</div>',
                unsafe_allow_html=True)
    st.stop()

# ---------- Main: video + chat ----------
top_left, top_right = st.columns([4, 1], vertical_alignment="center")
top_left.markdown(f"### {short_title(st.session_state.course_title)}")
top_right.button("🧹 Clear chat", on_click=clear_chat, use_container_width=True)

left, right = st.columns([3, 2], gap="large")

with left:
    st.video(f"https://www.youtube.com/watch?v={st.session_state.current_video}",
             start_time=st.session_state.start_time)
    st.markdown(
        f'<div class="now-playing"><span>▶ <b>{short_title(title_of(st.session_state.current_video))}</b></span>'
        f'<span class="badge">from {format_time(st.session_state.start_time)}</span></div>',
        unsafe_allow_html=True)

with right:
    chat_box = st.container(height=520)

    with chat_box:
        if not st.session_state.messages:
            st.markdown("#### 👋 Ask me anything about these videos")
            st.caption("Or start with one of these:")
            for suggestion in ["Summarize the main ideas", "What are the key terms explained?",
                               "Explain the hardest concept simply"]:
                st.button("💡 " + suggestion, key="sug_" + suggestion, on_click=ask_suggested,
                          args=(suggestion,), use_container_width=True)

        for i, message in enumerate(st.session_state.messages):
            avatar = "🧑‍🎓" if message["role"] == "user" else "🎯"
            with st.chat_message(message["role"], avatar=avatar):
                if message.get("fresh"):
                    st.write_stream(typewriter(message["content"]))
                    message["fresh"] = False
                else:
                    st.write(message["content"])

                sources = message.get("sources", [])
                if sources:
                    columns = st.columns(min(len(sources), 3))
                    for j, source in enumerate(sources):
                        label = f"⏱ {format_time(source['start'])} · {short_title(title_of(source['video_id']))[:18]}"
                        columns[j % len(columns)].button(
                            label, key=f"ts_{i}_{j}", on_click=jump_to,
                            args=(source["video_id"], source["start"]), use_container_width=True)

    question = st.chat_input("Ask about these videos…")
    if st.session_state.pending:
        question = st.session_state.pending
        st.session_state.pending = None

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        video_ids = [video["id"] for video in st.session_state.videos]
        language = st.session_state.get("language") or "English"
        with st.spinner("Searching the videos…"):
            try:
                result = answer_question(question, video_ids, language)
                st.session_state.messages.append({"role": "assistant", "content": result["answer"],
                                                  "sources": result["sources"], "fresh": True})
            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {e}"})
        st.rerun()