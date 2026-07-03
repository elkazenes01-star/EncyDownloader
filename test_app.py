import pytest
from unittest.mock import patch, MagicMock
import json
import os
import tempfile
from app import app, search_youtube, cleanup_old_downloads, DOWNLOAD_DIR


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_page(client):
    """Test that home page loads with search form."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"YouTube Video Downloader" in response.data
    assert b'name="q"' in response.data
    assert b"Search" in response.data


def test_search_redirect_empty_query(client):
    """Test that empty search redirects to home."""
    response = client.get("/search?q=")
    assert response.status_code == 302
    assert "/" in response.headers["Location"]


def test_search_redirect_no_query(client):
    """Test that missing query parameter redirects to home."""
    response = client.get("/search")
    assert response.status_code == 302


@patch("app.search_youtube")
def test_search_results_page(mock_search, client):
    """Test search results page with mocked data."""
    mock_search.return_value = [
        {
            "id": "abc123",
            "title": "Test Video",
            "thumbnail": "https://img.youtube.com/vi/abc123/0.jpg",
            "duration": "3:45",
            "channel": "Test Channel",
            "url": "https://www.youtube.com/watch?v=abc123",
        }
    ]
    response = client.get("/search?q=test+video")
    assert response.status_code == 200
    assert b"Test Video" in response.data
    assert b"Test Channel" in response.data
    assert b"MP3" in response.data
    assert b"MP4" in response.data
    assert b"abc123" in response.data


@patch("app.search_youtube")
def test_search_no_results(mock_search, client):
    """Test search with no results."""
    mock_search.return_value = []
    response = client.get("/search?q=xyznonexistent")
    assert response.status_code == 200
    assert b"No results found" in response.data


def test_pricing_page(client):
    """Test pricing page renders correctly."""
    response = client.get("/pricing")
    assert response.status_code == 200
    assert b"Pro" in response.data
    assert "10\u20ac" in response.data.decode("utf-8")
    assert "59\u20ac" in response.data.decode("utf-8")
    assert "Besplatno" in response.data.decode("utf-8")
    assert "Kupi Pretplatu" in response.data.decode("utf-8")


def test_subscribe_redirect(client):
    """Test subscribe button redirects to placeholder."""
    response = client.get("/subscribe")
    assert response.status_code == 302
    assert "lemonsqueezy.com" in response.headers["Location"]


def test_subscribe_uses_env_var(client):
    """Test that subscribe uses the LEMON_SQUEEZY_CHECKOUT_URL env var."""
    with patch.dict(os.environ, {"LEMON_SQUEEZY_CHECKOUT_URL": "https://example.com/checkout/test"}):
        from importlib import reload
        import app as app_module
        reload(app_module)
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as test_client:
            response = test_client.get("/subscribe")
            assert response.status_code == 302
            assert "example.com/checkout/test" in response.headers["Location"]


@patch("subprocess.run")
def test_search_youtube_function(mock_run):
    """Test the search_youtube function parses yt-dlp output."""
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({
        "id": "video1",
        "title": "My Video",
        "thumbnail": "https://img.youtube.com/thumb.jpg",
        "duration_string": "5:30",
        "channel": "My Channel",
        "url": "https://www.youtube.com/watch?v=video1",
    })
    mock_run.return_value = mock_result

    results = search_youtube("test query")
    assert len(results) == 1
    assert results[0]["id"] == "video1"
    assert results[0]["title"] == "My Video"
    assert results[0]["channel"] == "My Channel"


@patch("subprocess.run")
def test_search_youtube_handles_timeout(mock_run):
    """Test that search handles timeout gracefully."""
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="yt-dlp", timeout=30)
    results = search_youtube("test")
    assert results == []


@patch("subprocess.run")
def test_search_youtube_handles_invalid_json(mock_run):
    """Test that search handles invalid JSON gracefully."""
    mock_result = MagicMock()
    mock_result.stdout = "not valid json\n"
    mock_run.return_value = mock_result
    results = search_youtube("test")
    assert results == []


@patch("subprocess.run")
def test_download_mp3_success(mock_run, client):
    """Test MP3 download writes file to disk and sends it."""
    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0

        if "--get-title" in cmd:
            mock_result.stdout = "Test Song Title"
        elif "-x" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_template = cmd[i + 1]
                    output_path = output_template.replace("%(ext)s", "mp3")
                    with open(output_path, "wb") as f:
                        f.write(b"fake mp3 content")
                    break
        return mock_result

    mock_run.side_effect = side_effect

    response = client.get("/download/abc123?format=mp3")
    assert response.status_code == 200
    assert "audio/mpeg" in response.content_type
    assert b"fake mp3 content" in response.data
    assert "Test Song Title.mp3" in response.headers.get("Content-Disposition", "")


@patch("subprocess.run")
def test_download_mp4_success(mock_run, client):
    """Test MP4 download writes file to disk and sends it."""
    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0

        if "--get-title" in cmd:
            mock_result.stdout = "Test Video"
        elif "--merge-output-format" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_template = cmd[i + 1]
                    output_path = output_template.replace("%(ext)s", "mp4")
                    with open(output_path, "wb") as f:
                        f.write(b"fake mp4 content")
                    break
        return mock_result

    mock_run.side_effect = side_effect

    response = client.get("/download/abc123?format=mp4")
    assert response.status_code == 200
    assert "video/mp4" in response.content_type
    assert b"fake mp4 content" in response.data
    assert "Test Video.mp4" in response.headers.get("Content-Disposition", "")


@patch("subprocess.run")
def test_download_cleans_up_file(mock_run, client):
    """Test that the downloaded file is removed after sending."""
    created_files = []

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0

        if "--get-title" in cmd:
            mock_result.stdout = "Cleanup Test"
        elif "-x" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_template = cmd[i + 1]
                    output_path = output_template.replace("%(ext)s", "mp3")
                    with open(output_path, "wb") as f:
                        f.write(b"temp content")
                    created_files.append(output_path)
                    break
        return mock_result

    mock_run.side_effect = side_effect

    response = client.get("/download/testclean?format=mp3")
    assert response.status_code == 200

    # File should be deleted after sending
    for f in created_files:
        assert not os.path.exists(f), f"File {f} should have been cleaned up"


@patch("subprocess.run")
def test_download_timeout_returns_504(mock_run, client):
    """Test that a download timeout returns 504."""
    import subprocess as sp

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if "--get-title" in cmd:
            mock_result = MagicMock()
            mock_result.stdout = "Timeout Video"
            return mock_result
        raise sp.TimeoutExpired(cmd="yt-dlp", timeout=300)

    mock_run.side_effect = side_effect

    response = client.get("/download/timeout123?format=mp4")
    assert response.status_code == 504


@patch("subprocess.run")
def test_download_no_file_returns_500(mock_run, client):
    """Test that a failed download (no file created) returns 500."""
    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: video not found"
        mock_result.returncode = 1

        if "--get-title" in cmd:
            mock_result.stdout = "Missing Video"
        return mock_result

    mock_run.side_effect = side_effect

    response = client.get("/download/missing123?format=mp3")
    assert response.status_code == 500


@patch("subprocess.run")
def test_download_mp4_caps_at_720p(mock_run, client):
    """Test that MP4 format selector caps at 720p."""
    captured_cmds = []

    def side_effect(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        captured_cmds.append(cmd)
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.returncode = 0

        if "--get-title" in cmd:
            mock_result.stdout = "720p Test"
        elif "--merge-output-format" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    output_template = cmd[i + 1]
                    output_path = output_template.replace("%(ext)s", "mp4")
                    with open(output_path, "wb") as f:
                        f.write(b"video data")
                    break
        return mock_result

    mock_run.side_effect = side_effect

    response = client.get("/download/res123?format=mp4")
    assert response.status_code == 200

    # Check that the download command includes 720p cap
    download_cmd = [c for c in captured_cmds if "--merge-output-format" in c]
    assert len(download_cmd) == 1
    assert "bestvideo[height<=720]+bestaudio/best[height<=720]/best" in download_cmd[0]


def test_cleanup_old_downloads():
    """Test that cleanup removes old files."""
    import time

    # Create a temp file in downloads dir
    test_file = os.path.join(DOWNLOAD_DIR, "old_test_file.mp3")
    with open(test_file, "w") as f:
        f.write("old content")

    # Set modification time to 20 minutes ago
    old_time = time.time() - 1200
    os.utime(test_file, (old_time, old_time))

    cleanup_old_downloads(max_age_seconds=600)
    assert not os.path.exists(test_file)


def test_cleanup_keeps_recent_files():
    """Test that cleanup keeps recent files."""
    test_file = os.path.join(DOWNLOAD_DIR, "recent_test_file.mp3")
    with open(test_file, "w") as f:
        f.write("recent content")

    cleanup_old_downloads(max_age_seconds=600)
    assert os.path.exists(test_file)

    # Clean up
    os.remove(test_file)


def test_nav_links(client):
    """Test navigation links are present."""
    response = client.get("/")
    assert b"Home" in response.data
    assert b"Pro" in response.data
    assert b"YT Downloader" in response.data


def test_static_css_accessible(client):
    """Test that static CSS file is served correctly."""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200


def test_render_yaml_exists():
    """Test that render.yaml exists and has correct structure."""
    import yaml
    render_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.yaml")
    assert os.path.exists(render_path)
    with open(render_path) as f:
        config = yaml.safe_load(f)
    assert "services" in config
    service = config["services"][0]
    assert service["type"] == "web"
    assert service["runtime"] == "docker"


def test_secret_key_from_env():
    """Test that SECRET_KEY can be set via environment variable."""
    with patch.dict(os.environ, {"SECRET_KEY": "my-production-secret"}):
        from importlib import reload
        import app as app_module
        reload(app_module)
        assert app_module.app.secret_key == "my-production-secret"
