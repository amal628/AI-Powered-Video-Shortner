# Start both Backend (FastAPI) and Frontend
# Terminal 1: Start FastAPI Backend (GPU strict mode)
$backendCmd = @"
Set-Location backend
$env:WHISPER_DEVICE='cuda'
$env:WHISPER_STRICT_GPU='true'
$env:FFMPEG_GPU='true'
$env:WHISPER_MODEL_SIZE='medium'
$env:WHISPER_FAST_MODEL_SIZE='small'
$env:WHISPER_ACCURATE_MODEL_SIZE='medium'
$env:WHISPER_BEAM_SIZE='2'
$env:WHISPER_FAST_BEAM_SIZE='1'
$env:WHISPER_ACCURATE_BEAM_SIZE='2'
$env:USE_LLM_SUMMARY='false'
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"@
Start-Process powershell -ArgumentList "-Command", $backendCmd

# Wait for backend to start
Start-Sleep -Seconds 3

# Terminal 2: Start Frontend Dev Server
Start-Process powershell -ArgumentList "-Command", "Set-Location frontend; npm run dev"

Write-Host "Both servers should be starting..."
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:5173"
