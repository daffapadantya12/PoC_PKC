import os
from pathlib import Path
import tempfile

import streamlit as st
import litellm
import re

try:
    from minio import Minio
except Exception:
    Minio = None


def _clean_endpoint(endpoint_raw: str | None) -> str | None:
    if not endpoint_raw:
        return None
    endpoint_clean = endpoint_raw.replace("https://", "").replace("http://", "")
    endpoint_clean = endpoint_clean.split("/")[0]
    return endpoint_clean


def get_minio_client() -> object | None:
    if Minio is None:
        return None
    endpoint_raw = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    secure = os.getenv("MINIO_SECURE", "true").lower() == "true"
    if not (endpoint_raw and access_key and secret_key):
        return None
    endpoint = _clean_endpoint(endpoint_raw)
    try:
        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        bucket = os.getenv("MINIO_BUCKET", "pkc")
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
        except Exception:
            pass
        return client
    except Exception:
        return None


def list_minio_videos(prefix: str = "downloads/") -> list[str]:
    client = st.session_state.get("minio_client") or get_minio_client()
    if not client:
        return []
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".wav"}
    keys: list[str] = []
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            name = obj.object_name
            if Path(name).suffix.lower() in video_exts:
                keys.append(name)
    except Exception:
        return []
    return keys


def get_minio_public_url(key: str) -> str:
    base = os.getenv("MINIO_PUBLIC_BASE")
    if not base:
        endpoint_raw = os.getenv("MINIO_ENDPOINT", "")
        domain = _clean_endpoint(endpoint_raw) or ""
        bucket = os.getenv("MINIO_BUCKET", "pkc")
        base = f"https://{domain}/{bucket}"
    base = base.rstrip("/")
    return f"{base}/{key}"


def download_minio_object_to_tmp(key: str) -> str:
    client = st.session_state.get("minio_client") or get_minio_client()
    if not client:
        raise RuntimeError("MinIO client not available")
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    tmp_dir = Path(tempfile.gettempdir()) / "plmvp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / Path(key).name
    try:
        response = client.get_object(bucket, key)
        with open(local_path, "wb") as f:
            data = response.read()
            f.write(data)
        response.close()
        response.release_conn()
        return str(local_path)
    except Exception as e:
        raise RuntimeError(f"Failed download: {e}")


def _format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs_int = int(seconds % 60)
    msec = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs_int:02d},{msec:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg["start"]) 
        end = _format_timestamp(seg["end"]) 
        text = seg["text"]
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def translate_texts_to_indonesian(texts: list[str]) -> list[str]:
    if not texts:
        return []
    system = (
        "You are a professional translator. Translate to Indonesian. "
        "Return only the translated text lines, in order, one per line. "
        "Do not add numbering."
    )
    joined = "\n".join(texts)
    try:
        resp = litellm.completion(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_base=os.getenv("LLM_API_BASE", None),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": joined},
            ],
            temperature=0,
        )
        output = resp.choices[0].message["content"].strip()
        lines = [l.strip() for l in output.split("\n") if l.strip()]
        if len(lines) == len(texts):
            return lines
        translated: list[str] = []
        for t in texts:
            r = litellm.completion(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                api_base=os.getenv("LLM_API_BASE", None),
                messages=[
                    {"role": "system", "content": "Translate to Indonesian. Output only translation."},
                    {"role": "user", "content": t},
                ],
                temperature=0,
            )
            translated.append(r.choices[0].message["content"].strip())
        return translated
    except Exception:
        return texts


@st.cache_resource
def get_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError(f"faster-whisper not installed: {e}")
    model_size = os.getenv("WHISPER_MODEL", "tiny")  # default to tiny to reduce crashes
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_with_faster_whisper(audio_path: str) -> list[dict]:
    model = get_whisper_model()
    segments_iter, info = model.transcribe(audio_path, vad_filter=True)
    segments: list[dict] = []
    for seg in segments_iter:
        segments.append({"start": seg.start, "end": seg.end, "text": seg.text})
    return segments


