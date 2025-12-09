# Physics Learning Assistant

Aplikasi tutor fisika interaktif menggunakan OpenAI Realtime API untuk percakapan suara real-time dengan video pembelajaran.

## Features

- **Voice Chat** - Percakapan suara real-time dengan AI tutor menggunakan OpenAI Realtime API + WebRTC
- **Video Learning** - Video pembelajaran fisika dengan subtitle otomatis
- **Topic Search** - Pencarian video berdasarkan topik/kata kunci (instant, tanpa API call)
- **Video Navigation** - Navigasi ke timestamp tertentu via voice command
- **Transcript Access** - AI dapat membaca dan menjelaskan isi video di setiap detik

## Tech Stack

- **Frontend**: Streamlit + HTML/JavaScript (WebRTC)
- **AI Voice**: OpenAI Realtime API (gpt-4o-realtime-preview)
- **Transcription**: OpenAI Whisper API
- **Video Storage**: MinIO (S3-compatible)
- **Search**: Topic-based keyword matching (client-side)

## Setup

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` ke `.env` dan isi kredensial:

```bash
cp .env.example .env
```

```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# MinIO Configuration
MINIO_ENDPOINT=play.min.io
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=physics-videos
MINIO_VIDEOS_PATH=downloads
MINIO_SECURE=true

# Max videos to process (0 = no limit)
MAX_VIDEOS=0
```

### 3. Generate Video Data

Script ini akan:
- Download video dari MinIO
- Transcribe menggunakan Whisper API
- Generate rich topics/keywords menggunakan LLM
- Simpan metadata ke `data/videos.json`

```bash
uv run python generate_data.py
```

Akan muncul prompt untuk memasukkan jumlah maksimal video yang ingin diproses.

### 4. Run Application

```bash
uv run streamlit run app.py
```

Buka http://localhost:8501 di browser.

## Usage

1. Klik **"Mulai Percakapan"** untuk memulai voice chat
2. Bicara dengan AI tutor dalam Bahasa Indonesia
3. Contoh perintah:
   - "Saya mau belajar hukum newton"
   - "Jelaskan isi video di detik 60"
   - "Pindah ke menit 2"

## Project Structure

```
.
├── app.py              # Main Streamlit application
├── generate_data.py    # Video transcription & metadata generator
├── data/
│   ├── videos.json     # Video metadata with topics/keywords
│   └── subtitles/      # VTT subtitle files
├── .env.example        # Environment variables template
├── pyproject.toml      # Python dependencies
└── README.md
```

## How Search Works

Pencarian menggunakan **topic-based matching** yang berjalan di browser:

1. Setiap video memiliki 30-50 topics/keywords yang di-generate oleh LLM
2. Query user di-match dengan topics, keywords, dan title
3. Video di-score berdasarkan jumlah keyword match
4. Hasil instant tanpa API call (WebRTC tetap connected)

## License

MIT
