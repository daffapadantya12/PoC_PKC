"""
Physics Learning App with OpenAI Realtime API

A Streamlit application that provides an interactive physics tutor
using OpenAI Realtime API for real-time voice conversations.

The audio is handled entirely in JavaScript using WebRTC and the
OpenAI Realtime API WebSocket connection directly from the browser.

Usage:
    uv run streamlit run app.py
"""

import base64
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DATA_DIR = Path("data")
VIDEOS_FILE = DATA_DIR / "videos.json"
SUBTITLES_DIR = DATA_DIR / "subtitles"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# =============================================================================
# Data Loading Functions
# =============================================================================

@st.cache_data
def load_videos_data() -> dict:
    """Load video data from JSON file."""
    if not VIDEOS_FILE.exists():
        return {"videos": [], "metadata": {}}
    try:
        with open(VIDEOS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"videos": [], "metadata": {}}


def get_subtitle_data(subtitle_file: str | None) -> str | None:
    """Get base64 encoded subtitle data."""
    if not subtitle_file:
        return None

    subtitle_path = DATA_DIR / subtitle_file
    if subtitle_path.exists():
        with open(subtitle_path, encoding="utf-8") as f:
            vtt_content = f.read()
        encoded = base64.b64encode(vtt_content.encode()).decode()
        return f"data:text/vtt;base64,{encoded}"

    return None


# =============================================================================
# Main JavaScript Component (Voice Chat + Video Player)
# =============================================================================

