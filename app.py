"""
Dynamic Physics Learning App with YouTube Integration

A Streamlit application that provides an interactive physics tutor
using YouTube videos. Videos are fetched dynamically based on
what the user wants to learn.

Usage:
    uv run streamlit run app.py
"""

# Top-level imports (remove sentence_transformers here)
import json
import os
import re
from datetime import datetime
from pathlib import Path

import litellm
import numpy as np
import scrapetube
import streamlit as st
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from minio_whisper import (
    get_minio_client,
    list_minio_videos,
    get_minio_public_url,
    download_minio_object_to_tmp,
    process_minio_video_to_indonesian_srt,
    build_video_player_with_subtitles,
    batch_ensure_subtitles,
    ensure_subtitle_for_key,
    search_minio_videos_by_query,
    object_exists,
)

# Load environment variables
load_dotenv()

# Configuration
DATA_DIR = Path("data")
CACHE_FILE = DATA_DIR / "learning_cache.json"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_BASE = os.getenv("LLM_API_BASE", None)  # Optional custom API base URL
MAX_VIDEOS_PER_TOPIC = 5


@st.cache_resource
def get_embedding_model() -> object:
    """Load and cache the sentence transformer model for semantic search."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    except Exception:
        st.warning("Embedding model unavailable; using lightweight text similarity.")
        return None


def compute_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity between two texts using embeddings."""
    model = get_embedding_model()
    if model is None:
        tokens1 = set(re.findall(r'\w+', text1.lower()))
        tokens2 = set(re.findall(r'\w+', text2.lower()))
        if not tokens1 or not tokens2:
            return 0.0
        return len(tokens1 & tokens2) / len(tokens1 | tokens2)
    embeddings = model.encode([text1, text2])
    # Cosine similarity
    similarity = np.dot(embeddings[0], embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
    )
    return float(similarity)


# Page config
st.set_page_config(
    page_title="Physics Learning Assistant",
    page_icon="🔬",
    layout="wide",
)


# =============================================================================
# Cache Management Functions
# =============================================================================

def load_cache() -> dict:
    """Load cache from JSON file."""
    if not CACHE_FILE.exists():
        return {"topics": {}, "last_updated": None}
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"topics": {}, "last_updated": None}


def save_cache(cache: dict):
    """Save cache to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    cache["last_updated"] = datetime.now().isoformat()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def normalize_topic(topic: str) -> str:
    """Normalize topic for cache key."""
    return topic.lower().strip()


def semantic_search_cache(user_topic: str, cache: dict, threshold: float = 0.7) -> tuple[dict | None, str | None]:
    """Find semantically similar topic in cache using local embeddings.

    Args:
        user_topic: The topic user wants to learn
        cache: The cache dictionary
        threshold: Minimum similarity score (0-1) to consider a match

    Returns:
        tuple: (topic_data, matched_key) or (None, None) if no match
    """
    topics = cache.get("topics", {})

    if not topics:
        return None, None

    # First, check exact match (normalized)
    normalized = normalize_topic(user_topic)
    if normalized in topics:
        return topics[normalized], normalized

    # Use local embeddings for semantic similarity
    best_match = None
    best_score = 0.0

    for cached_key in topics.keys():
        # Compare user topic with cached topic key
        similarity = compute_similarity(user_topic.lower(), cached_key.lower())

        if similarity > best_score:
            best_score = similarity
            best_match = cached_key

    # Return match if above threshold
    if best_match and best_score >= threshold:
        return topics[best_match], best_match

    return None, None


def append_to_cache(topic: str, queries: list[str], videos: list[dict]):
    """Append new topic data to cache."""
    cache = load_cache()
    normalized = normalize_topic(topic)

    cache["topics"][normalized] = {
        "original_topic": topic,
        "queries": queries,
        "videos": videos,
        "fetched_at": datetime.now().isoformat(),
    }

    save_cache(cache)


# =============================================================================
# YouTube Fetching Functions (from fetch_youtube_data.py)
# =============================================================================

def parse_video_data(video: dict, query: str) -> dict:
    """Parse scrapetube video data into our format."""
    title = ""
    if "title" in video:
        if "runs" in video["title"] and video["title"]["runs"]:
            title = video["title"]["runs"][0].get("text", "")
        elif "simpleText" in video["title"]:
            title = video["title"]["simpleText"]

    channel = ""
    if "ownerText" in video and "runs" in video["ownerText"]:
        if video["ownerText"]["runs"]:
            channel = video["ownerText"]["runs"][0].get("text", "")

    thumbnail = ""
    if "thumbnail" in video and "thumbnails" in video["thumbnail"]:
        thumbnails = video["thumbnail"]["thumbnails"]
        if thumbnails:
            thumbnail = thumbnails[-1].get("url", "")

    return {
        "video_id": video.get("videoId", ""),
        "title": title,
        "channel": channel,
        "thumbnail": thumbnail,
        "published_time": video.get("publishedTimeText", {}).get("simpleText", ""),
        "length": video.get("lengthText", {}).get("simpleText", ""),
        "view_count": video.get("viewCountText", {}).get("simpleText", ""),
        "query": query,
    }


def fetch_transcript(video_id: str) -> list[dict] | None:
    """Fetch transcript for a video."""
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id)

        transcript = []
        for snippet in transcript_data.snippets:
            transcript.append({
                "text": snippet.text,
                "start": snippet.start,
                "duration": snippet.duration,
            })
        return transcript
    except Exception:
        return None


def fetch_videos_for_queries(queries: list[str], max_total: int = 5) -> list[dict]:
    """Fetch videos for multiple queries."""
    all_videos = []
    seen_ids = set()
    videos_per_query = max(1, max_total // len(queries))

    for query in queries:
        try:
            videos = scrapetube.get_search(query)
            count = 0

            for video in videos:
                if count >= videos_per_query or len(all_videos) >= max_total:
                    break

                video_data = parse_video_data(video, query)

                if not video_data["video_id"] or video_data["video_id"] in seen_ids:
                    continue

                seen_ids.add(video_data["video_id"])

                # Fetch transcript
                video_data["transcript"] = fetch_transcript(video_data["video_id"])
                all_videos.append(video_data)
                count += 1

        except Exception:
            continue

        if len(all_videos) >= max_total:
            break

    return all_videos


# =============================================================================
# LLM Functions
# =============================================================================

def generate_search_queries(topic: str) -> list[str]:
    """Use LLM to generate YouTube search queries from user topic."""
    response = litellm.completion(
        model=LLM_MODEL,
        api_base=LLM_API_BASE,
        messages=[
            {
                "role": "system",
                "content": """You are a helpful assistant that generates YouTube search queries.
