from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import subprocess
import sys
import os

# Install yt-dlp if not present
try:
    import yt_dlp
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
    import yt_dlp

API_KEY = "BLAZEXSOUL"

def verify_key(params):
    return params.get("key", [None])[0] == API_KEY

def search_youtube(query, max_results=8):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": "ytsearch",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        entries = result.get("entries", [])
        videos = []
        for e in entries:
            if e:
                videos.append({
                    "title": e.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={e.get('id', '')}",
                    "thumbnail": e.get("thumbnail", f"https://i.ytimg.com/vi/{e.get('id','')}/hqdefault.jpg"),
                    "duration": e.get("duration_string", e.get("duration", "")),
                    "channel": e.get("uploader", e.get("channel", "")),
                    "views": e.get("view_count", 0),
                    "video_id": e.get("id", ""),
                })
        return videos

def get_video_formats(url):
    ydl_opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
        
        options = []
        seen_qualities = set()
        
        # Video formats with audio merged
        video_formats = [
            f for f in formats
            if f.get("vcodec") != "none" and f.get("acodec") != "none"
            and f.get("url")
        ]
        
        # If no merged formats, get best video+audio combo
        if not video_formats:
            video_only = [f for f in formats if f.get("vcodec") != "none" and f.get("url")]
            for vf in sorted(video_only, key=lambda x: x.get("height") or 0, reverse=True):
                height = vf.get("height", 0)
                label = f"{height}p" if height else vf.get("format_note", "Unknown")
                if label not in seen_qualities and height:
                    seen_qualities.add(label)
                    options.append({
                        "quality": label,
                        "format": vf.get("ext", "mp4"),
                        "url": vf.get("url", ""),
                        "filesize": vf.get("filesize") or vf.get("filesize_approx"),
                        "fps": vf.get("fps"),
                        "type": "video",
                    })
        else:
            for vf in sorted(video_formats, key=lambda x: x.get("height") or 0, reverse=True):
                height = vf.get("height", 0)
                label = f"{height}p" if height else vf.get("format_note", "Unknown")
                if label not in seen_qualities:
                    seen_qualities.add(label)
                    options.append({
                        "quality": label,
                        "format": vf.get("ext", "mp4"),
                        "url": vf.get("url", ""),
                        "filesize": vf.get("filesize") or vf.get("filesize_approx"),
                        "fps": vf.get("fps"),
                        "type": "video",
                    })
        
        return {
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration_string", ""),
            "channel": info.get("uploader", ""),
            "options": options[:6],  # Top 6 quality options
        }

def get_audio_url(url):
    ydl_opts = {"quiet": True, "no_warnings": True, "format": "bestaudio/best"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
        
        # Get best audio formats
        audio_formats = [
            f for f in formats
            if f.get("acodec") != "none" and f.get("vcodec") == "none" and f.get("url")
        ]
        
        options = []
        seen = set()
        for af in sorted(audio_formats, key=lambda x: x.get("abr") or 0, reverse=True):
            abr = af.get("abr", 0)
            label = f"{int(abr)}kbps" if abr else af.get("format_note", "audio")
            if label not in seen:
                seen.add(label)
                options.append({
                    "quality": label,
                    "format": af.get("ext", "m4a"),
                    "url": af.get("url", ""),
                    "filesize": af.get("filesize") or af.get("filesize_approx"),
                    "type": "audio",
                })
        
        # Fallback: merged format audio track
        if not options:
            best = info.get("url", "")
            if best:
                options.append({
                    "quality": "best",
                    "format": info.get("ext", "m4a"),
                    "url": best,
                    "type": "audio",
                })
        
        return {
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration_string", ""),
            "channel": info.get("uploader", ""),
            "options": options[:4],
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # CORS headers
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # --- Auth Check ---
        if not verify_key(params):
            self.wfile.write(json.dumps({
                "success": False,
                "error": "Invalid API key. Use ?key=BLAZEXSOUL"
            }).encode())
            return

        try:
            # ==================== SEARCH ====================
            if path == "/blaze-search":
                query = params.get("search", [None])[0]
                if not query:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Missing ?search= parameter"
                    }).encode())
                    return

                results = search_youtube(query)
                self.wfile.write(json.dumps({
                    "success": True,
                    "query": query,
                    "results": results
                }, ensure_ascii=False).encode())

            # ==================== VIDEO DOWNLOAD ====================
            elif path == "/blaze-download":
                url = params.get("q", [None])[0]
                if not url:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Missing ?q=<youtube_url> parameter"
                    }).encode())
                    return

                data = get_video_formats(url)
                self.wfile.write(json.dumps({
                    "success": True,
                    "title": data["title"],
                    "thumbnail": data["thumbnail"],
                    "duration": data["duration"],
                    "channel": data["channel"],
                    "options": data["options"],
                    "note": "Use the 'url' from any option to stream/download directly"
                }, ensure_ascii=False).encode())

            # ==================== AUDIO DOWNLOAD ====================
            elif path == "/blaze-audio":
                url = params.get("q", [None])[0]
                if not url:
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Missing ?q=<youtube_url> parameter"
                    }).encode())
                    return

                data = get_audio_url(url)
                self.wfile.write(json.dumps({
                    "success": True,
                    "title": data["title"],
                    "thumbnail": data["thumbnail"],
                    "duration": data["duration"],
                    "channel": data["channel"],
                    "options": data["options"],
                    "note": "Use the 'url' from any option to stream/play audio directly"
                }, ensure_ascii=False).encode())

            # ==================== HOME ====================
            else:
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": "🔥 Blaze API by BLAZEXSOUL",
                    "endpoints": {
                        "/blaze-search": "?key=BLAZEXSOUL&search=<query>",
                        "/blaze-download": "?key=BLAZEXSOUL&q=<youtube_url>",
                        "/blaze-audio": "?key=BLAZEXSOUL&q=<youtube_url>"
                    }
                }).encode())

        except Exception as e:
            self.wfile.write(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())

    def log_message(self, format, *args):
        pass  # Suppress default logs
