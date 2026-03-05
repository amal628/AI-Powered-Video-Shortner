# AI-Powered Video Shortener

Transform long videos into engaging short-form content automatically with AI. Perfect for content creators, marketers, and social media managers.

## ✨ Features

### 🎯 Automatic Engaging Moment Detection
- AI identifies the most engaging moments in your videos automatically
- Analyzes speech patterns, emotional triggers, and engagement hooks
- Prioritizes hook segments, conclusions, and high-value content
- Fast processing - typically under 1 minute for most videos

### 🎬 Smooth Transitions
- Professional crossfade transitions between clips
- Multiple transition types: fade, crossfade, wipe, dissolve
- Configurable transition duration
- Intro and outro fade effects

### 📱 Social Media Ready
Optimized presets for all major platforms:
- **Instagram Reels** - 9:16, up to 90s
- **Instagram Stories** - 9:16, up to 60s
- **TikTok** - 9:16, up to 180s
- **YouTube Shorts** - 9:16, up to 60s
- **WhatsApp Status** - 9:16, up to 30s
- **Facebook Stories/Reels** - 9:16, up to 90s
- **Snapchat Spotlight** - 9:16, up to 60s
- **Twitter/X Stories** - 9:16, up to 140s
- **LinkedIn Stories** - 9:16, up to 20s

### ⚡ Fast Processing
- Optimized FFmpeg settings for speed
- Parallel segment extraction
- Hardware acceleration support
- Ultrafast encoding preset option

### 🎨 Additional Features
- AI-powered transcription with Whisper
- Custom caption styling and burning
- Video preview with transcript
- Download in multiple formats

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- FFmpeg (installed and in PATH)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd AI_Powered_Video_Shortener
```

2. **Install backend dependencies**
```bash
cd backend
pip install -r requirements.txt
```

3. **Install frontend dependencies**
```bash
cd ../frontend
npm install
```

4. **Start the application**
```bash
# From the root directory
./start.bat  # Windows
# or
./start.sh   # Linux/Mac
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📖 API Endpoints

### Video Processing
```
POST /api/process-video
```
Process a video with customizable options:
```json
{
  "file_id": "uuid",
  "platform": "instagram_reels",
  "target_duration": 30.0,
  "transition_type": "crossfade",
  "transition_duration": 0.3,
  "add_intro_fade": true,
  "add_outro_fade": true
}
```

### Get Platforms
```
GET /api/platforms
```
Returns all available social media platform presets.

### Analyze Engagement
```
POST /api/analyze-engagement
```
Analyze video for engagement moments.

### Upload Video
```
POST /api/upload-video/
```
Upload a video file for processing.

### Transcribe
```
POST /api/transcribe
```
Transcribe video audio using Whisper AI.

## 🎯 Platform Specifications

| Platform | Aspect Ratio | Max Duration | Recommended | Resolution |
|----------|-------------|--------------|-------------|------------|
| Instagram Reels | 9:16 | 90s | 15s | 1080x1920 |
| TikTok | 9:16 | 180s | 30s | 1080x1920 |
| YouTube Shorts | 9:16 | 60s | 30s | 1080x1920 |
| Instagram Story | 9:16 | 60s | 15s | 1080x1920 |
| WhatsApp Status | 9:16 | 30s | 15s | 720x1280 |
| Facebook Story | 9:16 | 60s | 15s | 1080x1920 |

## 🔧 Configuration

### Backend Configuration
Edit `backend/.env`:
```env
# Whisper Model (tiny, base, small, medium, large)
WHISPER_MODEL_SIZE=base

# Upload settings
MAX_UPLOAD_SIZE=524288000
```

### Processing Options
- `transition_type`: none, fade, crossfade, wipe_left, wipe_right, dissolve
- `transition_duration`: Duration of transitions in seconds (0.1-1.0)
- `add_intro_fade`: Add fade-in at the beginning
- `add_outro_fade`: Add fade-out at the end

## 🏗️ Project Structure

```
AI_Powered_Video_Shortener/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   ├── core/             # Configuration
│   │   ├── models/           # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   │   ├── engagement_detector.py    # AI engagement detection
│   │   │   ├── fast_video_processor.py   # Optimized processing
│   │   │   ├── social_media_formats.py   # Platform presets
│   │   │   └── ...
│   │   └── static/           # Uploaded/processed files
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── PlatformSelector.jsx     # Platform selection UI
│   │   │   ├── VideoUpload.jsx          # Upload component
│   │   │   └── ...
│   │   ├── services/         # API services
│   │   └── ...
│   └── package.json
└── start.bat                 # Startup script
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

---

Built with ❤️ using FastAPI, React, Whisper AI, and FFmpeg.
>>>>>>> 146ce6e (Initial commit - AI Powered Video Shortener)