Given a learning topic, generate 3 effective YouTube search queries in English.
Return ONLY the queries, one per line, no numbering or bullets."""
            },
            {
                "role": "user",
                "content": f"Generate 3 YouTube search queries for learning about: {topic}"
            }
        ],
    )

    queries_text = response.choices[0].message.content.strip()
    queries = [q.strip() for q in queries_text.split("\n") if q.strip()]
    return queries[:3]  # Limit to 3 queries


def extract_topic_from_message(message: str) -> str | None:
    """Use LLM to extract NEW learning topic from user message.

    Returns None if:
    - User is asking follow-up questions about current topic
    - User is requesting timestamp navigation (e.g., "pindah ke detik 60")
    - User is asking about video content
    - User is answering assessment questions
    """
    response = litellm.completion(
        model=LLM_MODEL,
        api_base=LLM_API_BASE,
        messages=[
            {
                "role": "system",
                "content": """You determine if a user wants to learn a NEW topic or is continuing with their current topic.

Return "NONE" for:
- Follow-up questions about the current topic
- Timestamp/navigation requests ("pindah ke detik 60", "skip to minute 2", "jelaskan bagian ini")
- Questions about video content ("apa yang dijelaskan di menit 3?")
- Answering quiz/assessment questions
- Clarification requests ("jelaskan lagi", "ulangi", "maksudnya apa?")
- General chat ("iya", "tidak", "oke", "paham")

Return the NEW TOPIC only if:
- User explicitly wants to learn something DIFFERENT
- Examples: "saya mau belajar gerak parabola", "ganti ke momentum", "ajarkan tentang energi"

Return ONLY the new topic or "NONE", nothing else."""
            },
            {
                "role": "user",
                "content": message
            }
        ],
    )

    result = response.choices[0].message.content.strip()
    return None if result.upper() == "NONE" else result


def get_video_context(videos: list[dict]) -> str:
    """Build context string from video data for LLM."""
    if not videos:
        return "Tidak ada video yang tersedia."

    context_parts = []
    for i, video in enumerate(videos, 1):
        video_info = f"""
Video {i}:
- ID: {video['video_id']}
- Title: {video['title']}
- Channel: {video['channel']}
"""
        if video.get("transcript"):
            transcript_text = ""
            for segment in video["transcript"]:
                start_time = int(segment["start"])
                transcript_text += f"[{start_time}s] {segment['text']} "
            video_info += f"- Transcript: {transcript_text[:2000]}..."

        context_parts.append(video_info)

    return "\n".join(context_parts)


def get_system_prompt(topic: str, video_context: str, current_video_id: str | None = None) -> str:
    """Generate system prompt for the physics tutor."""

    current_video_info = ""
    if current_video_id:
        current_video_info = f"""
