import os
import subprocess
import json
from flask import Flask, render_template, request, redirect, url_for, Response, stream_with_context

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-key-change-in-production")

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LEMON_SQUEEZY_CHECKOUT_URL = os.environ.get(
    "LEMON_SQUEEZY_CHECKOUT_URL",
    "https://lemonsqueezy.com/checkout/placeholder-product-id"
)


def search_youtube(query, max_results=10):
    """Search YouTube using yt-dlp and return video metadata."""
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--no-download",
        "--flat-playlist",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        videos = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    videos.append({
                        "id": data.get("id", ""),
                        "title": data.get("title", "Unknown"),
                        "thumbnail": data.get("thumbnail") or data.get("thumbnails", [{}])[-1].get("url", ""),
                        "duration": data.get("duration_string", data.get("duration", "")),
                        "channel": data.get("channel", data.get("uploader", "Unknown")),
                        "url": data.get("url") or f"https://www.youtube.com/watch?v={data.get('id', '')}",
                    })
                except json.JSONDecodeError:
                    continue
        return videos
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def get_video_info(video_id):
    """Get detailed info about a specific video."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = ["yt-dlp", url, "--dump-json", "--no-download"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return redirect(url_for("index"))
    videos = search_youtube(query)
    return render_template("results.html", query=query, videos=videos)


@app.route("/download/<video_id>")
def download(video_id):
    fmt = request.args.get("format", "mp4")
    url = f"https://www.youtube.com/watch?v={video_id}"

    if fmt == "mp3":
        cmd = [
            "yt-dlp",
            url,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", "-",
        ]
        mimetype = "audio/mpeg"
        ext = "mp3"
    else:
        cmd = [
            "yt-dlp",
            url,
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "-o", "-",
        ]
        mimetype = "video/mp4"
        ext = "mp4"

    # Get the title for the filename
    title = video_id
    try:
        title_cmd = ["yt-dlp", url, "--get-title"]
        title_result = subprocess.run(title_cmd, capture_output=True, text=True, timeout=15)
        if title_result.stdout.strip():
            title = title_result.stdout.strip()
            title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    except Exception:
        pass

    def generate():
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            process.terminate()
            process.wait()

    filename = f"{title}.{ext}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": mimetype,
    }
    return Response(stream_with_context(generate()), headers=headers)


@app.route("/get-url/<video_id>")
def get_url(video_id):
    """Get direct download URL for the video."""
    fmt = request.args.get("format", "mp4")
    url = f"https://www.youtube.com/watch?v={video_id}"

    if fmt == "mp3":
        cmd = ["yt-dlp", url, "-x", "--audio-format", "mp3", "--get-url"]
    else:
        cmd = ["yt-dlp", url, "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best", "--get-url"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        direct_url = result.stdout.strip().split("\n")[0]
        if direct_url:
            return redirect(direct_url)
    except Exception:
        pass

    return redirect(url_for("download", video_id=video_id, format=fmt))


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")


@app.route("/subscribe")
def subscribe():
    return redirect(LEMON_SQUEEZY_CHECKOUT_URL)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