def get_full_app_html(api_key: str, videos_data: list[dict]) -> str:
    """Generate the complete HTML/JS application."""

    # Build video info with subtitles and full transcript with timestamps
    video_info = []
    for v in videos_data:
        subtitle_url = get_subtitle_data(v.get("subtitle_file"))

        # Build transcript with timestamps for AI to reference
        transcript_segments = v.get("transcript", [])
        transcript_with_time = []
        for seg in transcript_segments:
            start = int(seg.get("start", 0))
            end = int(seg.get("end", 0))
            text = seg.get("text", "")
            transcript_with_time.append({
                "start": start,
                "end": end,
                "text": text
            })

        video_info.append({
            "id": v.get("id"),
            "title": v.get("title"),
            "topics": v.get("topics", []),
            "keywords": v.get("keywords", []),
            "duration": v.get("duration_formatted", ""),
            "duration_seconds": v.get("duration", 0),
            "url": v.get("url", ""),
            "subtitle_url": subtitle_url,
            "transcript": transcript_with_time,
        })

    videos_json = json.dumps(video_info, ensure_ascii=False)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
        }}

        .app-container {{
            display: flex;
            gap: 20px;
            padding: 16px;
            height: 100vh;
        }}

        .chat-panel {{
            width: 35%;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .panel-title {{
            font-size: 18px;
            font-weight: 600;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .control-buttons {{
            display: flex;
            gap: 12px;
        }}

        .btn {{
            padding: 12px 20px;
            border: none;
            border-radius: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
            justify-content: center;
        }}

        .btn-start {{
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        }}

        .btn-start:hover:not(:disabled) {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
        }}

        .btn-stop {{
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
        }}

        .btn-stop:hover:not(:disabled) {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
        }}

        .btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }}

        .status-indicator {{
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            display: inline-block;
            width: fit-content;
        }}

        .status-disconnected {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}

        .status-connecting {{
            background: rgba(251, 191, 36, 0.2);
            color: #f59e0b;
        }}

        .status-connected {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }}

        .status-speaking {{
            background: rgba(99, 102, 241, 0.2);
            color: #6366f1;
            animation: pulse 1.5s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}

        .transcript-container {{
            background: #1e293b;
            border-radius: 12px;
            padding: 16px;
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }}

        .transcript-container::-webkit-scrollbar {{
            width: 6px;
        }}

        .transcript-container::-webkit-scrollbar-track {{
            background: #0f172a;
            border-radius: 3px;
        }}

        .transcript-container::-webkit-scrollbar-thumb {{
            background: #475569;
            border-radius: 3px;
        }}

        .transcript-title {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 12px;
            font-weight: 600;
        }}

        .transcripts {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            flex: 1;
            overflow-y: auto;
        }}

        .message {{
            padding: 10px 14px;
            border-radius: 12px;
            max-width: 90%;
            word-wrap: break-word;
            font-size: 14px;
            line-height: 1.4;
        }}

        .message-user {{
            background: #6366f1;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }}

        .message-assistant {{
            background: #334155;
            color: #f8fafc;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }}

        .empty-state {{
            color: #64748b;
            text-align: center;
            padding: 40px 20px;
            font-size: 14px;
        }}

        .video-panel {{
            width: 65%;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .video-title {{
            font-size: 18px;
            font-weight: 600;
        }}

        .video-meta {{
            color: #94a3b8;
            font-size: 13px;
        }}

        .video-container {{
            background: #1e293b;
            border-radius: 16px;
            padding: 16px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}

        .video-wrapper {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        video {{
            width: 100%;
            max-height: 100%;
            border-radius: 12px;
            background: #000;
        }}

        .welcome-state {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            padding: 40px;
        }}

        .welcome-icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}

        .welcome-title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 12px;
        }}

        .welcome-text {{
            color: #94a3b8;
            font-size: 14px;
            line-height: 1.6;
            max-width: 400px;
        }}

        .visualizer {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            height: 30px;
            margin: 8px 0;
        }}

        .visualizer-bar {{
            width: 4px;
            background: #6366f1;
            border-radius: 2px;
            transition: height 0.1s ease;
        }}

        .search-info {{
            background: rgba(99, 102, 241, 0.1);
            border-left: 3px solid #6366f1;
            padding: 8px 12px;
            border-radius: 0 8px 8px 0;
            font-size: 12px;
            color: #94a3b8;
            margin-top: 8px;
        }}
    </style>
</head>
<body>
    <div class="app-container">
        <div class="chat-panel">
            <div class="panel-title">🎙️ Voice Chat</div>

            <div class="control-buttons">
                <button id="startBtn" class="btn btn-start" onclick="startConversation()">
                    🎙️ Mulai Bicara
                </button>
                <button id="stopBtn" class="btn btn-stop" onclick="stopConversation()" disabled>
                    ⏹️ Hentikan
                </button>
            </div>

            <div id="status" class="status-indicator status-disconnected">
                🔴 Tidak terhubung
            </div>

            <div class="visualizer" id="visualizer" style="display: none;">
                <div class="visualizer-bar" style="height: 8px;"></div>
                <div class="visualizer-bar" style="height: 16px;"></div>
                <div class="visualizer-bar" style="height: 12px;"></div>
                <div class="visualizer-bar" style="height: 20px;"></div>
                <div class="visualizer-bar" style="height: 14px;"></div>
                <div class="visualizer-bar" style="height: 18px;"></div>
                <div class="visualizer-bar" style="height: 10px;"></div>
            </div>

            <div class="transcript-container">
                <div class="transcript-title">💬 Percakapan</div>
                <div class="transcripts" id="transcripts">
                    <div class="empty-state">
                        Klik "Mulai Bicara" untuk memulai percakapan dengan AI tutor...
                    </div>
                </div>
            </div>
        </div>

        <div class="video-panel">
            <div>
                <div class="video-title" id="videoTitle">📺 Video Learning</div>
                <div class="video-meta" id="videoMeta"></div>
            </div>

            <div class="video-container">
                <div class="video-wrapper" id="videoWrapper">
                    <div class="welcome-state" id="welcomeState">
                        <div class="welcome-icon">🔬</div>
                        <div class="welcome-title">Physics Learning Assistant</div>
                        <div class="welcome-text">
                            1. Klik tombol <b>Mulai Bicara</b><br>
                            2. Izinkan akses mikrofon<br>
                            3. Bicara tentang topik fisika<br><br>
                            <b>Coba katakan:</b> "Saya mau belajar tentang Hukum Newton"
                        </div>
                    </div>
                    <video id="mainVideo" controls style="display: none;">
                        Your browser does not support video.
                    </video>
                </div>
                <div class="search-info" id="searchInfo" style="display: none;"></div>
            </div>
        </div>
    </div>

    <script>
    const API_KEY = '{api_key}';
    const VIDEOS_DATA = {videos_json};

    let peerConnection = null;
    let dataChannel = null;
    let audioElement = null;
    let mediaStream = null;
    let isConnected = false;
    let currentVideoId = null;

    const statusEl = document.getElementById('status');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const transcriptsEl = document.getElementById('transcripts');
    const visualizerEl = document.getElementById('visualizer');
    const videoEl = document.getElementById('mainVideo');
    const welcomeEl = document.getElementById('welcomeState');
    const videoTitleEl = document.getElementById('videoTitle');
    const videoMetaEl = document.getElementById('videoMeta');
    const searchInfoEl = document.getElementById('searchInfo');

    function updateStatus(status, text) {{
        statusEl.className = 'status-indicator status-' + status;
        statusEl.textContent = text;
    }}

    function addTranscript(role, text) {{
        const emptyState = transcriptsEl.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        const msgDiv = document.createElement('div');
        msgDiv.className = 'message message-' + role;
        msgDiv.textContent = text;
        transcriptsEl.appendChild(msgDiv);
        transcriptsEl.scrollTop = transcriptsEl.scrollHeight;
    }}

    function animateVisualizer() {{
        if (!isConnected) return;

        const bars = visualizerEl.querySelectorAll('.visualizer-bar');
        bars.forEach(bar => {{
            const height = Math.random() * 25 + 5;
            bar.style.height = height + 'px';
        }});

        requestAnimationFrame(() => {{
            setTimeout(animateVisualizer, 100);
        }});
    }}

    function showVideo(videoData, timestamp = 0) {{
        if (!videoData || !videoData.url) return;

        currentVideoId = videoData.id;

        videoTitleEl.textContent = '📺 ' + videoData.title;
        videoMetaEl.textContent = 'Duration: ' + videoData.duration + ' | Topics: ' + (videoData.topics || []).slice(0, 3).join(', ');

        welcomeEl.style.display = 'none';
        videoEl.style.display = 'block';

        videoEl.src = videoData.url;

        while (videoEl.firstChild) {{
            videoEl.removeChild(videoEl.firstChild);
        }}

        if (videoData.subtitle_url) {{
            const track = document.createElement('track');
            track.kind = 'subtitles';
            track.src = videoData.subtitle_url;
            track.srclang = 'id';
            track.label = 'Indonesian';
            track.default = true;
            videoEl.appendChild(track);
        }}

        videoEl.load();
        videoEl.addEventListener('loadedmetadata', function onLoad() {{
            videoEl.currentTime = timestamp;
            videoEl.play().catch(e => console.log('Autoplay prevented'));
            if (videoEl.textTracks.length > 0) {{
                videoEl.textTracks[0].mode = 'showing';
            }}
            videoEl.removeEventListener('loadedmetadata', onLoad);
        }});
    }}

    function navigateToTimestamp(timestamp) {{
        if (videoEl.src) {{
            videoEl.currentTime = timestamp;
            videoEl.play().catch(e => console.log('Autoplay prevented'));
        }}
    }}

    function sendFunctionResult(callId, result) {{
        if (dataChannel && dataChannel.readyState === 'open') {{
            const event = {{
                type: 'conversation.item.create',
                item: {{
                    type: 'function_call_output',
                    call_id: callId,
                    output: JSON.stringify(result)
                }}
            }};
            dataChannel.send(JSON.stringify(event));
            dataChannel.send(JSON.stringify({{ type: 'response.create' }}));
        }}
    }}

    function handleNavigateVideo(args, callId) {{
        const timestamp = args.timestamp || 0;
        const videoId = args.video_id;

        console.log('Navigate video:', videoId, 'timestamp:', timestamp);

        if (videoId && videoId !== currentVideoId) {{
            const video = VIDEOS_DATA.find(v => v.id === videoId);
            if (video) {{
                showVideo(video, timestamp);
            }}
        }} else {{
            navigateToTimestamp(timestamp);
        }}

        sendFunctionResult(callId, {{
            success: true,
            message: 'Video berpindah ke detik ' + timestamp
        }});
    }}

    // Topic-based search - instant, no API call, no page reload
    function searchByTopics(query) {{
        if (!query || !VIDEOS_DATA || VIDEOS_DATA.length === 0) {{
            return [];
        }}

        const queryLower = query.toLowerCase();
        const queryWords = queryLower.split(/\\s+/).filter(w => w.length > 1);

        // Score each video
        const scored = VIDEOS_DATA.map(video => {{
            let score = 0;

            // Combine all searchable text
            const topics = (video.topics || []).join(' ').toLowerCase();
            const keywords = (video.keywords || []).join(' ').toLowerCase();
            const title = (video.title || '').toLowerCase();
            const allText = topics + ' ' + keywords + ' ' + title;

            // Check for exact phrase match (highest score)
            if (allText.includes(queryLower)) {{
                score += 20;
            }}

            // Check for word matches
            queryWords.forEach(word => {{
                // Exact word match in topics
                if (topics.includes(word)) {{
                    score += 10;
                }}

                // Exact word match in keywords
                if (keywords.includes(word)) {{
                    score += 8;
                }}

                // Title match (high priority)
                if (title.includes(word)) {{
                    score += 15;
                }}

                // Partial match (prefix)
                const allWords = allText.split(/\\s+/);
                allWords.forEach(w => {{
                    if (w.startsWith(word) && w !== word) {{
                        score += 3;
                    }}
                }});
            }});

            return {{ ...video, score }};
        }});

        // Filter and sort by score
        return scored
            .filter(v => v.score > 0)
            .sort((a, b) => b.score - a.score);
    }}

    // Handle search video - instant topic-based search
    function handleSearchVideo(args, callId) {{
        const query = args.query || '';
        console.log('Topic-based search:', query);

        const results = searchByTopics(query);

        if (results.length > 0) {{
            const best = results[0];
            console.log('Best match:', best.title, 'score:', best.score);

            showVideo(best, 0);

            // Show search info
            searchInfoEl.style.display = 'block';
            const topicsPreview = (best.topics || []).slice(0, 5).join(', ');
            searchInfoEl.innerHTML = '🔍 <b>Ditemukan:</b> ' + best.title + ' (Topics: ' + topicsPreview + ')';

            sendFunctionResult(callId, {{
                success: true,
                video_id: best.id,
                title: best.title,
                topics: best.topics,
                score: best.score,
                message: 'Menemukan video: ' + best.title + '. Video ini membahas tentang: ' + topicsPreview
            }});
        }} else {{
            sendFunctionResult(callId, {{
                success: false,
                message: 'Tidak menemukan video yang relevan untuk: ' + query + '. Coba kata kunci lain.'
            }});
        }}
    }}

    function handleGetVideoContent(args, callId) {{
        const timestamp = args.timestamp || 0;
        const videoId = args.video_id || currentVideoId;

        console.log('Get video content at:', timestamp, 'for video:', videoId);

        const video = VIDEOS_DATA.find(v => v.id === videoId);
        if (!video) {{
            sendFunctionResult(callId, {{
                success: false,
                message: 'Video tidak ditemukan'
            }});
            return;
        }}

        const startRange = Math.max(0, timestamp - 10);
        const endRange = timestamp + 10;

        const relevantSegments = (video.transcript || []).filter(seg => {{
            return (seg.start >= startRange && seg.start <= endRange) ||
                   (seg.end >= startRange && seg.end <= endRange) ||
                   (seg.start <= startRange && seg.end >= endRange);
        }});

        if (relevantSegments.length === 0) {{
            let closestSeg = null;
            let minDist = Infinity;
            (video.transcript || []).forEach(seg => {{
                const dist = Math.min(Math.abs(seg.start - timestamp), Math.abs(seg.end - timestamp));
                if (dist < minDist) {{
                    minDist = dist;
                    closestSeg = seg;
                }}
            }});

            if (closestSeg) {{
                relevantSegments.push(closestSeg);
            }}
        }}

        let contentText = '';
        relevantSegments.forEach(seg => {{
            contentText += '[' + formatTime(seg.start) + '-' + formatTime(seg.end) + '] ' + seg.text + '\\n';
        }});

        navigateToTimestamp(timestamp);

        sendFunctionResult(callId, {{
            success: true,
            video_id: videoId,
            video_title: video.title,
            timestamp: timestamp,
            content: contentText || 'Tidak ada konten di timestamp ini',
            segments: relevantSegments,
            message: 'Konten video di detik ' + timestamp + ': ' + contentText
        }});
    }}

    function formatTime(seconds) {{
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return mins + ':' + secs.toString().padStart(2, '0');
    }}

    async function startConversation() {{
        try {{
            updateStatus('connecting', '🟡 Menghubungkan...');
            startBtn.disabled = true;

            const tokenResponse = await fetch('https://api.openai.com/v1/realtime/sessions', {{
                method: 'POST',
                headers: {{
                    'Authorization': 'Bearer ' + API_KEY,
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{
                    model: 'gpt-4o-realtime-preview-2024-12-17',
                    voice: 'alloy',
                    instructions: 'Kamu adalah tutor fisika yang ramah dan berpengetahuan untuk anak SD. Kamu membantu siswa belajar dengan video pembelajaran.\\n\\nKEMAMPUAN PENTING:\\n- Kamu BISA melihat dan mengetahui isi video di setiap detik karena kamu punya akses ke transcript video\\n- Gunakan get_video_content(timestamp=X) untuk mengetahui apa yang dibahas di detik tertentu\\n- Gunakan search_video untuk mencari video berdasarkan topik\\n- Kamu adalah guide yang membantu siswa memahami isi video\\n\\nATURAN:\\n1. Gunakan Bahasa Indonesia sederhana\\n2. Jawab dengan detail tapi tetap mudah dipahami anak SD\\n3. SELALU panggil search_video ketika user minta belajar topik baru\\n4. SELALU panggil get_video_content ketika user bertanya tentang isi video di waktu tertentu\\n5. Panggil navigate_video ketika user minta pindah ke detik tertentu\\n\\nCONTOH PENGGUNAAN TOOLS:\\n- User: "Saya mau belajar hukum newton" -> Panggil search_video(query="hukum newton")\\n- User: "Isi detik 60 tentang apa?" -> Panggil get_video_content(timestamp=60), lalu jelaskan isinya\\n- User: "Pindah ke detik 30" -> Panggil navigate_video(timestamp=30)\\n- User: "Di menit 1 membahas apa?" -> Panggil get_video_content(timestamp=60)\\n\\nJANGAN membahas topik di luar fisika.\\n\\nSTRATEGI PEMAHAMAN INTUITIF:\\n- Setelah memberi penjelasan, SELALU ajukan 1 pertanyaan singkat untuk mengecek pemahaman siswa.\\n- Gunakan gaya ramah dan memotivasi. Contoh: "Keren kan Hukum Newton? Nah, sekarang untuk menguji kamu aku mau bertanya: jika gaya didobel, apa yang terjadi pada percepatan?"\\n- Jika jawaban belum tepat, beri umpan balik singkat, analogi sehari-hari, lalu tanyakan pertanyaan lanjutan.\\n- Jika jawaban benar, beri pujian singkat dan arahkan ke konsep berikutnya dengan contoh singkat.',
                    tools: [
                        {{
                            type: 'function',
                            name: 'navigate_video',
                            description: 'Navigasi video ke timestamp tertentu. Panggil ini saat user minta pindah ke detik/menit tertentu.',
                            parameters: {{
                                type: 'object',
                                properties: {{
                                    video_id: {{ type: 'string', description: 'ID video (opsional)' }},
                                    timestamp: {{ type: 'integer', description: 'Waktu dalam detik', minimum: 0 }}
                                }},
                                required: ['timestamp']
                            }}
                        }},
                        {{
                            type: 'function',
                            name: 'search_video',
                            description: 'Cari video berdasarkan topik/kata kunci. WAJIB panggil ini saat user minta belajar topik baru.',
                            parameters: {{
                                type: 'object',
                                properties: {{
                                    query: {{ type: 'string', description: 'Kata kunci pencarian topik fisika' }}
                                }},
                                required: ['query']
                            }}
                        }},
                        {{
                            type: 'function',
                            name: 'get_video_content',
                            description: 'Dapatkan isi/konten video di timestamp tertentu. WAJIB panggil ini saat user bertanya tentang apa yang dibahas di detik/menit tertentu.',
                            parameters: {{
                                type: 'object',
                                properties: {{
                                    video_id: {{ type: 'string', description: 'ID video (opsional)' }},
                                    timestamp: {{ type: 'integer', description: 'Waktu dalam detik', minimum: 0 }}
                                }},
                                required: ['timestamp']
                            }}
                        }}
                    ],
                    input_audio_transcription: {{ model: 'whisper-1' }},
                    turn_detection: {{ type: 'server_vad' }}
                }})
            }});

            if (!tokenResponse.ok) {{
                const errorText = await tokenResponse.text();
                throw new Error('Failed to get session: ' + errorText);
            }}

            const sessionData = await tokenResponse.json();
            const ephemeralKey = sessionData.client_secret.value;

            peerConnection = new RTCPeerConnection();

            audioElement = document.createElement('audio');
            audioElement.autoplay = true;

            peerConnection.ontrack = (event) => {{
                audioElement.srcObject = event.streams[0];
            }};

            mediaStream = await navigator.mediaDevices.getUserMedia({{
                audio: {{
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }}
            }});

            mediaStream.getTracks().forEach(track => {{
                peerConnection.addTrack(track, mediaStream);
            }});

            dataChannel = peerConnection.createDataChannel('oai-events');

            dataChannel.onopen = () => {{
                console.log('Data channel opened');
                isConnected = true;
                updateStatus('connected', '🟢 Terhubung - Silakan berbicara');
                stopBtn.disabled = false;
                visualizerEl.style.display = 'flex';
                animateVisualizer();
            }};

            dataChannel.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                handleServerEvent(data);
            }};

            dataChannel.onclose = () => {{
                console.log('Data channel closed');
                isConnected = false;
            }};

            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);

            const sdpResponse = await fetch('https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17', {{
                method: 'POST',
                headers: {{
                    'Authorization': 'Bearer ' + ephemeralKey,
                    'Content-Type': 'application/sdp'
                }},
                body: offer.sdp
            }});

            if (!sdpResponse.ok) {{
                throw new Error('Failed to connect to Realtime API');
            }}

            const answerSdp = await sdpResponse.text();
            await peerConnection.setRemoteDescription({{
                type: 'answer',
                sdp: answerSdp
            }});

        }} catch (error) {{
            console.error('Error starting conversation:', error);
            updateStatus('disconnected', '🔴 Error: ' + error.message);
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }}
    }}

    function handleServerEvent(event) {{
        console.log('Server event:', event.type);

        switch (event.type) {{
            case 'conversation.item.input_audio_transcription.completed':
                if (event.transcript) {{
                    addTranscript('user', event.transcript);
                }}
                break;

            case 'response.audio_transcript.done':
                if (event.transcript) {{
                    addTranscript('assistant', event.transcript);
                }}
                break;

            case 'response.function_call_arguments.done':
                const funcName = event.name;
                const callId = event.call_id;
                let args = {{}};

                try {{
                    args = JSON.parse(event.arguments || '{{}}');
                }} catch (e) {{
                    console.error('Failed to parse function args:', e);
                }}

                console.log('Function call:', funcName, args);

                if (funcName === 'navigate_video') {{
                    handleNavigateVideo(args, callId);
                }} else if (funcName === 'search_video') {{
                    handleSearchVideo(args, callId);
                }} else if (funcName === 'get_video_content') {{
                    handleGetVideoContent(args, callId);
                }}
                break;

            case 'input_audio_buffer.speech_started':
                updateStatus('speaking', '🎤 Mendengarkan...');
                break;

            case 'input_audio_buffer.speech_stopped':
                updateStatus('connected', '🟢 Memproses...');
                break;

            case 'response.done':
                updateStatus('connected', '🟢 Terhubung - Silakan berbicara');
                break;

            case 'error':
                console.error('API Error:', event.error);
                updateStatus('disconnected', '🔴 Error: ' + (event.error?.message || 'Unknown'));
                break;
        }}
    }}

    function stopConversation() {{
        isConnected = false;

        if (dataChannel) {{
            dataChannel.close();
            dataChannel = null;
        }}

        if (peerConnection) {{
            peerConnection.close();
            peerConnection = null;
        }}

        if (mediaStream) {{
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }}

        if (audioElement) {{
            audioElement.srcObject = null;
            audioElement = null;
        }}

        updateStatus('disconnected', '🔴 Tidak terhubung');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        visualizerEl.style.display = 'none';
    }}

    </script>
</body>
</html>
    """


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Main application."""
    st.set_page_config(
        page_title="Physics Learning Assistant",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Hide Streamlit UI elements
    st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stApp > header {display: none;}
        .main .block-container {
            padding: 0;
            max-width: 100%;
        }
        iframe {
            border: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Check API key
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY tidak ditemukan di file .env")
        st.info("Silakan copy .env.example ke .env dan isi API key Anda")
        return

    # Load video data
    videos_data = load_videos_data()
    videos_list = videos_data.get("videos", [])

    # Render full app as single HTML component
    # Search is now handled client-side with topic-based matching (no page reload)
    app_html = get_full_app_html(OPENAI_API_KEY, videos_list)
    st.components.v1.html(app_html, height=700, scrolling=False)


if __name__ == "__main__":
    main()
