# YT Downloader - YouTube Video Search & Download App

A Flask web application for searching and downloading YouTube videos as MP3 (audio) or MP4 (video).

## Features

- **Search**: Search YouTube videos directly from the app
- **Download MP3**: Extract high-quality audio from any video
- **Download MP4**: Download videos in 720p or highest available quality
- **Pro Section**: Pricing page with mock subscription buttons (Lemon Squeezy placeholder)
- **Dark UI**: Clean, modern dark-themed interface

## Requirements

- Python 3.9+
- yt-dlp
- ffmpeg (for audio conversion)

## Setup & Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd youtube_projekat
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install ffmpeg** (required for MP3 conversion):
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows - download from https://ffmpeg.org/download.html
   ```

## Running the App

```bash
python app.py
```

The app will start on `http://localhost:5000`

## Usage

1. Open your browser and go to `http://localhost:5000`
2. Enter a search term in the search bar
3. Browse results with thumbnails and video info
4. Click **MP3** to download audio or **MP4** to download video
5. Visit the **Pro** section to see pricing plans

## Project Structure

```
youtube_projekat/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── templates/
│   ├── base.html          # Base template with nav & footer
│   ├── index.html         # Home page with search
│   ├── results.html       # Search results page
│   └── pricing.html       # Pro pricing page
├── static/
│   └── css/
│       └── style.css      # Application styles
└── downloads/             # (auto-created) Download cache
```

## Notes

- Downloads are streamed directly to the user's browser
- The "Buy Subscription" button redirects to a placeholder Lemon Squeezy URL
- For personal use only - respect YouTube's Terms of Service
- The app uses `yt-dlp` for all YouTube interactions (search, metadata, downloads)

## Troubleshooting

- **No search results**: Ensure `yt-dlp` is installed and up to date (`pip install -U yt-dlp`)
- **Download fails**: Make sure `ffmpeg` is installed for MP3 conversion
- **Slow downloads**: This depends on your internet connection and YouTube's servers
