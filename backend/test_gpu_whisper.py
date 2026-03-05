# Test script to verify Whisper service loads correctly with GPU
import sys
sys.path.insert(0, '.')

from app.services.whisper_service import whisper_service

print('Whisper service loaded successfully')
print('strict_gpu:', whisper_service.strict_gpu)
print('default_model_size:', whisper_service.default_model_size)
print('default_beam_size:', whisper_service.default_beam_size)

# Check runtime info
info = whisper_service.get_runtime_info()
print('\nRuntime Info:')
print('  last_device:', info.get('last_device'))
print('  last_compute_type:', info.get('last_compute_type'))
