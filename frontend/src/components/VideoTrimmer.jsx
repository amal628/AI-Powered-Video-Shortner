// frontend/src/components/VideoTrimmer.jsx
import { memo, useCallback, useEffect, useRef, useState } from 'react';
import './VideoTrimmer.css';

// Format time as MM:SS
const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

// Format time with milliseconds
const formatTimeDetailed = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

// Video trimmer using native browser APIs
const VideoTrimmer = memo(({
    videoFile,
    videoUrl,
    onTrimComplete,
    onCancel,
    initialStartTime = 0,
    initialEndTime = 30
}) => {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const [duration, setDuration] = useState(0);
    const [startTime, setStartTime] = useState(initialStartTime);
    const [endTime, setEndTime] = useState(initialEndTime);
    const [currentTime, setCurrentTime] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const [processingProgress, setProcessingProgress] = useState(0);
    const [dragging, setDragging] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const timelineRef = useRef(null);

    // Initialize video duration
    useEffect(() => {
        if (videoRef.current) {
            const handleLoadedMetadata = () => {
                const videoDuration = videoRef.current.duration;
                setDuration(videoDuration);
                if (initialEndTime > videoDuration || initialEndTime === 30) {
                    setEndTime(Math.min(30, videoDuration));
                }
            };

            const handleTimeUpdate = () => {
                setCurrentTime(videoRef.current.currentTime);
            };

            const handleEnded = () => {
                setIsPlaying(false);
            };

            videoRef.current.addEventListener('loadedmetadata', handleLoadedMetadata);
            videoRef.current.addEventListener('timeupdate', handleTimeUpdate);
            videoRef.current.addEventListener('ended', handleEnded);

            return () => {
                if (videoRef.current) {
                    videoRef.current.removeEventListener('loadedmetadata', handleLoadedMetadata);
                    videoRef.current.removeEventListener('timeupdate', handleTimeUpdate);
                    videoRef.current.removeEventListener('ended', handleEnded);
                }
            };
        }
    }, [initialEndTime]);

    // Play/pause toggle
    const togglePlay = useCallback(() => {
        if (videoRef.current) {
            if (isPlaying) {
                videoRef.current.pause();
            } else {
                videoRef.current.play();
            }
            setIsPlaying(!isPlaying);
        }
    }, [isPlaying]);

    // Seek to time
    const seekTo = useCallback((time) => {
        if (videoRef.current) {
            videoRef.current.currentTime = Math.max(0, Math.min(time, duration));
        }
    }, [duration]);

    // Jump to start/end
    const jumpToStart = useCallback(() => {
        seekTo(startTime);
    }, [startTime, seekTo]);

    const jumpToEnd = useCallback(() => {
        seekTo(endTime);
    }, [endTime, seekTo]);

    // Play selected region
    const playSelection = useCallback(() => {
        if (videoRef.current) {
            videoRef.current.currentTime = startTime;
            videoRef.current.play();
            setIsPlaying(true);
        }
    }, [startTime]);

    // Handle timeline click
    const handleTimelineClick = useCallback((e) => {
        if (timelineRef.current && !dragging) {
            const rect = timelineRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const percentage = x / rect.width;
            const time = percentage * duration;
            seekTo(time);
        }
    }, [duration, dragging, seekTo]);

    // Handle drag start
    const handleDragStart = useCallback((type) => (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragging(type);
    }, []);

    // Handle drag move
    useEffect(() => {
        if (!dragging) return;

        const handleMouseMove = (e) => {
            if (timelineRef.current) {
                const rect = timelineRef.current.getBoundingClientRect();
                const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
                const percentage = x / rect.width;
                const time = percentage * duration;

                if (dragging === 'start') {
                    const newStart = Math.min(time, endTime - 1);
                    setStartTime(Math.max(0, newStart));
                    seekTo(newStart);
                } else if (dragging === 'end') {
                    const newEnd = Math.max(time, startTime + 1);
                    setEndTime(Math.min(duration, newEnd));
                }
            }
        };

        const handleMouseUp = () => {
            setDragging(null);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [dragging, duration, endTime, startTime, seekTo]);

    // Trim video using MediaRecorder API with precise duration control
    const handleTrim = useCallback(async () => {
        if (!videoFile) {
            alert('No video file selected.');
            return;
        }

        setIsProcessing(true);
        setProcessingProgress(0);

        const targetDuration = endTime - startTime;

        try {
            const video = document.createElement('video');
            video.src = videoUrl;
            video.muted = true;
            video.preload = 'metadata';

            await new Promise((resolve, reject) => {
                video.onloadedmetadata = resolve;
                video.onerror = reject;
            });

            // Set up canvas for recording
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');

            // Create MediaRecorder
            const stream = canvas.captureStream(30);

            // Add audio if available
            let audioContext = null;
            let audioSource = null;

            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const audioStream = audioContext.createMediaStreamDestination();

                // Create audio element for capturing audio
                const audioElement = document.createElement('audio');
                audioElement.src = videoUrl;
                audioElement.crossOrigin = 'anonymous';

                await new Promise((resolve) => {
                    audioElement.oncanplaythrough = resolve;
                    audioElement.load();
                });

                const source = audioContext.createMediaElementSource(audioElement);
                source.connect(audioStream);
                source.connect(audioContext.destination);

                // Add audio track to stream
                audioStream.stream.getAudioTracks().forEach(track => {
                    stream.addTrack(track);
                });

                audioSource = { context: audioContext, element: audioElement, source };
            } catch (audioError) {
                console.warn('Could not capture audio:', audioError);
            }

            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
                    ? 'video/webm;codecs=vp9'
                    : 'video/webm',
                videoBitsPerSecond: 5000000
            });

            const chunks = [];
            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunks.push(e.data);
                }
            };

            const recordingComplete = new Promise((resolve) => {
                mediaRecorder.onstop = () => {
                    const blob = new Blob(chunks, { type: 'video/webm' });
                    resolve(blob);
                };
            });

            // Start recording
            video.currentTime = startTime;

            await new Promise((resolve) => {
                video.onseeked = resolve;
            });

            // Record start time for precise duration control
            const recordStartTime = performance.now();

            mediaRecorder.start(100);

            // Start audio if available
            if (audioSource) {
                audioSource.element.currentTime = startTime;
                await audioSource.element.play();
            }

            video.play();

            // Draw frames with precise timing control
            const drawFrame = () => {
                const elapsed = (performance.now() - recordStartTime) / 1000;
                const currentVideoTime = startTime + elapsed;

                // Stop when we've recorded exactly the target duration
                if (elapsed >= targetDuration || video.ended) {
                    mediaRecorder.stop();
                    video.pause();
                    if (audioSource) {
                        audioSource.element.pause();
                        audioSource.context.close();
                    }
                    return;
                }

                // Sync video playback to our timing
                if (Math.abs(video.currentTime - currentVideoTime) > 0.1) {
                    video.currentTime = currentVideoTime;
                }

                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                setProcessingProgress(Math.round((elapsed / targetDuration) * 100));
                requestAnimationFrame(drawFrame);
            };

            drawFrame();

            const blob = await recordingComplete;

            // Create URL for the trimmed video
            const url = URL.createObjectURL(blob);
            setPreviewUrl(url);

            // Notify parent with the exact target duration
            if (onTrimComplete) {
                onTrimComplete({
                    blob: blob,
                    url: url,
                    startTime,
                    endTime,
                    duration: targetDuration  // Return the exact user-specified duration
                });
            }
        } catch (error) {
            console.error('Trim failed:', error);
            alert('Failed to trim video: ' + error.message);
        } finally {
            setIsProcessing(false);
            setProcessingProgress(0);
        }
    }, [videoFile, videoUrl, startTime, endTime, onTrimComplete]);

    // Handle cancel
    const handleCancel = useCallback(() => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        if (onCancel) {
            onCancel();
        }
    }, [previewUrl, onCancel]);

    // Quick duration presets
    const durationPresets = [
        { label: '15s', duration: 15 },
        { label: '30s', duration: 30 },
        { label: '60s', duration: 60 },
        { label: '90s', duration: 90 },
    ];

    const applyPreset = useCallback((presetDuration) => {
        const newEnd = Math.min(startTime + presetDuration, duration);
        setEndTime(newEnd);
    }, [startTime, duration]);

    return (
        <div className="video-trimmer">
            {/* Header */}
            <div className="trimmer-header">
                <h3>✂️ Video Trimmer</h3>
                <p>Drag the handles to select the portion of the video you want to keep</p>
            </div>

            {/* Video Preview */}
            <div className="video-container">
                <video
                    ref={videoRef}
                    src={videoUrl}
                    className="trim-video"
                    preload="metadata"
                />

                {/* Video Controls Overlay */}
                <div className="video-controls">
                    <button
                        className="control-btn"
                        onClick={togglePlay}
                        title={isPlaying ? 'Pause' : 'Play'}
                    >
                        {isPlaying ? '⏸️' : '▶️'}
                    </button>
                    <button
                        className="control-btn"
                        onClick={jumpToStart}
                        title="Jump to start"
                    >
                        ⏮️
                    </button>
                    <button
                        className="control-btn"
                        onClick={jumpToEnd}
                        title="Jump to end"
                    >
                        ⏭️
                    </button>
                    <button
                        className="control-btn play-selection"
                        onClick={playSelection}
                        title="Play selection"
                    >
                        🔄 Play Selection
                    </button>
                </div>
            </div>

            {/* Timeline */}
            <div className="timeline-container">
                <div
                    className="timeline"
                    ref={timelineRef}
                    onClick={handleTimelineClick}
                >
                    {/* Timeline track */}
                    <div className="timeline-track"></div>

                    {/* Selected region */}
                    <div
                        className="timeline-selection"
                        style={{
                            left: `${(startTime / duration) * 100}%`,
                            width: `${((endTime - startTime) / duration) * 100}%`
                        }}
                    >
                        {/* Start handle */}
                        <div
                            className="trim-handle start-handle"
                            onMouseDown={handleDragStart('start')}
                        >
                            <div className="handle-line"></div>
                            <div className="handle-grip">⋮</div>
                        </div>

                        {/* End handle */}
                        <div
                            className="trim-handle end-handle"
                            onMouseDown={handleDragStart('end')}
                        >
                            <div className="handle-line"></div>
                            <div className="handle-grip">⋮</div>
                        </div>
                    </div>

                    {/* Playhead */}
                    <div
                        className="playhead"
                        style={{ left: `${(currentTime / duration) * 100}%` }}
                    ></div>
                </div>

                {/* Time markers */}
                <div className="time-markers">
                    <span>0:00</span>
                    <span>{formatTime(duration / 4)}</span>
                    <span>{formatTime(duration / 2)}</span>
                    <span>{formatTime((duration * 3) / 4)}</span>
                    <span>{formatTime(duration)}</span>
                </div>
            </div>

            {/* Time Inputs */}
            <div className="time-inputs">
                <div className="time-input-group">
                    <label>Start Time</label>
                    <input
                        type="text"
                        value={formatTimeDetailed(startTime)}
                        onChange={(e) => {
                            const parsed = parseFloat(e.target.value.replace(':', '.'));
                            if (!isNaN(parsed) && parsed >= 0 && parsed < endTime) {
                                setStartTime(parsed);
                            }
                        }}
                        className="time-input"
                    />
                </div>
                <div className="time-input-group">
                    <label>End Time</label>
                    <input
                        type="text"
                        value={formatTimeDetailed(endTime)}
                        onChange={(e) => {
                            const parsed = parseFloat(e.target.value.replace(':', '.'));
                            if (!isNaN(parsed) && parsed > startTime && parsed <= duration) {
                                setEndTime(parsed);
                            }
                        }}
                        className="time-input"
                    />
                </div>
                <div className="time-input-group">
                    <label>Duration</label>
                    <span className="duration-display">{formatTimeDetailed(endTime - startTime)}</span>
                </div>
            </div>

            {/* Quick Presets */}
            <div className="duration-presets">
                <span>Quick Duration:</span>
                {durationPresets.map(preset => (
                    <button
                        key={preset.label}
                        className="preset-btn"
                        onClick={() => applyPreset(preset.duration)}
                        disabled={startTime + preset.duration > duration}
                    >
                        {preset.label}
                    </button>
                ))}
            </div>

            {/* Processing Progress */}
            {isProcessing && (
                <div className="processing-progress">
                    <div className="progress-header">
                        <span>Processing video...</span>
                        <span>{processingProgress}%</span>
                    </div>
                    <div className="progress-bar">
                        <div
                            className="progress-fill"
                            style={{ width: `${processingProgress}%` }}
                        ></div>
                    </div>
                </div>
            )}

            {/* Action Buttons */}
            <div className="trimmer-actions">
                <button
                    className="trim-btn primary"
                    onClick={handleTrim}
                    disabled={isProcessing || startTime >= endTime}
                >
                    {isProcessing ? (
                        <>
                            <span className="btn-spinner"></span>
                            Processing...
                        </>
                    ) : (
                        <>
                            ✂️ Trim Video
                        </>
                    )}
                </button>
                <button
                    className="trim-btn secondary"
                    onClick={handleCancel}
                    disabled={isProcessing}
                >
                    Cancel
                </button>
            </div>

            {/* Preview of trimmed video */}
            {previewUrl && (
                <div className="trimmed-preview">
                    <h4>✅ Trimmed Video Preview</h4>
                    <video
                        src={previewUrl}
                        controls
                        className="preview-video"
                    />
                    <a
                        href={previewUrl}
                        download="trimmed_video.webm"
                        className="download-link"
                    >
                        📥 Download Trimmed Video
                    </a>
                </div>
            )}

            {/* Hidden canvas for recording */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />
        </div>
    );
});

VideoTrimmer.displayName = 'VideoTrimmer';

export default VideoTrimmer;
