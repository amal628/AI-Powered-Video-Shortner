import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './VideoPreview.css';
import VideoMetadata from './VideoMetadata';
import SubtitleControls from './SubtitleControls';

// Social media platform aspect ratios
const SOCIAL_MEDIA_RATIOS = {
    'original': { label: 'Original', ratio: 'auto', width: 'auto', height: 'auto' },
    'instagram': { label: 'Instagram Reels', ratio: '9:16', width: '100%', height: '177.78%' },
    'youtube': { label: 'YouTube Shorts', ratio: '9:16', width: '100%', height: '177.78%' },
    'facebook': { label: 'Facebook Reels', ratio: '9:16', width: '100%', height: '177.78%' },
    'x': { label: 'X (Twitter)', ratio: '9:16', width: '100%', height: '177.78%' },
    'whatsapp': { label: 'WhatsApp Status', ratio: '9:16', width: '100%', height: '177.78%' },
    'linkedin': { label: 'LinkedIn', ratio: '9:16', width: '100%', height: '177.78%' },
    'snapchat': { label: 'Snapchat Spotlight', ratio: '9:16', width: '100%', height: '177.78%' },
    '16:9': { label: 'YouTube/Netflix', ratio: '16:9', width: '100%', height: '56.25%' },
    '4:3': { label: 'Classic TV', ratio: '4:3', width: '100%', height: '75%' },
    '1:1': { label: 'Square', ratio: '1:1', width: '100%', height: '100%' },
    '21:9': { label: 'Cinematic', ratio: '21:9', width: '100%', height: '42.86%' }
};

