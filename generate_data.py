"""
MinIO Video Transcription Script with Rich Topics

Transcribes videos from MinIO using OpenAI Whisper API,
generates metadata JSON with rich topics/keywords for search,
and VTT subtitle files.

Usage:
    uv run python generate_data.py
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import time

from dotenv import load_dotenv
from minio import Minio
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration
DATA_DIR = Path("data")
VIDEOS_FILE = DATA_DIR / "videos.json"
SUBTITLES_DIR = DATA_DIR / "subtitles"

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "play.min.io")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "physics-videos")
MINIO_VIDEOS_PATH = os.getenv("MINIO_VIDEOS_PATH", "")
MINIO_SECURE = os.getenv("MINIO_SECURE", "true").lower() == "true"
MAX_VIDEOS = int(os.getenv("MAX_VIDEOS", "0"))  # 0 = no limit


def get_minio_client() -> Minio:
    """Create and return MinIO client."""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def get_openai_client() -> OpenAI:
    """Create and return OpenAI client."""
    return OpenAI()


def get_video_url(object_name: str) -> str:
    """Generate public URL for a video file in MinIO."""
    protocol = "https" if MINIO_SECURE else "http"
    return f"{protocol}://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_name}"


def list_videos(client: Minio, bucket: str, prefix: str = "", max_videos: int = 0) -> list[dict]:
    """List all MP4 videos in the bucket under the given prefix.

    Args:
        client: MinIO client
        bucket: Bucket name
        prefix: Path prefix to filter videos
        max_videos: Maximum number of videos to return (0 = no limit)

    Returns:
        List of video info dicts sorted by size (smallest first)
    """
    videos = []
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"

    try:
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        for obj in objects:
            if obj.object_name.lower().endswith(".mp4"):
                videos.append(
                    {
                        "object_name": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified.isoformat()
                        if obj.last_modified
                        else None,
                    }
                )
    except Exception as e:
        print(f"Error listing objects: {e}")

    # Sort by size (smallest first)
    videos.sort(key=lambda v: v["size"])

    # Apply limit if specified
    if max_videos > 0:
        videos = videos[:max_videos]

    return videos


def download_video(client: Minio, bucket: str, object_name: str) -> str:
    """Download video to temporary file and return path."""
    suffix = Path(object_name).suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name
    temp_file.close()

    try:
        client.fget_object(bucket, object_name, temp_path)
        print(f"  Downloaded: {object_name} -> {temp_path}")
        return temp_path
    except Exception as e:
        print(f"  Error downloading {object_name}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return ""


def transcribe_video(openai_client: OpenAI, video_path: str) -> dict | None:
    """Transcribe video using OpenAI Whisper API."""
    try:
        with open(video_path, "rb") as audio_file:
            print("  Transcribing with Whisper API...")
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="id",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        segments = []
        if hasattr(transcript, "segments") and transcript.segments:
            for seg in transcript.segments:
                segments.append(
                    {
                        "text": getattr(seg, "text", "").strip(),
                        "start": getattr(seg, "start", 0.0),
                        "end": getattr(seg, "end", 0.0),
                    }
                )

        full_text = transcript.text if hasattr(transcript, "text") else ""
        duration = segments[-1]["end"] if segments else 0.0

        return {
            "segments": segments,
            "full_text": full_text,
            "duration": duration,
            "language": "id",
        }
    except Exception as e:
        print(f"  Error transcribing: {e}")
        return None


def format_vtt_timestamp(seconds: float) -> str:
    """Convert seconds to VTT timestamp format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def generate_vtt(segments: list[dict]) -> str:
    """Generate WebVTT subtitle content from segments."""
    vtt_lines = ["WEBVTT", ""]

    for i, seg in enumerate(segments, 1):
        start = format_vtt_timestamp(seg["start"])
        end = format_vtt_timestamp(seg["end"])
        text = seg["text"]

        vtt_lines.append(f"{i}")
        vtt_lines.append(f"{start} --> {end}")
        vtt_lines.append(text)
        vtt_lines.append("")

    return "\n".join(vtt_lines)


def save_vtt_file(video_id: str, vtt_content: str) -> str:
    """Save VTT content to file and return relative path."""
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)

    vtt_filename = f"{video_id}.vtt"
    vtt_path = SUBTITLES_DIR / vtt_filename

    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)

    return f"subtitles/{vtt_filename}"


def extract_title_from_filename(filename: str) -> str:
    """Extract readable title from filename."""
    name = Path(filename).stem
    name = name.replace("_", " ").replace("-", " ")
    return name.title()


