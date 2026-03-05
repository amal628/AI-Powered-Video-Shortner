import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.services.whisper_service import whisper_service

info = whisper_service.get_runtime_info()
print("Whisper Info:", info)
