# backend/app/services/audio_extractor.py

import subprocess
from pathlib import Path
import logging
import warnings
import os

warnings.filterwarnings("ignore")
from ..core.config import settings

logger = logging.getLogger(__name__)
FFMPEG_AUDIO_TIMEOUT_SECONDS = float(
    os.getenv(
        "FFMPEG_AUDIO_TIMEOUT_SECONDS",
        "360"
    )
)


from pathlib import Path

def extract_audio_from_video(video_path: str | Path, audio_filename: str) -> str:
    """
    Extract audio from ANY video format and convert to
    Whisper-optimized WAV (16kHz mono PCM).

    Returns:
        Absolute path to extracted audio file
    """

    try:
        video_path = Path(video_path)

        # Always force WAV output (ignore incoming filename extension)
        audio_filename = audio_filename.replace(".mp3", ".wav")
        audio_output_path = settings.AUDIO_DIR / audio_filename

        settings.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        command = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",                    # remove video
            "-acodec", "pcm_s16le",   # 16-bit PCM
            "-ar", "16000",           # 16kHz sample rate
            "-ac", "1",               # mono
            "-map", "a",              # automatically map audio stream
            "-y",
            str(audio_output_path)
        ]

        logger.info(f"Extracting audio using FFmpeg: {' '.join(command)}")

        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=FFMPEG_AUDIO_TIMEOUT_SECONDS
        )

        logger.info("Audio extraction completed successfully.")

        return str(audio_output_path)

    except subprocess.CalledProcessError as e:
        logger.error("FFmpeg audio extraction failed.")
        logger.error(e.stderr.decode())
        raise RuntimeError("Audio extraction failed.")
    except subprocess.TimeoutExpired:
        logger.error(
            "Audio extraction timed out after %.1fs",
            FFMPEG_AUDIO_TIMEOUT_SECONDS
        )
        raise RuntimeError("Audio extraction timed out. Please try a shorter clip.")

    except Exception as e:
        logger.exception("Unexpected error during audio extraction.")
        raise RuntimeError(f"Audio extraction failed: {str(e)}")
