import os
import subprocess
import json
import uuid
import glob
from flask import Flask, render_template, request, redirect, url_for, send_file, after_this_request, abort

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


def cleanup_old_downloads(max_age_seconds=600):
    """Remove download files older than max_age_seconds."""
    import time
    now = time.time()
    for filepath in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > max_age_seconds:
                try:
                    os.remove(filepath)
                except OSError:
                    pass


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

    # Clean up old files to prevent disk filling up on Render free tier
    cleanup_old_downloads()

    # Generate a unique filename to avoid conflicts
    unique_id = uuid.uuid4().hex[:8]
    base_filename = f"{video_id}_{unique_id}"

    if fmt == "mp3":
        # Output template: yt-dlp will append the extension
        output_template = os.path.join(DOWNLOAD_DIR, f"{base_filename}.%(ext)s")
        cmd = [
            "yt-dlp",
            url,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_template,
            "--no-playlist",
        ]
        expected_ext = "mp3"
        mimetype = "audio/mpeg"
    else:
        output_template = os.path.join(DOWNLOAD_DIR, f"{base_filename}.%(ext)s")
        cmd = [
            "yt-dlp",
            url,
            "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            "--no-playlist",
        ]
        expected_ext = "mp4"
        mimetype = "video/mp4"

    # Get the title for the download filename shown to user
    title = video_id
    try:
        title_cmd = ["yt-dlp", url, "--get-title", "--no-playlist"]
        title_result = subprocess.run(title_cmd, capture_output=True, text=True, timeout=15)
        if title_result.stdout.strip():
            title = title_result.stdout.strip()
            title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    except Exception:
        pass

    # Run the download to disk
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        abort(504, description="Download timed out. Try a shorter video.")
    except Exception as e:
        abort(500, description=f"Download failed: {str(e)}")

    # Find the downloaded file (yt-dlp may adjust the extension)
    downloaded_file = None

    # First check for the expected file
    expected_path = os.path.join(DOWNLOAD_DIR, f"{base_filename}.{expected_ext}")
    if os.path.isfile(expected_path):
        downloaded_file = expected_path
    else:
        # Look for any file matching our base_filename pattern
        pattern = os.path.join(DOWNLOAD_DIR, f"{base_filename}.*")
        matches = glob.glob(pattern)
        if matches:
            downloaded_file = matches[0]

    if not downloaded_file or not os.path.isfile(downloaded_file):
        abort(500, description="Download failed. The file could not be saved.")

    # Determine the actual extension for the user-facing filename
    actual_ext = os.path.splitext(downloaded_file)[1].lstrip(".")
    download_name = f"{title}.{actual_ext}"

    # Schedule file deletion after sending
    @after_this_request
    def remove_file(response):
        try:
            if downloaded_file and os.path.isfile(downloaded_file):
                os.remove(downloaded_file)
        except OSError:
            pass
        return response

    return send_file(
        downloaded_file,
        mimetype=mimetype,
        as_attachment=True,
        download_name=download_name,
    )


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
