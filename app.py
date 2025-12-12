import base64
import json
import os
from pathlib import Path

import streamlit as st
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Konfigurasi Path
DATA_DIR = Path("data")
VIDEOS_FILE = DATA_DIR / "videos.json"  # Fallback
VIDEOS_API_URL = "http://localhost:28302/content/cards/ba7a27624af1511010900f501ddea0b7dacb3d3858ce2291efe45eb4245bdf02/raw"
SUBTITLES_DIR = DATA_DIR / "subtitles"
SYSTEM_PROMPT_FILE = Path("system_prompt.md")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


@st.cache_data
def load_videos_data() -> dict:
    """Load video data from API (preferred) or JSON file."""
    # Try fetching from API
    try:
        response = requests.get(VIDEOS_API_URL, timeout=5)
        if response.status_code == 200:
            return response.json()
        print(f"API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"API Connection Error: {e}")

    # Fallback to local file
    if not VIDEOS_FILE.exists():
        return {"videos": [], "metadata": {}}
    try:
        with open(VIDEOS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"videos": [], "metadata": {}}


@st.cache_data
def load_system_prompt() -> str:
    """Load system prompt from markdown file."""
    if not SYSTEM_PROMPT_FILE.exists():
        return "Kamu adalah tutor fisika yang ramah. Bicaralah dengan tempo cepat dan energik."
    try:
        with open(SYSTEM_PROMPT_FILE, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Kamu adalah tutor fisika yang ramah."


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

def get_full_app_html(api_key: str, videos_data: list[dict], system_prompt: str) -> str:
    """Generate the complete HTML/JS application."""

    video_info = []
    for v in videos_data:
        subtitle_url = get_subtitle_data(v.get("subtitle_file"))
        transcript_segments = v.get("transcript", [])
        transcript_with_time = [
            {"start": int(seg.get("start", 0)), "end": int(seg.get("end", 0)), "text": seg.get("text", "")}
            for seg in transcript_segments
        ]
        video_info.append({
            "id": v.get("id"), "title": v.get("title"), "topics": v.get("topics", []),
            "keywords": v.get("keywords", []), "duration": v.get("duration_formatted", ""),
            "duration_seconds": v.get("duration", 0), "url": v.get("url", ""),
            "subtitle_url": subtitle_url, "transcript": transcript_with_time,
        })

    videos_json = json.dumps(video_info, ensure_ascii=False)
    system_prompt_escaped = system_prompt.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <!-- PENTING: Viewport meta tag agar responsif di mobile -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #0f172a; 
            color: #f8fafc; 
            height: 100vh; /* Menggunakan tinggi viewport penuh */
            overflow: hidden; /* Mencegah scroll pada body utama */
        }}
        
        .app-container {{ 
            display: flex; 
            gap: 20px; 
            padding: 16px; 
            height: 100%; 
            width: 100%;
        }}
        
        /* Desktop Layout (Default) */
        .chat-panel {{ 
            width: 35%; 
            display: flex; 
            flex-direction: column; 
            gap: 16px; 
            height: 100%;
        }}
        
        .video-panel {{ 
            width: 65%; 
            display: flex; 
            flex-direction: column; 
            gap: 16px; 
            height: 100%;
        }}

        /* Common Elements */
        .panel-title {{ font-size: 18px; font-weight: 600; color: #f8fafc; display: flex; align-items: center; gap: 8px; flex-shrink: 0; }}
        .control-buttons {{ display: flex; gap: 12px; flex-shrink: 0; }}
        .btn {{ padding: 12px 20px; border: none; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; display: flex; align-items: center; gap: 8px; flex: 1; justify-content: center; }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        
        .status-indicator {{ padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500; display: inline-block; width: fit-content; flex-shrink: 0; }}
        .status-disconnected {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
        .status-connecting {{ background: rgba(251, 191, 36, 0.2); color: #f59e0b; }}
        .status-connected {{ background: rgba(34, 197, 94, 0.2); color: #22c55e; }}
        .status-ai-speaking {{ background: rgba(59, 130, 246, 0.2); color: #3b82f6; }}
        .status-speaking {{ background: rgba(99, 102, 241, 0.2); color: #6366f1; }}
        
        .transcript-container {{ background: #1e293b; border-radius: 12px; padding: 16px; flex: 1; overflow-y: auto; display: flex; flex-direction: column; min-height: 0; }}
        .transcript-title {{ color: #94a3b8; font-size: 14px; margin-bottom: 12px; font-weight: 600; flex-shrink: 0; }}
        .transcripts {{ display: flex; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto; padding-right: 4px; }}
        
        .message {{ padding: 10px 14px; border-radius: 12px; max-width: 90%; word-wrap: break-word; font-size: 14px; }}
        .message-user {{ background: #6366f1; color: white; align-self: flex-end; }}
        .message-assistant {{ background: #334155; color: #f8fafc; align-self: flex-start; }}
        .empty-state {{ color: #64748b; text-align: center; padding: 40px 20px; }}
        
        .video-title {{ font-size: 18px; font-weight: 600; flex-shrink: 0; }}
        .video-meta {{ color: #94a3b8; font-size: 13px; flex-shrink: 0; }}
        .video-container {{ background: #1e293b; border-radius: 16px; padding: 16px; flex: 1; display: flex; flex-direction: column; min-height: 0; }}
        .video-wrapper {{ flex: 1; display: flex; align-items: center; justify-content: center; width: 100%; position: relative; }}
        video {{ width: 100%; max-height: 100%; border-radius: 12px; background: #000; transition: volume 0.5s ease; object-fit: contain; }}
        .welcome-state {{ display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; padding: 20px; }}
        
        .visualizer {{ display: flex; align-items: center; justify-content: center; gap: 4px; height: 30px; margin: 8px 0; flex-shrink: 0; }}
        .visualizer-bar {{ width: 4px; background: #6366f1; border-radius: 2px; transition: height 0.1s ease; }}
        .search-info {{ background: rgba(99, 102, 241, 0.1); border-left: 3px solid #6366f1; padding: 8px 12px; border-radius: 0 8px 8px 0; font-size: 12px; color: #94a3b8; margin-top: 8px; flex-shrink: 0; }}

        /* --- MOBILE RESPONSIVE STYLES --- */
        @media (max-width: 768px) {{
            body {{
                height: 100dvh; /* Dynamic viewport height untuk mobile modern */
            }}
            .app-container {{
                flex-direction: column; /* Ubah layout jadi atas-bawah */
                padding: 10px;
                gap: 10px;
            }}
            
            /* Pada Mobile, Video panel di atas, Chat panel di bawah */
            .video-panel {{
                width: 100%;
                height: 40%; /* Video mengambil 40% layar */
                order: 1; /* Urutan pertama */
                gap: 8px;
            }}
            
            .chat-panel {{
                width: 100%;
                height: 60%; /* Chat mengambil 60% layar */
                order: 2; /* Urutan kedua */
                gap: 10px;
            }}
            
            .video-title {{ font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
            .panel-title {{ font-size: 16px; }}
            .btn {{ padding: 10px 16px; font-size: 13px; }}
            
            .video-container {{ padding: 8px; border-radius: 12px; }}
            .transcript-container {{ padding: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="app-container">
        <div class="chat-panel">
            <div class="panel-title">🎙️ Voice Chat</div>
            <div class="control-buttons">
                <button id="startBtn" class="btn" onclick="startConversation()">Mulai</button>
                <button id="stopBtn" class="btn" onclick="stopConversation()" disabled>Hentikan</button>
            </div>
            <div id="status" class="status-indicator status-disconnected">🔴 Tidak terhubung</div>
            <div class="visualizer" id="visualizer" style="display: none;">
                <div class="visualizer-bar"></div><div class="visualizer-bar"></div><div class="visualizer-bar"></div>
            </div>
            <div class="transcript-container">
                <div class="transcript-title">💬 Percakapan</div>
                <div class="transcripts" id="transcripts"><div class="empty-state">Klik "Mulai" untuk memulai.</div></div>
            </div>
        </div>
        <div class="video-panel">
            <div>
                <div class="video-title" id="videoTitle">📺 Video Belajar</div>
                <div class="video-meta" id="videoMeta">Pilih topik untuk memulai</div>
            </div>
            <div class="video-container">
                <div class="video-wrapper" id="videoWrapper">
                    <div class="welcome-state" id="welcomeState">
                        <h2>Selamat Datang!</h2>
                        <p>AI Tutor Fisika siap membantu. Klik "Mulai" dan tanyakan apa saja!</p>
                    </div>
                    <video id="mainVideo" controls muted style="display: none;"></video>
                </div>
                <div class="search-info" id="searchInfo" style="display: none;"></div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/markdown-it@14.1.0/dist/markdown-it.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <script>
    const API_KEY = '{api_key}';
    const VIDEOS_DATA = {videos_json};
    const SYSTEM_PROMPT = '{system_prompt_escaped}';

    // Initialize Markdown parser
    const md = window.markdownit();

    let peerConnection = null, dataChannel = null, audioElement = null, mediaStream = null;
    let isConnected = false, isAIsTurn = false, currentVideoId = null;
    let originalVideoVolume = 0.0;
    let wasPlayingBeforeSpeech = false;
    let audioContext = null, audioAnalyser = null, audioAnalysisLoop = null;
    
    const statusEl = document.getElementById('status');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const transcriptsEl = document.getElementById('transcripts');
    const videoEl = document.getElementById('mainVideo');
    const welcomeStateEl = document.getElementById('welcomeState');
    const videoTitleEl = document.getElementById('videoTitle');
    const videoMetaEl = document.getElementById('videoMeta');
    const visualizerEl = document.getElementById('visualizer');
    const searchInfoEl = document.getElementById('searchInfo');

    function setMicrophoneEnabled(enabled) {{ if (mediaStream) mediaStream.getAudioTracks().forEach(t => t.enabled = enabled); }}
    function updateStatus(status, text) {{ statusEl.className = `status-indicator status-${{status}}`; statusEl.textContent = text; }}
    
    function renderMessage(text) {{
        // 1. Render Markdown first
        let html = md.render(text);
        
        // 2. Render Block Math: $$...$$ OR \[...\]
        html = html.replace(/(\$\$|\\\\\[)([\\s\\S]*?)(\$\$|\\\\\])/g, (match, open, tex, close) => {{
            try {{ return katex.renderToString(tex, {{ displayMode: true }}); }}
            catch(e) {{ return match; }}
        }});
        
        // 3. Render Inline Math: $...$ OR \(...\)
        html = html.replace(/(\$|\\\\\()([^$\\n]+?)(\$|\\\\\))/g, (match, open, tex, close) => {{
            try {{ return katex.renderToString(tex, {{ displayMode: false }}); }}
            catch(e) {{ return match; }}
        }});
        
        // 4. Fallback: Render ( A = B ) as math if it contains latex symbols
        // Matches ( ... = ... ) or ( ... \ ... ) pattern roughly
        // Escape {{ and }} for f-string
        html = html.replace(/\(\s*([a-zA-Z0-9\s\\._{{}}^]*?=[a-zA-Z0-9\s\\._{{}}^]*?)\s*\)/g, (match, tex) => {{
             try {{ return katex.renderToString(tex, {{ displayMode: false }}); }}
             catch(e) {{ return match; }}
        }});
        // Also catch ( ... \frac ... ) etc even without =
        html = html.replace(/\(\s*(\\[a-zA-Z]+[\\s\\S]*?)\s*\)/g, (match, tex) => {{
             // Only if it looks like latex (starts with backslash command)
             try {{ return katex.renderToString(tex, {{ displayMode: false }}); }}
             catch(e) {{ return match; }}
        }});
        
        return html;
    }}

    function addTranscript(role, text) {{
        const emptyState = transcriptsEl.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        const msgDiv = document.createElement('div');
        msgDiv.className = `message message-${{role}}`; 
        
        // Use innerHTML with rendered content
        msgDiv.innerHTML = renderMessage(text);
        
        transcriptsEl.appendChild(msgDiv); transcriptsEl.scrollTop = transcriptsEl.scrollHeight;
    }}
    function animateVisualizer() {{
        if (!isAIsTurn) {{
            const bars = visualizerEl.querySelectorAll('.visualizer-bar');
            bars.forEach(bar => {{ bar.style.height = `${{Math.random() * 15 + 3}}px`; }});
            requestAnimationFrame(animateVisualizer);
        }}
    }}
    
    function showVideo(videoData, timestamp = 0) {{
        if (!videoData || !videoData.url) return;
        
        if (currentVideoId === videoData.id) {{
            navigateToTimestamp(timestamp);
            if (timestamp > 0) {{
                const minutes = Math.floor(timestamp / 60);
                const seconds = Math.floor(timestamp % 60);
                searchInfoEl.innerHTML = `⏱️ Melompat ke ${{(minutes > 0 ? minutes + 'm ' : '') + seconds + 's'}}`;
                searchInfoEl.style.display = 'block';
            }}
            return; 
        }}

        currentVideoId = videoData.id;
        videoTitleEl.textContent = '📺 ' + videoData.title;
        videoMetaEl.textContent = `Durasi: ${{videoData.duration}} | Topik: ${{videoData.topics.slice(0, 3).join(', ')}}`;
        welcomeStateEl.style.display = 'none';
        videoEl.style.display = 'block';
        videoEl.src = videoData.url;
        
        while (videoEl.firstChild) {{ videoEl.removeChild(videoEl.firstChild); }}
        if (videoData.subtitle_url) {{
            const track = document.createElement('track');
            track.kind = 'subtitles'; track.src = videoData.subtitle_url; track.srclang = 'id';
            track.label = 'Indonesian'; track.default = true;
            videoEl.appendChild(track);
        }}
        
        videoEl.load();
        
        videoEl.addEventListener('loadedmetadata', () => {{
            if (timestamp > 0) {{
                videoEl.currentTime = timestamp;
            }}
            if (isAIsTurn) {{
                videoEl.muted = true;
                videoEl.playbackRate = 0.5;
            }} else {{
                videoEl.muted = false;
                videoEl.playbackRate = 1.0;
            }}
            videoEl.play().catch(e => console.error("Autoplay dicegah:", e));
        }}, {{ once: true }});
    }}

    function navigateToTimestamp(timestamp) {{ 
        if (videoEl.src) {{ 
            videoEl.currentTime = timestamp; 
            videoEl.play().catch(e => console.error("Autoplay dicegah:", e)); 
        }} 
    }}

    function sendFunctionResult(callId, result) {{
        if (dataChannel?.readyState === 'open') {{
            dataChannel.send(JSON.stringify({{ type: 'conversation.item.create', item: {{ type: 'function_call_output', call_id: callId, output: JSON.stringify(result) }} }}));
            dataChannel.send(JSON.stringify({{ type: 'response.create' }}));
        }}
    }}

    function setupAudioAnalysis(stream) {{
        try {{
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            audioAnalyser = audioContext.createAnalyser();
            audioAnalyser.fftSize = 256;
            source.connect(audioAnalyser);
            
            const dataArray = new Uint8Array(audioAnalyser.frequencyBinCount);
            let lastSpeechTime = Date.now();
            
            function checkAudioVolume() {{
                if (!audioAnalyser) return;
                audioAnalyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for(let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                const average = sum / dataArray.length;
                
                if (average > 10) {{
                    lastSpeechTime = Date.now();
                    if (!isAIsTurn) {{
                        isAIsTurn = true;
                        updateStatus('ai-speaking', '🔵 AI Berbicara...'); 
                        // setMicrophoneEnabled(false); // REMOVED: Allow barge-in
                        visualizerEl.style.display = 'none';
                        if (!videoEl.paused) {{
                            videoEl.muted = true;
                            videoEl.playbackRate = 0.5;
                        }}
                    }}
                    if (!videoEl.paused && (videoEl.playbackRate !== 0.5 || !videoEl.muted)) {{
                        videoEl.playbackRate = 0.5;
                        videoEl.muted = true;
                    }}
                }} else {{
                    if (isAIsTurn && (Date.now() - lastSpeechTime > 800)) {{
                        isAIsTurn = false;
                        updateStatus('connected', '🟢 Giliran Anda');
                        setMicrophoneEnabled(true);
                        videoEl.muted = false;
                        videoEl.playbackRate = 1.0;
                    }}
                    if (!isAIsTurn && !videoEl.paused && videoEl.playbackRate !== 1.0) {{
                        videoEl.playbackRate = 1.0;
                        videoEl.muted = false;
                    }}
                }}
                audioAnalysisLoop = requestAnimationFrame(checkAudioVolume);
            }}
            checkAudioVolume();
        }} catch (e) {{
            console.error("Gagal setup audio analysis:", e);
        }}
    }}

    function searchContentAndFindTimestamp(query) {{
        if (!query) return null;
        const queryLower = query.toLowerCase();
        const cleanQuery = queryLower.replace(/[^\w\s]/gi, '');
        const queryTerms = cleanQuery.split(/\s+/).filter(w => w.length > 2);

        let bestMatch = {{ video: null, timestamp: 0, score: 0, matchedText: '' }};

        for (const video of VIDEOS_DATA) {{
            let videoBaseScore = 0;
            if (video.title) {{
                const titleLower = video.title.toLowerCase();
                if (titleLower.includes(queryLower)) videoBaseScore = 10;
                else if (queryTerms.some(term => titleLower.includes(term))) videoBaseScore = 5;
            }}
            if (!video.transcript || video.transcript.length === 0) {{
                if (videoBaseScore > bestMatch.score) bestMatch = {{ video: video, timestamp: 0, score: videoBaseScore, matchedText: "Judul Video" }};
                continue;
            }}
            for (const segment of video.transcript) {{
                if (!segment.text) continue;
                const textLower = segment.text.toLowerCase();
                let segmentScore = videoBaseScore; 
                if (textLower.includes(cleanQuery) || textLower.includes(queryLower)) segmentScore += 100; 
                else {{
                    let hitCount = 0;
                    queryTerms.forEach(term => {{ if (textLower.includes(term)) hitCount++; }});
                    if (hitCount > 0) segmentScore += (hitCount * hitCount * 5);
                }}
                if (segmentScore > bestMatch.score) bestMatch = {{ video: video, timestamp: segment.start, score: segmentScore, matchedText: segment.text }};
            }}
        }}
        return bestMatch.score > 0 ? bestMatch : null;
    }}

    function handleNavigateVideo(args, callId) {{
        const timestamp = args.timestamp || 0;
        navigateToTimestamp(timestamp);
        sendFunctionResult(callId, {{ success: true, message: `Video berpindah ke detik ${{timestamp}}` }});
    }}

    function handleSearchVideo(args, callId) {{
        const query = args.query || '';
        const result = searchContentAndFindTimestamp(query);
        if (result) {{
            const {{ video, timestamp, matchedText }} = result;
            showVideo(video, timestamp);
            const minutes = Math.floor(timestamp / 60);
            const seconds = Math.floor(timestamp % 60);
            const timeStr = timestamp > 0 ? ` (mulai menit ${{minutes}}:${{seconds}})` : "";
            const message = `Saya menemukan video "${{video.title}}"${{timeStr}} yang membahas hal tersebut.`;
            searchInfoEl.innerHTML = `🔍 Ditemukan: <b>${{video.title}}</b><br/><small style="opacity:0.8">Segmen: "${{matchedText}}"</small>`;
            searchInfoEl.style.display = 'block';
            sendFunctionResult(callId, {{ success: true, message: message }});
        }} else {{
            searchInfoEl.style.display = 'none';
            sendFunctionResult(callId, {{ success: false, message: `Maaf, saya tidak menemukan video yang relevan dengan "${{query}}"` }});
        }}
    }}

    function handleGetVideoContent(args, callId) {{
        const video = VIDEOS_DATA.find(v => v.id === (args.video_id || currentVideoId));
        if (!video) return sendFunctionResult(callId, {{ success: false, message: 'Video tidak ditemukan.'}});
        
        const timestamp = args.timestamp || 0;
        const transcript = video.transcript || [];
        // Find index of the segment at or immediately following the timestamp
        const index = transcript.findIndex(s => timestamp >= s.start && timestamp <= s.end);
        
        if (index === -1) {{
             sendFunctionResult(callId, {{ success: true, content: 'Tidak ada konten pada waktu tersebut.' }});
             return;
        }}

        // Get context: -2 to +2 segments
        const startIdx = Math.max(0, index - 2);
        const endIdx = Math.min(transcript.length, index + 3);
        const contextSegments = transcript.slice(startIdx, endIdx);
        
        const content = contextSegments.map(s => `[${{s.start}}-${{s.end}}] ${{s.text}}`).join(" ");
        
        navigateToTimestamp(timestamp);
        sendFunctionResult(callId, {{ success: true, content: content }});
    }}

    async function startConversation() {{
        if (peerConnection) await stopConversation();
        try {{
            updateStatus('connecting', '🟡 Menghubungkan...'); startBtn.disabled = true;
            const tokenResponse = await fetch('https://api.openai.com/v1/realtime/sessions', {{
                method: 'POST', headers: {{ 'Authorization': `Bearer ${{API_KEY}}`, 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    model: 'gpt-4o-realtime-preview-2024-12-17', voice: 'alloy', instructions: SYSTEM_PROMPT,
                    tools: [
                        {{ type: 'function', name: 'navigate_video', description: 'Navigasi video ke timestamp tertentu.', parameters: {{ type: 'object', properties: {{ video_id: {{ type: 'string' }}, timestamp: {{ type: 'integer' }} }}, required: ['timestamp'] }} }},
                        {{ type: 'function', name: 'search_video', description: 'Cari video berdasarkan topik/kata kunci.', parameters: {{ type: 'object', properties: {{ query: {{ type: 'string' }} }}, required: ['query'] }} }},
                        {{ type: 'function', name: 'get_video_content', description: 'Dapatkan konten video di timestamp tertentu.', parameters: {{ type: 'object', properties: {{ video_id: {{ type: 'string' }}, timestamp: {{ type: 'integer' }} }}, required: ['timestamp'] }} }}
                    ],
                    input_audio_transcription: {{ model: 'whisper-1' }}, turn_detection: {{ type: 'server_vad' }} 
                }})
            }});
            if (!tokenResponse.ok) throw new Error(`Gagal sesi: ${{await tokenResponse.text()}}`);
            const sessionData = await tokenResponse.json(); const ephemeralKey = sessionData.client_secret.value;
            peerConnection = new RTCPeerConnection();
            audioElement = document.createElement('audio'); 
            audioElement.autoplay = true;
            audioElement.playbackRate = 1.25; 
            
            peerConnection.ontrack = (event) => {{ 
                const stream = event.streams[0];
                audioElement.srcObject = stream;
                audioElement.onloadedmetadata = () => {{ audioElement.playbackRate = 1.25; }};
                setupAudioAnalysis(stream);
            }};
            
            mediaStream = await navigator.mediaDevices.getUserMedia({{ audio: {{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }} }});
            mediaStream.getAudioTracks().forEach(track => peerConnection.addTrack(track, mediaStream));
            dataChannel = peerConnection.createDataChannel('oai-events');
            dataChannel.onopen = () => {{
                isConnected = true; isAIsTurn = false;
                updateStatus('ai-speaking', '🔵 AI menyapa...');
                stopBtn.disabled = false;
                // setMicrophoneEnabled(false); // REMOVED: Allow barge-in
                visualizerEl.style.display = 'none';
                
                // [MODIFIKASI PENTING]: Instruksi awal diperketat agar tidak auto-play
                dataChannel.send(JSON.stringify({{ 
                    type: 'conversation.item.create', 
                    item: {{ 
                        type: 'message', 
                        role: 'user', 
                        content: [{{ 
                            type: 'input_text', 
                            text: '[SYSTEM]: Sapa pengguna dengan hangat. JANGAN panggil function/tool apapun. Cukup tanyakan apa yang ingin dipelajari.'
                        }}] 
                    }} 
                }}));
                dataChannel.send(JSON.stringify({{ type: 'response.create' }}));
            }};
            dataChannel.onmessage = (event) => handleServerEvent(JSON.parse(event.data));
            dataChannel.onclose = () => {{ isConnected = false; }};
            const offer = await peerConnection.createOffer(); await peerConnection.setLocalDescription(offer);
            const sdpResponse = await fetch('https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17', {{
                method: 'POST', headers: {{ 'Authorization': `Bearer ${{ephemeralKey}}`, 'Content-Type': 'application/sdp' }}, body: offer.sdp
            }});
            if (!sdpResponse.ok) throw new Error('Gagal terhubung ke Realtime API');
            await peerConnection.setRemoteDescription({{ type: 'answer', sdp: await sdpResponse.text() }});
        }} catch (error) {{
            console.error('Error:', error);
            updateStatus('disconnected', `🔴 Error: ${{error.message}}`);
            startBtn.disabled = false; stopBtn.disabled = true;
        }}
    }}

    function handleServerEvent(event) {{
        if (event.type !== 'input_audio_buffer.chunk') console.log(`EVENT: ${{event.type.padEnd(45, ' ')}} | isAIsTurn: ${{isAIsTurn}}`);
        switch (event.type) {{
            case 'conversation.item.input_audio_transcription.completed':
                if (event.transcript) addTranscript('user', event.transcript);
                break;
            case 'response.audio_transcript.done':
                if (event.transcript) addTranscript('assistant', event.transcript);
                break;
            case 'response.function_call_arguments.done':
                const funcName = event.name, callId = event.call_id;
                let args = {{}};
                try {{ args = JSON.parse(event.arguments || '{{}}'); }} catch(e) {{ console.error("Gagal parse argumen:", e); }}
                if (funcName === 'navigate_video') handleNavigateVideo(args, callId);
                else if (funcName === 'search_video') handleSearchVideo(args, callId);
                else if (funcName === 'get_video_content') handleGetVideoContent(args, callId);
                break;
            case 'response.audio.started':
                if (!videoEl.paused) {{ videoEl.muted = true; videoEl.playbackRate = 0.5; }}
                break;
            case 'input_audio_buffer.speech_started':
                isAIsTurn = false;
                videoEl.playbackRate = 1.0;
                videoEl.muted = true;
                updateStatus('speaking', '🎤 Mendengarkan...');
                visualizerEl.style.display = 'flex';
                animateVisualizer();
                break;
            case 'input_audio_buffer.speech_stopped':
                // setMicrophoneEnabled(false); // REMOVED: Allow barge-in
                updateStatus('connected', '🟢 Memproses...');
                visualizerEl.style.display = 'none';
                videoEl.muted = false;
                videoEl.playbackRate = 1.0;
                break;
            case 'error':
                console.error('API Error:', event.error); updateStatus('disconnected', `🔴 Error: ${{event.error?.message || 'Unknown'}}`);
                isAIsTurn = false;
                setMicrophoneEnabled(true);
                break;
        }}
    }}

    async function stopConversation() {{
        if (!peerConnection) return;
        isConnected = false; isAIsTurn = false;
        videoEl.pause();
        videoEl.currentTime = 0;
        videoEl.muted = false; 
        videoEl.playbackRate = 1.0;
        if (audioAnalysisLoop) cancelAnimationFrame(audioAnalysisLoop);
        if (audioContext) audioContext.close();
        audioContext = null; audioAnalyser = null;
        setMicrophoneEnabled(true);
        if (dataChannel) {{ dataChannel.close(); dataChannel = null; }}
        if (peerConnection) {{ peerConnection.close(); peerConnection = null; }}
        if (mediaStream) {{ mediaStream.getTracks().forEach(track => track.stop()); mediaStream = null; }}
        if (audioElement) {{ audioElement.srcObject = null; audioElement = null; }}
        updateStatus('disconnected', '🔴 Tidak terhubung');
        startBtn.disabled = false; stopBtn.disabled = true;
        visualizerEl.style.display = 'none';
        searchInfoEl.style.display = 'none';
    }}
    </script>
</body>
</html>
    """

# Helper untuk membersihkan input text
def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9 ]', '', text)

def main():
    st.set_page_config(page_title="Physics Learning Assistant", page_icon="🔬", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(r"""<style>#MainMenu, footer, header, .stApp > header {visibility: hidden;} .main .block-container {padding: 0; max-width: 100%;} iframe {border: none !important;}</style>""", unsafe_allow_html=True)
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY tidak ditemukan di file .env")
        return
    videos_data = load_videos_data()
    videos_list = videos_data.get("videos", [])
    system_prompt = load_system_prompt()
    app_html = get_full_app_html(OPENAI_API_KEY, videos_list, system_prompt)
    st.components.v1.html(app_html, height=700, scrolling=False)

if __name__ == "__main__":
    main()