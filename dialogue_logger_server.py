#!/usr/bin/env python3
import json
import os
import uuid
import csv
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DIALOGUE_DIR = os.path.join(os.path.dirname(__file__), "dialogue")
OS_ENV_ONLY_LOCAL = True  # guard: only localhost accepted

os.makedirs(DIALOGUE_DIR, exist_ok=True)

COLUMNS = [
    "timestamp",
    "session_id",
    "type",
    "user_input",
    "ai_response",
    "action",
    "details",
]


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def session_file(session_id: str) -> str:
    safe_id = session_id.replace("/", "_")
    return os.path.join(DIALOGUE_DIR, f"session_{safe_id}.jsonl")


def csv_file(session_id: str) -> str:
    safe_id = session_id.replace("/", "_")
    return os.path.join(DIALOGUE_DIR, f"session_{safe_id}.csv")


def normalize_entry(entry: dict) -> dict:
    out = {
        "timestamp": entry.get("timestamp", ""),
        "session_id": entry.get("session_id", ""),
        "type": entry.get("type", "") or "",
        "user_input": entry.get("user_input", "") or "",
        "ai_response": entry.get("ai_response", "") or "",
        "action": entry.get("action", "") or "",
        "details": "",
    }
    details = entry.get("details")
    if isinstance(details, (dict, list)):
        out["details"] = json.dumps(details, ensure_ascii=False)
    elif details is not None:
        out["details"] = details
    return out


def ensure_csv_header(path: str):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()


def write_csv_row(session_id: str, entry: dict):
    path = csv_file(session_id)
    ensure_csv_header(path)
    row = normalize_entry(entry)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writerow(row)


class LoggerHandler(BaseHTTPRequestHandler):
    server_version = "DialogueLogger/1.0"

    def _only_local(self) -> bool:
        client_ip = self.client_address[0]
        return client_ip in ("127.0.0.1", "::1")

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Keep server quiet
        pass

    def do_POST(self):
        if OS_ENV_ONLY_LOCAL and not self._only_local():
            return self._send_json(403, {"ok": False, "error": "Forbidden: localhost only"})

        parsed = urlparse(self.path)
        path = parsed.path
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as e:
            return self._send_json(400, {"ok": False, "error": f"Invalid JSON: {e}"})

        # Common fields
        ts = iso_now()
        session_id = data.get("session_id")

        if path == "/start":
            if not session_id:
                session_id = str(uuid.uuid4())
            sf = session_file(session_id)
            entry = {
                "timestamp": ts,
                "session_id": session_id,
                "type": "session_start"
            }
            with open(sf, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            write_csv_row(session_id, entry)
            return self._send_json(200, {"ok": True, "session_id": session_id})

        if not session_id:
            return self._send_json(400, {"ok": False, "error": "session_id required"})

        sf = session_file(session_id)

        if path == "/log":
            entry = {
                "timestamp": ts,
                "session_id": session_id,
                "user_input": data.get("user_input"),
                "ai_response": data.get("ai_response"),
                "action": data.get("action")
            }
            with open(sf, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            write_csv_row(session_id, entry)
            return self._send_json(200, {"ok": True})

        if path == "/action":
            action = data.get("action")
            details = data.get("details")
            entry = {
                "timestamp": ts,
                "session_id": session_id,
                "user_input": None,
                "ai_response": None,
                "action": action,
                "details": details,
            }
            with open(sf, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            write_csv_row(session_id, entry)
            return self._send_json(200, {"ok": True})

        if path == "/end":
            entry = {
                "timestamp": ts,
                "session_id": session_id,
                "type": "session_end",
                "action": "end_session"
            }
            with open(sf, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            write_csv_row(session_id, entry)
            return self._send_json(200, {"ok": True})

        return self._send_json(404, {"ok": False, "error": "Unknown endpoint"})

    def do_OPTIONS(self):
        if OS_ENV_ONLY_LOCAL and not self._only_local():
            return self._send_json(403, {"ok": False, "error": "Forbidden: localhost only"})
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.end_headers()


def run(host="127.0.0.1", port=8777):
    httpd = ThreadingHTTPServer((host, port), LoggerHandler)
    print(f"[DialogueLogger] Listening on http://{host}:{port} (localhost only)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()