def extract_metadata_with_llm(
    openai_client: OpenAI, filename: str, transcript_text: str
) -> dict:
    """Use LLM to extract title, description, and rich topics from video content."""
    max_transcript_len = 4000
    truncated_transcript = transcript_text[:max_transcript_len]
    if len(transcript_text) > max_transcript_len:
        truncated_transcript += "..."

    try:
        response = openai_client.chat.completions.create(
            model="gpt-5-nano-2025-08-07",
            messages=[
                {
                    "role": "system",
                    "content": """Kamu adalah asisten yang menganalisis konten video pembelajaran FISIKA.
Berdasarkan nama file dan transkrip video, ekstrak informasi berikut dalam format JSON:

{
    "title": "Judul video yang deskriptif dalam Bahasa Indonesia",
    "description": "Deskripsi singkat 2-3 kalimat tentang isi video",
    "topics": ["topik1", "topik2", ...],
    "keywords": ["keyword1", "keyword2", ...]
}

ATURAN PENTING untuk topics dan keywords (HARUS 30-50 item total):

1. **Topics** (15-25 item) - Konsep dan topik utama:
   - Topik utama: "hukum newton", "gaya", "gerak"
   - Sub-topik: "hukum 1 newton", "hukum 2 newton", "hukum 3 newton", "inersia"
   - Konsep terkait: "percepatan", "kecepatan", "massa", "momentum"
   - Kategori: "mekanika", "dinamika", "kinematika"

2. **Keywords** (15-25 item) - Kata kunci pencarian:
   - Terminologi: "f=ma", "gaya gesek", "gaya normal"
   - Sinonim Indonesia: "tenaga", "dorongan", "tarikan"
   - Sinonim Inggris: "newton", "force", "motion", "acceleration"
   - Query umum: "rumus newton", "contoh hukum newton", "pengertian gaya"
   - Variasi penulisan: "hkm newton", "newton 1", "newton pertama"

3. Semua dalam lowercase
4. Sertakan variasi ejaan dan singkatan yang umum digunakan siswa
5. Sertakan istilah yang mungkin dicari siswa SD/SMP

Balas HANYA dengan JSON, tanpa penjelasan tambahan.""",
                },
                {
                    "role": "user",
                    "content": f"Filename: {filename}\n\nTranskrip:\n{truncated_transcript}",
                },
            ],
        )

        result_text = response.choices[0].message.content.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        metadata = json.loads(result_text)

        # Combine topics and keywords, ensure minimum coverage
        topics = metadata.get("topics", [])
        keywords = metadata.get("keywords", [])

        # Add filename-based keywords as fallback
        filename_keywords = extract_keywords_from_filename(filename)

        return {
            "title": metadata.get("title", extract_title_from_filename(filename)),
            "description": metadata.get(
                "description", f"Video pembelajaran: {filename}"
            ),
            "topics": topics if topics else filename_keywords,
            "keywords": keywords if keywords else [],
        }

    except Exception as e:
        print(f"  Warning: LLM extraction failed ({e}), using fallback")
        title = extract_title_from_filename(filename)
        filename_keywords = extract_keywords_from_filename(filename)
        return {
            "title": title,
            "description": f"Video pembelajaran: {title}",
            "topics": filename_keywords,
            "keywords": [],
        }


def extract_keywords_from_filename(filename: str) -> list[str]:
    """Extract keywords from filename as fallback."""
    name = Path(filename).stem.lower()
    # Replace separators with spaces
    name = name.replace("_", " ").replace("-", " ").replace(".", " ")
    # Split and filter short words
    words = [w.strip() for w in name.split() if len(w.strip()) > 2]
    return words