# Local subtitles cache directory
SUBTITLES_DIR = Path("data") / "subtitles"


def _local_srt_path_for_key(key: str) -> Path:
    SUBTITLES_DIR.mkdir(parents=True, exist_ok=True)
    return SUBTITLES_DIR / f"{Path(key).stem}.id.srt"


def _save_local_srt(key: str, srt_content: str) -> Path:
    path = _local_srt_path_for_key(key)
    path.write_text(srt_content, encoding="utf-8")
    return path


def process_minio_video_to_indonesian_srt(key: str, local_path: str) -> tuple[str, str, str]:
    segments = transcribe_with_faster_whisper(local_path)
    texts = [s["text"] for s in segments]
    translated = translate_texts_to_indonesian(texts)
    for i in range(len(segments)):
        segments[i]["text"] = translated[i]
    srt_content = segments_to_srt(segments)

    # Persist locally to avoid re-running Whisper repeatedly
    _save_local_srt(key, srt_content)

    srt_key = f"subtitles/{Path(key).stem}.id.srt"
    client = st.session_state.get("minio_client") or get_minio_client()
    if client:
        import io
        bucket = os.getenv("MINIO_BUCKET", "pkc")
        data_bytes = srt_content.encode("utf-8")
        client.put_object(bucket, srt_key, io.BytesIO(data_bytes), length=len(data_bytes), content_type="text/plain")
    subtitle_url = get_minio_public_url(srt_key)
    return srt_content, srt_key, subtitle_url


def build_video_player_with_subtitles(video_url: str, subtitle_url: str | None) -> str:
    track_html = (
        f'<track src="{subtitle_url}" kind="subtitles" srclang="id" label="Bahasa Indonesia" default>'
        if subtitle_url else ""
    )
    return f"""
    <video width="100%" height="480" controls crossorigin="anonymous">
        <source src="{video_url}" type="video/mp4">
        {track_html}
    </video>
    """


def object_exists(client, bucket: str, key: str) -> bool:
    try:
        client.stat_object(bucket, key)
        return True
    except Exception:
        return False


def ensure_subtitle_for_key(key: str) -> tuple[str | None, str | None]:
    client = st.session_state.get("minio_client") or get_minio_client()
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    srt_key = f"subtitles/{Path(key).stem}.id.srt"

    # 1) Local cache first
    local_srt = _local_srt_path_for_key(key)
    if local_srt.exists():
        # Upload to MinIO if missing, but do NOT transcribe again
        if client and not object_exists(client, bucket, srt_key):
            import io
            data_bytes = local_srt.read_bytes()
            try:
                client.put_object(bucket, srt_key, io.BytesIO(data_bytes), length=len(data_bytes), content_type="text/plain")
            except Exception:
                pass
        # Return URL if available; otherwise None (UI can handle gracefully)
        subtitle_url = get_minio_public_url(srt_key) if client else None
        return subtitle_url, srt_key

    # 2) If remote already exists, use it
    if client and object_exists(client, bucket, srt_key):
        return get_minio_public_url(srt_key), srt_key

    # 3) Missing locally and remotely; do NOT transcribe here (lazy)
    return None, None


def batch_ensure_subtitles(keys: list[str]) -> list[dict]:
    client = st.session_state.get("minio_client") or get_minio_client()
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    results: list[dict] = []

    for key in keys:
        srt_key = f"subtitles/{Path(key).stem}.id.srt"
        local_srt = _local_srt_path_for_key(key)

        if local_srt.exists():
            status = "local_exists"
            subtitle_url = None
            # Upload if missing remotely
            if client and not object_exists(client, bucket, srt_key):
                import io
                data_bytes = local_srt.read_bytes()
                try:
                    client.put_object(bucket, srt_key, io.BytesIO(data_bytes), length=len(data_bytes), content_type="text/plain")
                    status = "uploaded"
                    subtitle_url = get_minio_public_url(srt_key)
                except Exception as e:
                    results.append({"key": key, "status": "error", "error": str(e)})
                    continue
            else:
                # Remote already has it
                if client:
                    subtitle_url = get_minio_public_url(srt_key)
            results.append({"key": key, "status": status, "subtitle_key": srt_key, "subtitle_url": subtitle_url})
            continue

        # No local SRT; do not transcribe here
        if client and object_exists(client, bucket, srt_key):
            results.append({"key": key, "status": "remote_exists", "subtitle_key": srt_key, "subtitle_url": get_minio_public_url(srt_key)})
        else:
            results.append({"key": key, "status": "missing"})

    return results