VIDEO YANG SEDANG DITONTON: {current_video_id}
- Jika user minta pindah ke timestamp tertentu (misal "pindah ke detik 60"),
  gunakan video yang SAMA: [VIDEO: {current_video_id}|60]
- JANGAN ganti ke video lain kecuali user minta topik berbeda
"""

    return f"""Kamu adalah tutor fisika yang ramah untuk anak SD. Bantu siswa memahami konsep fisika dengan video YouTube.

TOPIK SAAT INI: {topic}
{current_video_info}

ATURAN PENTING:
1. Jawab dalam Bahasa Indonesia yang SEDERHANA
2. Gunakan bahasa anak SD (umur 10-12 tahun)
3. Jawaban harus SINGKAT (maksimal 3-4 kalimat penjelasan)
4. Gunakan contoh sehari-hari yang mudah dibayangkan anak-anak
5. Hindari istilah rumit, gunakan kata-kata sederhana
6. SELALU akhiri dengan PERTANYAAN ASSESSMENT yang menguji pemahaman:
   - BUKAN sekadar "Sudah paham?" atau "Mengerti?"
   - HARUS pertanyaan yang memaksa siswa BERPIKIR
   - Pertanyaan harus RELEVAN dengan materi yang baru dijelaskan

NAVIGASI VIDEO:
1. TIMESTAMP dalam video yang sama:
   - User: "pindah ke detik 60" → [VIDEO: {current_video_id or 'current_id'}|60]
   - User: "jelaskan menit ke-2" → [VIDEO: {current_video_id or 'current_id'}|120]

2. GANTI ke video lain (jika video lain lebih relevan):
   - Jika ada pertanyaan spesifik yang lebih baik dijawab video lain
   - Format: [VIDEO: video_id_lain|0]

3. TIDAK PERLU video command jika:
   - Hanya menjawab pertanyaan assessment
   - Video saat ini sudah sesuai

FORMAT RESPONS:
[Penjelasan singkat 3-4 kalimat dengan bahasa anak SD]

[Pertanyaan assessment yang menguji pemahaman]

[VIDEO: video_id|timestamp] (HANYA jika perlu navigasi/ganti video)

CONTOH RESPONS:
User: "pindah ke detik 60"
→ "Di bagian ini dijelaskan tentang gaya gesek. Gaya gesek itu seperti rem.

Coba jawab: Kenapa ban mobil dibuat kasar? 🤔

[VIDEO: {current_video_id or 'abc123'}|60]"

User: "jelaskan lebih detail tentang F=ma"
→ (Jika video lain punya penjelasan lebih baik, ganti video)
"F=ma artinya gaya sama dengan massa dikali percepatan...

Coba hitung: Kalau massa 2kg dan percepatan 3, berapa gayanya? 🤔

[VIDEO: video_yang_relevan|timestamp]"

DATA VIDEO YANG TERSEDIA:
{video_context}

