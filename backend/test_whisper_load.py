# Test script to verify Whisper service loads correctly
import sys
sys.path.insert(0, '.')

from app.services.whisper_service import whisper_service

print('Whisper service loaded successfully')
print('strict_gpu:', whisper_service.strict_gpu)
print('default_model_size:', whisper_service.default_model_size)
print('default_beam_size:', whisper_service.default_beam_size)