def _hash_token64(token: str) -> int:
    import hashlib
    h = hashlib.sha1(token.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def compute_simhash(text: str) -> int:
    tokens = [t for t in re.findall(r"\w+", text.lower()) if t]
    if not tokens:
        return 0
    from collections import Counter
    counts = Counter(tokens)
    bits = [0] * 64
    for tok, w in counts.items():
        hv = _hash_token64(tok)
        for i in range(64):
            if (hv >> i) & 1:
                bits[i] += w
            else:
                bits[i] -= w
    out = 0
    for i in range(64):
        if bits[i] > 0:
            out |= (1 << i)
    return out


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def search_minio_videos_by_query(query: str, keys: list[str], top_k: int = 20) -> list[str]:
    if not query:
        return keys
    q = query.lower().strip()
    # Prefer substring matches first
    substr = [k for k in keys if q in Path(k).stem.lower()]
    others = [k for k in keys if k not in substr]
    # Rank others by simhash distance
    qh = compute_simhash(q)
    ranked = sorted(others, key=lambda k: hamming_distance(qh, compute_simhash(Path(k).stem)))
    return (substr + ranked)[:top_k]


def list_text_subtitles(prefix: str = "subtitles/") -> list[str]:
    """List .txt subtitle documents stored in MinIO under given prefix."""
    client = st.session_state.get("minio_client") or get_minio_client()
    if not client:
        return []
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    keys: list[str] = []
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            name = obj.object_name
            if Path(name).suffix.lower() == ".txt":
                keys.append(name)
    except Exception:
        return []
    return keys


def get_text_subtitle_content(key: str) -> str:
    """Download and return the text content of a MinIO subtitle .txt."""
    client = st.session_state.get("minio_client") or get_minio_client()
    if not client:
        return ""
    bucket = os.getenv("MINIO_BUCKET", "pkc")
    try:
        response = client.get_object(bucket, key)
        data = response.read()
        response.close()
        response.release_conn()
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def find_video_key_by_stem(stem: str, prefix: str = "downloads/") -> str | None:
    """Find a video key in MinIO with a filename stem matching the provided stem."""
    keys = list_minio_videos(prefix=prefix)
    # Exact stem match first
    for k in keys:
        if Path(k).stem == stem:
            return k
    # Fallback: substring match
    s = stem.lower()
    for k in keys:
        if s in Path(k).stem.lower():
            return k
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MinIO Whisper utilities")
    parser.add_argument("--batch", action="store_true", help="Transcribe all MinIO videos to local SRT cache")
    parser.add_argument("--prefix", default=os.getenv("MINIO_PREFIX", "downloads"), help="MinIO prefix to scan (default: downloads)")
    args = parser.parse_args()

    if args.batch:
        prefix = args.prefix.strip("/")
        keys = list_minio_videos(prefix=f"{prefix}/")
        print(f"Found {len(keys)} video(s) under '{prefix}/'.")
        for key in keys:
            try:
                if _local_srt_path_for_key(key).exists():
                    print(f"[skip] {key} — local SRT exists")
                    continue
                local_path = download_minio_object_to_tmp(key)
                process_minio_video_to_indonesian_srt(key, local_path)
                print(f"[ok] {key} — transcribed & cached locally")
            except Exception as e:
                print(f"[error] {key}: {e}")
    else:
        print("Usage: python minio_whisper.py --batch [--prefix downloads]")