Ingat:
- Untuk navigasi timestamp, TETAP gunakan video yang sedang ditonton
- Timestamp harus dalam detik (integer)
- WAJIB akhiri dengan pertanyaan assessment
"""


def chat_with_context(
    messages: list[dict],
    topic: str,
    videos: list[dict],
    current_video_id: str | None = None
) -> str:
    """Send messages to LLM with video context."""
    video_context = get_video_context(videos)
    system_prompt = get_system_prompt(topic, video_context, current_video_id)

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = litellm.completion(
        model=LLM_MODEL,
        api_base=LLM_API_BASE,
        messages=full_messages,
    )

    return response.choices[0].message.content


def parse_video_command(response: str) -> tuple[str | None, int | None]:
    """Parse video command from LLM response."""
    pattern = r'\[VIDEO:\s*([a-zA-Z0-9_-]+)(?:\|(\d+))?\]'
    match = re.search(pattern, response)

    if match:
        video_id = match.group(1)
        timestamp = int(match.group(2)) if match.group(2) else None
        return video_id, timestamp

    return None, None


def clean_response(response: str) -> str:
    """Remove video command from response for display."""
    pattern = r'\[VIDEO:\s*[a-zA-Z0-9_-]+(?:\|\d+)?\]'
    return re.sub(pattern, '', response).strip()


# =============================================================================
# UI Functions
# =============================================================================

def get_youtube_embed_html(video_id: str, start_time: int = 0) -> str:
    """Generate YouTube embed HTML."""
    return f"""
    <iframe
        width="100%"
        height="500"
        src="https://www.youtube.com/embed/{video_id}?start={start_time}&autoplay=1"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
    ></iframe>
    """


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_topic" not in st.session_state:
        st.session_state.current_topic = None
    if "topic_videos" not in st.session_state:
        st.session_state.topic_videos = []
    if "current_video_id" not in st.session_state:
        st.session_state.current_video_id = None
    if "current_timestamp" not in st.session_state:
        st.session_state.current_timestamp = 0
    if "is_fetching" not in st.session_state:
        st.session_state.is_fetching = False
    if "minio_client" not in st.session_state:
        st.session_state.minio_client = get_minio_client()
    if "minio_auto_processed" not in st.session_state:
        st.session_state.minio_auto_processed = False
    if "minio_current_key" not in st.session_state:
        st.session_state.minio_current_key = None


def process_new_topic(topic: str):
    """Process a new learning topic - check cache or fetch new videos.

    Automatically selects the first video for seamless playback.
    """
    cache = load_cache()

    # MinIO-driven selection from chat (no manual search UI)
    prefix = os.getenv("MINIO_PREFIX", "downloads").strip("/")
    all_keys = list_minio_videos(prefix=f"{prefix}/")
    if all_keys:
        ranked = search_minio_videos_by_query(topic, all_keys, top_k=len(all_keys))
        if ranked:
            selected_key = ranked[0]
            st.session_state.minio_current_key = selected_key
            st.session_state.current_topic = topic
            st.session_state.current_video_id = None
            st.session_state.current_timestamp = 0
            try:
                ensure_subtitle_for_key(selected_key)
            except Exception:
                pass
            return True, "minio"

    # Use semantic search to find similar topic in cache
    cached_data, _ = semantic_search_cache(topic, cache)

    if cached_data:
        # Use cached data - NO YouTube search needed
        videos = cached_data["videos"]
        st.session_state.topic_videos = videos
        st.session_state.current_topic = cached_data.get("original_topic", topic)

        # Auto-select first video for seamless experience
        if videos:
            st.session_state.current_video_id = videos[0]["video_id"]
            st.session_state.current_timestamp = 0

        return True, "cache"
    else:
        # Topic is truly new - fetch from YouTube
        st.session_state.is_fetching = True

        with st.spinner(f"🔍 Mencari video tentang '{topic}'..."):
            # Generate search queries
            queries = generate_search_queries(topic)

            # Fetch videos
            videos = fetch_videos_for_queries(queries, MAX_VIDEOS_PER_TOPIC)

            if videos:
                # Save to cache
                append_to_cache(topic, queries, videos)

                # Update session state
                st.session_state.topic_videos = videos
                st.session_state.current_topic = topic
                st.session_state.is_fetching = False

                # Auto-select first video for seamless experience
                st.session_state.current_video_id = videos[0]["video_id"]
                st.session_state.current_timestamp = 0

                return True, "fetched"
            else:
                st.session_state.is_fetching = False
                return False, "no_videos"


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Main application."""
    init_session_state()

    # Title
    st.title("🔬 Asisten Pembelajaran Fisika")
    st.markdown("---")

    # Create 30/70 layout
    chat_col, video_col = st.columns([3, 7])

    # Left column - Chat
    with chat_col:
        st.subheader("💬 Chat dengan Tutor")

        # Show current topic if any
        if st.session_state.current_topic:
            st.info(f"📖 Topik: **{st.session_state.current_topic}**")

        # Chat container
        chat_container = st.container(height=350)

        with chat_container:
            # Initial greeting if no messages
            if not st.session_state.messages:
                with st.chat_message("assistant"):
                    st.markdown("Halo! 👋 Saya tutor fisika kamu.\n\n**Apa yang ingin kamu pelajari hari ini?**\n\nContoh: *Hukum Newton*, *Gerak Parabola*, *Energi Kinetik*, dll.")

            # Display chat history
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ketik pertanyaan atau topik..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Check if this is a new topic or follow-up question
            if not st.session_state.current_topic:
                # First message - treat as topic
                success, _ = process_new_topic(prompt)

                if success:
                    # Generate initial response about the topic
                    response = chat_with_context(
                        st.session_state.messages,
                        st.session_state.current_topic,
                        st.session_state.topic_videos,
                        st.session_state.current_video_id
                    )
                else:
                    response = f"Maaf, saya tidak dapat menemukan video tentang '{prompt}'. Coba topik lain atau rephrase pertanyaanmu."
            else:
                # Check if user wants a new topic
                new_topic = extract_topic_from_message(prompt)

                if new_topic and normalize_topic(new_topic) != normalize_topic(st.session_state.current_topic):
                    # User wants a different topic
                    success, _ = process_new_topic(new_topic)

                    if success:
                        response = chat_with_context(
                            [{"role": "user", "content": prompt}],  # Fresh context
                            st.session_state.current_topic,
                            st.session_state.topic_videos,
                            st.session_state.current_video_id
                        )
                    else:
                        response = f"Maaf, saya tidak dapat menemukan video tentang '{new_topic}'. Mari lanjutkan dengan topik sebelumnya."
                else:
                    # Follow-up question on current topic (including timestamp navigation)
                    response = chat_with_context(
                        st.session_state.messages,
                        st.session_state.current_topic,
                        st.session_state.topic_videos,
                        st.session_state.current_video_id
                    )

            # Parse video command
            video_id, timestamp = parse_video_command(response)

            if video_id:
                st.session_state.current_video_id = video_id
                st.session_state.current_timestamp = timestamp or 0

            # Clean and store response
            clean_resp = clean_response(response)
            st.session_state.messages.append({"role": "assistant", "content": clean_resp})

            st.rerun()

        # Quick topic buttons
        st.markdown("---")
        st.markdown("**💡 Topik Populer:**")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Hukum Newton", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Saya ingin belajar tentang Hukum Newton"})
                st.rerun()
        with col2:
            if st.button("Gerak Parabola", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Saya ingin belajar tentang Gerak Parabola"})
                st.rerun()

        col3, col4 = st.columns(2)
        with col3:
            if st.button("Energi & Usaha", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Saya ingin belajar tentang Energi dan Usaha"})
                st.rerun()
        with col4:
            if st.button("Momentum", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": "Saya ingin belajar tentang Momentum"})
                st.rerun()

        # Clear chat
        if st.button("🗑️ Mulai Ulang", use_container_width=True):
            st.session_state.messages = []
            st.session_state.current_topic = None
            st.session_state.topic_videos = []
            st.session_state.current_video_id = None
            st.session_state.current_timestamp = 0
            st.rerun()

    # Right column - Video
    with video_col:
        # Prefer MinIO playback when a MinIO key has been selected by chat
        if st.session_state.minio_current_key:
            key = st.session_state.minio_current_key
            st.markdown(f"### {Path(key).stem}")
            video_url = get_minio_public_url(key)
            try:
                subtitle_url, _ = ensure_subtitle_for_key(key)
            except Exception:
                subtitle_url = None
            embed_html = build_video_player_with_subtitles(video_url, subtitle_url)
            st.components.v1.html(embed_html, height=480)

        elif st.session_state.current_video_id:
            # Find current video info
            current_video = None
            for video in st.session_state.topic_videos:
                if video["video_id"] == st.session_state.current_video_id:
                    current_video = video
                    break

            # Video title and info
            if current_video:
                st.markdown(f"### {current_video['title']}")
                st.caption(f"📺 {current_video['channel']} • {current_video.get('length', '')}")

            # Embed video
            embed_html = get_youtube_embed_html(
                st.session_state.current_video_id,
                st.session_state.current_timestamp
            )
            st.components.v1.html(embed_html, height=480)

            # Timestamp info
            if st.session_state.current_timestamp > 0:
                minutes = st.session_state.current_timestamp // 60
                seconds = st.session_state.current_timestamp % 60
                st.caption(f"▶️ Mulai dari {minutes}:{seconds:02d}")

            # Simple video navigation (if multiple videos)
            if len(st.session_state.topic_videos) > 1:
                st.markdown("---")
                cols = st.columns(len(st.session_state.topic_videos))
                for i, video in enumerate(st.session_state.topic_videos):
                    with cols[i]:
                        is_current = video["video_id"] == st.session_state.current_video_id
                        btn_label = f"{'▶️ ' if is_current else ''}{i+1}"
                        if st.button(
                            btn_label,
                            key=f"vid_{i}",
                            use_container_width=True,
                            disabled=is_current
                        ):
                            st.session_state.current_video_id = video["video_id"]
                            st.session_state.current_timestamp = 0
                            st.rerun()

        else:
            st.markdown("### 📺 Video Pembelajaran")
            st.info("💡 Ketik topik yang ingin kamu pelajari di chat untuk memulai!")

                    # Tombol manual dihapus; proses dan embed dilakukan otomatis di atas


if __name__ == "__main__":
    main()