def format_duration(seconds: float) -> str:
    """Format duration in MM:SS or HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_eta(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def process_video(
    minio_client: Minio,
    openai_client: OpenAI,
    bucket: str,
    video_info: dict,
    video_index: int,
) -> dict | None:
    """Process a single video: download, transcribe, generate VTT and rich topics.

    Returns:
        Video metadata dict or None on failure
    """
    object_name = video_info["object_name"]
    video_id = f"video_{video_index:03d}"

    print(f"\nProcessing [{video_id}]: {object_name}")

    # Download video
    local_path = download_video(minio_client, bucket, object_name)
    if not local_path:
        return None

    try:
        # Transcribe
        transcript_data = transcribe_video(openai_client, local_path)
        if not transcript_data:
            return None

        # Generate VTT
        vtt_content = generate_vtt(transcript_data["segments"])
        subtitle_file = save_vtt_file(video_id, vtt_content)
        print(f"  Saved subtitle: {subtitle_file}")

        # Extract metadata with rich topics using LLM
        print("  Extracting metadata with rich topics...")
        metadata = extract_metadata_with_llm(
            openai_client, object_name, transcript_data["full_text"]
        )
        print(
            f"  Generated {len(metadata['topics'])} topics, {len(metadata.get('keywords', []))} keywords"
        )

        # Build video metadata
        video_data = {
            "id": video_id,
            "title": metadata["title"],
            "description": metadata["description"],
            "filename": object_name,
            "url": get_video_url(object_name),
            "duration": transcript_data["duration"],
            "duration_formatted": format_duration(transcript_data["duration"]),
            "topics": metadata["topics"],
            "keywords": metadata.get("keywords", []),
            "transcript": transcript_data["segments"],
            "transcript_text": transcript_data["full_text"],
            "subtitle_file": subtitle_file,
            "language": "id",
            "created_at": video_info.get("last_modified"),
            "transcribed_at": datetime.now().isoformat(),
        }

        print(f"  Completed: {metadata['title']} ({video_data['duration_formatted']})")
        return video_data

    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
            print("  Cleaned up temp file")


def save_videos_json(videos: list[dict]):
    """Save all video metadata to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)

    output = {
        "videos": videos,
        "metadata": {
            "total_videos": len(videos),
            "last_updated": datetime.now().isoformat(),
            "minio_bucket": MINIO_BUCKET,
            "minio_videos_path": MINIO_VIDEOS_PATH,
            "minio_endpoint": MINIO_ENDPOINT,
        },
    }

    with open(VIDEOS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved video metadata to: {VIDEOS_FILE}")


def main():
    """Main function to process all videos from MinIO."""
    print("=" * 60)
    print("MinIO Video Transcription + Rich Topics Script")
    print("=" * 60)

    # Validate configuration
    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        print("Error: MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY must be set")
        return

    print(f"\nMinIO Endpoint: {MINIO_ENDPOINT}")
    print(f"Bucket: {MINIO_BUCKET}")
    print(f"Videos Path: {MINIO_VIDEOS_PATH or '(root)'}")
    print(f"Secure: {MINIO_SECURE}")

    # Create clients
    print("\nConnecting to MinIO...")
    minio_client = get_minio_client()
    openai_client = get_openai_client()

    # Check bucket exists
    if not minio_client.bucket_exists(MINIO_BUCKET):
        print(f"Error: Bucket '{MINIO_BUCKET}' does not exist")
        return

    # Get max videos limit - from env or prompt user
    max_videos = MAX_VIDEOS
    if max_videos == 0:
        try:
            user_input = input("\nMax videos to process (0 = all, default=all): ").strip()
            if user_input:
                max_videos = int(user_input)
        except (ValueError, EOFError):
            max_videos = 0

    # List videos
    full_path = (
        f"{MINIO_BUCKET}/{MINIO_VIDEOS_PATH}" if MINIO_VIDEOS_PATH else MINIO_BUCKET
    )
    print(f"\nListing videos in '{full_path}'...")
    video_list = list_videos(minio_client, MINIO_BUCKET, MINIO_VIDEOS_PATH, max_videos)

    if not video_list:
        print("No MP4 videos found in bucket")
        return

    limit_info = f" (limited to {max_videos})" if max_videos > 0 else ""
    print(f"Found {len(video_list)} video(s){limit_info}:")
    for v in video_list:
        print(f"  - {v['object_name']} ({v['size'] / 1024 / 1024:.1f} MB)")

    # Process each video
    processed_videos = []
    total_count = len(video_list)
    processed_count = 0
    start_time = time.monotonic()

    for i, video_info in enumerate(video_list, 1):
        video_start = time.monotonic()
        video_data = process_video(
            minio_client, openai_client, MINIO_BUCKET, video_info, i
        )
        video_elapsed = time.monotonic() - video_start

        if video_data:
            processed_videos.append(video_data)
            processed_count += 1

        elapsed_total = time.monotonic() - start_time
        avg_per_video = (elapsed_total / processed_count) if processed_count else 0.0
        remaining_videos = total_count - processed_count
        eta_remaining = avg_per_video * remaining_videos if processed_count else 0.0

        print(
            f"  ⏱ Time this video: {format_eta(video_elapsed)} | "
            f"Elapsed: {format_eta(elapsed_total)} | "
            f"ETA: {format_eta(eta_remaining)} "
            f"({processed_count}/{total_count})"
        )

    # Save results
    if processed_videos:
        save_videos_json(processed_videos)

        # Count total topics and keywords
        total_topics = sum(len(v.get("topics", [])) for v in processed_videos)
        total_keywords = sum(len(v.get("keywords", [])) for v in processed_videos)

        print(
            f"\nSuccessfully processed {len(processed_videos)}/{len(video_list)} videos"
        )
        print(f"Total topics: {total_topics}, Total keywords: {total_keywords}")
    else:
        print("\nNo videos were successfully processed")

    print("\nDone!")


if __name__ == "__main__":
    main()