const formatTime = (seconds) => {
    if (!Number.isFinite(seconds) || seconds <= 0) {
        return '0:00';
    }

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`;
};

const VideoPreview = ({ videoUrl, transcript, title = 'Video Preview', showSubtitles = false, showMetadata = false, metadata = {}, aspectRatio = 'auto', fileId, onVideoChange, onVideoRemove, onNarrativeAnalysis, onProcessingComplete, isProcessing, setIsProcessing }) => {
    const videoRef = useRef(null);
    const containerRef = useRef(null);
    const [isLoading, setIsLoading] = useState(Boolean(videoUrl));
    const [videoError, setVideoError] = useState('');
    const [videoMeta, setVideoMeta] = useState({
        width: 0,
        height: 0,
        duration: 0
    });

    // Playback control states
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [showControls, setShowControls] = useState(true);

    // View mode states
    const [viewMode, setViewMode] = useState('default'); // 'default', 'theater', 'fullscreen'
    const [subtitlesEnabled, setSubtitlesEnabled] = useState(showSubtitles);
    const [subtitleLanguage, setSubtitleLanguage] = useState('en');
    const [currentSubtitleUrl, setCurrentSubtitleUrl] = useState(null);
    const [showSubtitleControls, setShowSubtitleControls] = useState(false);

    // Skip forward/backward seconds
    const SKIP_SECONDS = 10;

    useEffect(() => {
        setIsLoading(Boolean(videoUrl));
        setVideoError('');
    }, [videoUrl]);

    useEffect(() => {
        setSubtitlesEnabled(showSubtitles);
    }, [showSubtitles]);

    const handleSubtitleToggle = (enabled) => {
        setShowSubtitleControls(enabled);
    };

    const handleSubtitleChange = (subtitleUrl) => {
        setCurrentSubtitleUrl(subtitleUrl);
        if (subtitleUrl) {
            setShowSubtitleControls(true);
            setSubtitlesEnabled(true);
        }
    };

    const handleLoadedMetadata = () => {
        const video = videoRef.current;
        if (!video) {
            setIsLoading(false);
            return;
        }

        setVideoMeta({
            width: video.videoWidth || 0,
            height: video.videoHeight || 0,
            duration: video.duration || 0
        });
        setIsLoading(false);
    };

    const handleVideoError = () => {
        setVideoError('Failed to load video preview.');
        setIsLoading(false);
    };

    const handleTimeUpdate = () => {
        const video = videoRef.current;
        if (video) {
            setCurrentTime(video.currentTime);
        }
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    // Playback control functions
    const togglePlay = useCallback(() => {
        const video = videoRef.current;
        if (video) {
            if (isPlaying) {
                video.pause();
            } else {
                video.play();
            }
        }
    }, [isPlaying]);

    const skipForward = useCallback(() => {
        const video = videoRef.current;
        if (video) {
            video.currentTime = Math.min(video.currentTime + SKIP_SECONDS, video.duration);
        }
    }, []);

    const skipBackward = useCallback(() => {
        const video = videoRef.current;
        if (video) {
            video.currentTime = Math.max(video.currentTime - SKIP_SECONDS, 0);
        }
    }, []);

    const handleVolumeChange = useCallback((e) => {
        const video = videoRef.current;
        const newVolume = parseFloat(e.target.value);
        if (video) {
            video.volume = newVolume;
            setVolume(newVolume);
            setIsMuted(newVolume === 0);
        }
    }, []);

    const toggleMute = useCallback(() => {
        const video = videoRef.current;
        if (video) {
            if (isMuted) {
                video.volume = volume || 1;
                video.muted = false;
                setIsMuted(false);
            } else {
                video.muted = true;
                setIsMuted(true);
            }
        }
    }, [isMuted, volume]);

    const handlePlaybackRateChange = useCallback((rate) => {
        const video = videoRef.current;
        if (video) {
            video.playbackRate = rate;
            setPlaybackRate(rate);
        }
    }, []);

    const toggleSubtitles = useCallback(() => {
        const video = videoRef.current;
        if (video && video.textTracks.length > 0) {
            const track = video.textTracks[0];
            if (subtitlesEnabled) {
                track.mode = 'hidden';
                setSubtitlesEnabled(false);
            } else {
                track.mode = 'showing';
                setSubtitlesEnabled(true);
            }
        } else {
            setSubtitlesEnabled(!subtitlesEnabled);
        }
    }, [subtitlesEnabled]);

    const updateSubtitleTrack = useCallback((language) => {
        const video = videoRef.current;
        if (!video) return;

        // Remove existing tracks
        while (video.textTracks.length > 0) {
            const track = video.textTracks[0];
            video.removeChild(track);
        }

        if (subtitlesEnabled && transcript) {
            // Create new subtitle track
            const track = video.addTextTrack('subtitles', 'Subtitles', language);
            track.mode = 'showing';
            
            // Convert transcript to plain text string
            let transcriptText = '';
            if (typeof transcript === 'string') {
                transcriptText = transcript;
            } else if (Array.isArray(transcript)) {
                // If transcript is an array of segment objects
                transcriptText = transcript.map(seg => 
                    typeof seg === 'string' ? seg : (seg?.text || '')
                ).join(' ').trim();
            } else if (typeof transcript === 'object' && transcript?.text) {
                // If transcript is an object with text property
                transcriptText = transcript.text;
            }
            
            // Split transcript into segments for better timing
            const words = transcriptText.split(' ').filter(w => w.trim());
            const totalDuration = videoMeta.duration || 60;
            const wordsPerSegment = Math.ceil(words.length / 10); // Create 10 segments
            const segmentDuration = totalDuration / 10;

            for (let i = 0; i < 10; i++) {
                const start = i * segmentDuration;
                const end = (i + 1) * segmentDuration;
                const startIndex = i * wordsPerSegment;
                const endIndex = Math.min(startIndex + wordsPerSegment, words.length);
                const segmentText = words.slice(startIndex, endIndex).join(' ');
                
                if (segmentText.trim()) {
                    const cue = new VTTCue(start, end, segmentText);
                    track.addCue(cue);
                }
            }
        }
    }, [subtitlesEnabled, transcript, videoMeta.duration]);

    // Update subtitle track when language changes or subtitles are toggled
    useEffect(() => {
        updateSubtitleTrack(subtitleLanguage);
    }, [subtitleLanguage, subtitlesEnabled, updateSubtitleTrack]);

    // View mode functions
    const toggleTheaterMode = useCallback(() => {
        setViewMode(prev => prev === 'theater' ? 'default' : 'theater');
    }, []);

    const toggleFullscreen = useCallback(() => {
        const container = containerRef.current;
        if (!container) return;

        if (viewMode === 'fullscreen') {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
            setViewMode('default');
        } else {
            if (container.requestFullscreen) {
                container.requestFullscreen();
            }
            setViewMode('fullscreen');
        }
    }, [viewMode]);

    // Handle fullscreen change events
    useEffect(() => {
        const handleFullscreenChange = () => {
            if (!document.fullscreenElement) {
                setViewMode('default');
            }
        };

        document.addEventListener('fullscreenchange', handleFullscreenChange);
        return () => {
            document.removeEventListener('fullscreenchange', handleFullscreenChange);
        };
    }, []);

    // Auto-hide controls after inactivity
    useEffect(() => {
        let timeout;
        const handleMouseMove = () => {
            setShowControls(true);
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                if (isPlaying) {
                    setShowControls(false);
                }
            }, 3000);
        };

        const container = containerRef.current;
        if (container) {
            container.addEventListener('mousemove', handleMouseMove);
        }

        return () => {
            clearTimeout(timeout);
            if (container) {
                container.removeEventListener('mousemove', handleMouseMove);
            }
        };
    }, [isPlaying]);

    const videoInfo = useMemo(() => {
        if (!videoMeta.width || !videoMeta.height) {
            return null;
        }

        return {
            resolution: `${videoMeta.width}x${videoMeta.height}`,
            duration: formatTime(videoMeta.duration)
        };
    }, [videoMeta]);

    const progress = videoMeta.duration > 0 ? (currentTime / videoMeta.duration) * 100 : 0;

    // Get aspect ratio configuration
    const getAspectRatioConfig = () => {
        return SOCIAL_MEDIA_RATIOS[aspectRatio] || SOCIAL_MEDIA_RATIOS['original'];
    };

    const aspectRatioConfig = getAspectRatioConfig();

    return (
        <div
            ref={containerRef}
            className={`video-preview-container ${viewMode}`}
            aria-label={title}
        >
            <div className={`video-wrapper ${viewMode}`}>
                {isLoading && (
                    <div className="video-loading">
                        <div className="loading-spinner" />
                        <p>Loading video...</p>
                    </div>
                )}

                {videoError && (
                    <div className="video-error">
                        <div className="error-icon">Warning</div>
                        <p>{videoError}</p>
                    </div>
                )}

                <video
                    ref={videoRef}
                    className={`preview-video ${subtitlesEnabled ? 'subtitles-enabled' : ''}`}
                    style={{
                        width: aspectRatioConfig.width,
                        height: aspectRatioConfig.height,
                        objectFit: 'contain',
                        margin: '0 auto',
                        display: 'block'
                    }}
                    src={videoUrl}
                    preload="metadata"
                    onLoadedMetadata={handleLoadedMetadata}
                    onError={handleVideoError}
                    onTimeUpdate={handleTimeUpdate}
                    onPlay={handlePlay}
                    onPause={handlePause}
                />

                {/* Custom Controls Overlay */}
                <div className={`video-controls ${showControls ? 'visible' : 'hidden'}`}>
                    {/* Progress Bar */}
                    <div className="progress-container">
                        <div
                            className="progress-bar"
                            onClick={(e) => {
                                const video = videoRef.current;
                                if (video) {
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    const pos = (e.clientX - rect.left) / rect.width;
                                    video.currentTime = pos * video.duration;
                                }
                            }}
                        >
                            <div className="progress-filled" style={{ width: `${progress}%` }} />
                            <div className="progress-handle" style={{ left: `${progress}%` }} />
                        </div>
                    </div>

                    {/* Control Buttons Row */}
                    <div className="controls-row">
                        {/* Left Controls */}
                        <div className="controls-left">
                            {/* Skip Backward */}
                            <button
                                className="control-btn"
                                onClick={skipBackward}
                                title={`Backward ${SKIP_SECONDS}s`}
                            >
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M12.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0019 16V8a1 1 0 00-1.6-.8l-5.334 4z" fill="currentColor" />
                                    <path d="M4.066 11.2a1 1 0 000 1.6l5.334 4A1 1 0 0011 16V8a1 1 0 00-1.6-.8l-5.334 4z" fill="currentColor" />
                                </svg>
                                <span className="skip-text">-{SKIP_SECONDS}</span>
                            </button>

                            {/* Play/Pause */}
                            <button className="control-btn play-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
                                {isPlaying ? (
                                    <svg viewBox="0 0 24 24" fill="none">
                                        <rect x="6" y="4" width="4" height="16" fill="currentColor" />
                                        <rect x="14" y="4" width="4" height="16" fill="currentColor" />
                                    </svg>
                                ) : (
                                    <svg viewBox="0 0 24 24" fill="none">
                                        <path d="M5 3l14 9-14 9V3z" fill="currentColor" />
                                    </svg>
                                )}
                            </button>

                            {/* Skip Forward */}
                            <button
                                className="control-btn"
                                onClick={skipForward}
                                title={`Forward ${SKIP_SECONDS}s`}
                            >
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M11.933 11.2a1 1 0 000 1.6l-5.334 4A1 1 0 005 8v8a1 1 0 001.6.8l5.334-4z" fill="currentColor" />
                                    <path d="M19.933 11.2a1 1 0 000 1.6l-5.334 4A1 1 0 0013 16V8a1 1 0 001.6.8l5.334-4z" fill="currentColor" />
                                </svg>
                                <span className="skip-text">+{SKIP_SECONDS}</span>
                            </button>

                            {/* Volume Control */}
                            <div className="volume-control">
                                <button className="control-btn" onClick={toggleMute} title={isMuted ? 'Unmute' : 'Mute'}>
                                    {isMuted || volume === 0 ? (
                                        <svg viewBox="0 0 24 24" fill="none">
                                            <path d="M3.63 3.63a.996.996 0 000 1.41L7.29 8.7 7 9H4c-.55 0-1 .45-1 1v4c0 .55.45 1 1 1h3l3.29 3.29c.63.63 1.71.18 1.71-.71v-4.17l4.18 4.18c-.49.37-1.02.68-1.6.91-.36.15-.58.53-.58.92 0 .72.73 1.18 1.39.91.8-.33 1.55-.77 2.22-1.31l1.34 1.34a.996.996 0 101.41-1.41L5.05 3.63a.996.996 0 00-1.42 0zM19 12c0 .82-.15 1.61-.41 2.34l1.53 1.53c.56-1.17.88-2.48.88-3.87 0-3.83-2.4-7.11-5.78-8.4-.59-.23-1.22.23-1.22.86v.19c0 .38.25.71.61.85C17.18 6.54 19 9.06 19 12zm-8.71-6.29l-.17.17L12 7.76V6.41c0-.89-1.08-1.33-1.71-.7zM16.5 12c0-1.77-1.02-3.29-2.5-4.03v1.79l2.48 2.48c.01-.08.02-.16.02-.24z" fill="currentColor" />
                                        </svg>
                                    ) : (
                                        <svg viewBox="0 0 24 24" fill="none">
                                            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="currentColor" />
                                        </svg>
                                    )}
                                </button>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={isMuted ? 0 : volume}
                                    onChange={handleVolumeChange}
                                    className="volume-slider"
                                    title="Volume"
                                />
                            </div>

                            {/* Time Display */}
                            <span className="time-display">
                                {formatTime(currentTime)} / {formatTime(videoMeta.duration)}
                            </span>
                        </div>

                        {/* Right Controls */}
                        <div className="controls-right">
                            {/* Playback Speed */}
                            <div className="playback-speed">
                                <select
                                    value={playbackRate}
                                    onChange={(e) => handlePlaybackRateChange(parseFloat(e.target.value))}
                                    title="Playback Speed"
                                >
                                    <option value="0.5">0.5x</option>
                                    <option value="0.75">0.75x</option>
                                    <option value="1">1x</option>
                                    <option value="1.25">1.25x</option>
                                    <option value="1.5">1.5x</option>
                                    <option value="2">2x</option>
                                </select>
                            </div>

                            {/* Subtitles Toggle with Language Selection */}
                            <div className="subtitle-settings">
                                <button
                                    className={`control-btn ${subtitlesEnabled ? 'active' : ''}`}
                                    onClick={toggleSubtitles}
                                    title={subtitlesEnabled ? 'Hide Subtitles' : 'Show Subtitles'}
                                >
                                    <svg viewBox="0 0 24 24" fill="none">
                                        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V6h16v12z" fill="currentColor" />
                                        <path d="M6 10h2v2H6zm0 4h8v2H6zm10 0h2v2h-2zm-6-4h8v2h-8z" fill="currentColor" />
                                    </svg>
                                </button>
                                {subtitlesEnabled && (
                                    <div className="subtitle-language-dropdown">
                                        <select
                                            value={subtitleLanguage}
                                            onChange={(e) => setSubtitleLanguage(e.target.value)}
                                            className="subtitle-language-select"
                                            title="Subtitle Language"
                                        >
                                            <option value="en">English</option>
                                            <option value="es">Spanish</option>
                                            <option value="fr">French</option>
                                            <option value="de">German</option>
                                            <option value="it">Italian</option>
                                            <option value="pt">Portuguese</option>
                                            <option value="ru">Russian</option>
                                            <option value="ja">Japanese</option>
                                            <option value="ko">Korean</option>
                                            <option value="zh">Chinese</option>
                                            <option value="hi">Hindi</option>
                                            <option value="ar">Arabic</option>
                                            <option value="ta">Tamil</option>
                                            <option value="ml">Malayalam</option>
                                            <option value="kn">Kannada</option>
                                            <option value="te">Telugu</option>
                                        </select>
                                    </div>
                                )}
                            </div>

                            {/* Theater Mode */}
                            <button
                                className={`control-btn ${viewMode === 'theater' ? 'active' : ''}`}
                                onClick={toggleTheaterMode}
                                title={viewMode === 'theater' ? 'Exit Theater Mode' : 'Theater Mode'}
                            >
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M19 6H5c-1.1 0-2 .9-2 2v8c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 10H5V8h14v8z" fill="currentColor" />
                                </svg>
                            </button>

                            {/* Fullscreen */}
                            <button
                                className={`control-btn ${viewMode === 'fullscreen' ? 'active' : ''}`}
                                onClick={toggleFullscreen}
                                title={viewMode === 'fullscreen' ? 'Exit Fullscreen' : 'Fullscreen'}
                            >
                                {viewMode === 'fullscreen' ? (
                                    <svg viewBox="0 0 24 24" fill="none">
                                        <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" fill="currentColor" />
                                    </svg>
                                ) : (
                                    <svg viewBox="0 0 24 24" fill="none">
                                        <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" fill="currentColor" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>
                </div>

            </div>

            {showMetadata && (
                <VideoMetadata
                    title={metadata.title || 'Video Title'}
                    language={metadata.language || 'English'}
                    genre={metadata.genre || 'Entertainment'}
                    releaseYear={metadata.releaseYear || '2024'}
                    starring={metadata.starring || 'Unknown'}
                    duration={metadata.duration || videoMeta?.duration || 0}
                    resolution={metadata.resolution || videoInfo?.resolution || '1920x1080'}
                    metadata={{
                        duration: metadata.duration || videoMeta?.duration,
                        resolution: metadata.resolution || videoInfo?.resolution,
                        codec: metadata.codec,
                        file_size: metadata.file_size,
                        width: metadata.width,
                        height: metadata.height,
                        fps: metadata.fps,
                        aspect_ratio: metadata.aspect_ratio,
                        audio_codec: metadata.audio_codec,
                        file_size_bytes: metadata.file_size_bytes
                    }}
                />
            )}
            
            {!showMetadata && transcript && (
                <div className="transcript-section">
                    <div className="transcript-header">
                        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M21 15V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            <path d="M7 8h10M7 12h10M7 16h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <span>Transcript</span>
                    </div>
                    <div className="transcript-content">
                        <p>{typeof transcript === 'string' 
                            ? transcript 
                            : (Array.isArray(transcript) 
                                ? transcript.map(seg => 
                                    typeof seg === 'string' 
                                        ? seg 
                                        : (seg?.text || '')
                                ).join(' ').trim()
                                : (transcript?.text || JSON.stringify(transcript, null, 2))
                            )
                        }</p>
                    </div>
                </div>
            )}

            {/* Subtitle Controls */}
            {fileId && (
                <SubtitleControls
                    fileId={fileId}
                    videoUrl={videoUrl}
                    onSubtitleToggle={handleSubtitleToggle}
                    onSubtitleChange={handleSubtitleChange}
                    currentSubtitleUrl={currentSubtitleUrl}
                    isProcessing={isProcessing}
                    setIsProcessing={setIsProcessing}
                />
            )}
        </div>
    );
};

export default VideoPreview;
