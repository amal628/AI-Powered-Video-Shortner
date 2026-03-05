# Audio Segmentation and Transcription Improvements

## Tasks
- [ ] 1. Improve whisper_service.py - better segment grouping with larger chunks
- [ ] 2. Improve video_processing.py - increase gap threshold for smoother transitions
- [ ] 3. Improve video_render_service.py - use re-encoding instead of stream copy for concatenation
- [ ] 4. Improve fast_video_processor.py - add audio crossfade at segment boundaries

## Implementation Notes

### Issue 1: Whisper Segmentation
- Whisper returns very short segments (sometimes just a few words)
- Fix: Group segments into larger coherent chunks based on sentence boundaries

### Issue 2: Segment Compression Gap Threshold
- Current gap threshold of 0.6s is too small
- Fix: Increase to 1.5-2.0s for smoother transitions

### Issue 3: Stream Copy Concatenation
- Using `-c copy` causes keyframe misalignment and audio desync
- Fix: Use re-encoding path for concatenation

### Issue 4: No Crossfade at Cut Points
- Direct concatenation causes clicks/pops
- Fix: Add audio crossfade between segments
