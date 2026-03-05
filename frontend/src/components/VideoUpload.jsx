import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { transcribeVideo, uploadVideo, getVideoInfo } from '../services/api';
import './VideoUpload.css';

const formatFileSize = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) {
        return '0 Bytes';
    }

    const units = ['Bytes', 'KB', 'MB', 'GB'];
    const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, unitIndex);

    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
};

const formatDurationDisplay = (seconds) => {
    if (!Number.isFinite(seconds) || seconds < 0) {
        return '0s';
    }

    const rounded = Math.round(seconds);
    const mins = Math.floor(rounded / 60);
    const secs = rounded % 60;

    if (mins <= 0) {
        return `${secs}s`;
    }

    return `${mins}m ${secs}s`;
};

const QUALITY_OPTIONS = [
    { value: 'low', label: '480p', desc: 'Fast' },
    { value: 'medium', label: '720p', desc: 'Balanced' },
    { value: 'high', label: '1080p', desc: 'Best' },
    { value: 'qhd', label: '1440p', desc: 'High' },
    { value: 'uhd', label: '2160p', desc: 'Ultra' }
];

const PLATFORM_OPTIONS = [
    { 
        value: 'original', 
        label: 'Original', 
        desc: 'Keep original ratio',
        duration: 'Custom',
        aspectRatio: 'Original'
    },
    { 
        value: 'instagram', 
        label: 'Instagram Reels', 
        desc: '15-90s vertical',
        duration: '15-90s',
        aspectRatio: '9:16'
    },
    { 
        value: 'youtube', 
        label: 'YouTube Shorts', 
        desc: '≤60s vertical',
        duration: '≤60s',
        aspectRatio: '9:16'
    },
    { 
        value: 'facebook', 
        label: 'Facebook Reels', 
        desc: '15-90s vertical',
        duration: '15-90s',
        aspectRatio: '9:16'
    },
    { 
        value: 'x', 
        label: 'X (Twitter)', 
        desc: '5s-60s vertical',
        duration: '5s-60s',
        aspectRatio: '9:16'
    },
    { 
        value: 'whatsapp', 
        label: 'WhatsApp Status', 
      desc: '≤30s vertical',
        duration: '≤30s',
        aspectRatio: '9:16'
    },
    { 
        value: 'linkedin', 
        label: 'LinkedIn', 
        desc: '3s-10min vertical',
        duration: '3s-10min',
        aspectRatio: '9:16'
    },
    { 
        value: 'snapchat', 
        label: 'Snapchat Spotlight', 
        desc: '≤60s vertical',
        duration: '≤60s',
        aspectRatio: '9:16'
    }
];

const VideoUpload = ({
    onVideoUpload,
    onTranscriptionComplete,
    onError,
    isProcessing,
    setIsProcessing
}) => {
    // Retry mechanism for fetching video metadata
    const fetchVideoMetadataWithRetry = useCallback(async (fileId, maxRetries = 3, delay = 2000) => {
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                const metadata = await getVideoInfo(fileId);
                return metadata;
            } catch (error) {
                if (attempt === maxRetries) {
                    throw error;
                }
                
                // Wait before retrying
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }, []);
    const fileInputRef = useRef(null);
    const previewUrlRef = useRef(null);

    const [file, setFile] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [statusMessage, setStatusMessage] = useState('');
    const [statusType, setStatusType] = useState('info');
    const [videoDuration, setVideoDuration] = useState(0);
    const [requestedDuration, setRequestedDuration] = useState(0);
    const [videoQuality, setVideoQuality] = useState('high');
    const [selectedPlatform, setSelectedPlatform] = useState('original');
    const [videoMetadata, setVideoMetadata] = useState(null);
    const [suggestedQualities, setSuggestedQualities] = useState([]);

    const isBusy = Boolean(isProcessing);

    const maxAllowedDuration = useMemo(() => {
        if (!videoDuration || videoDuration <= 0) {
            return 0;
        }

        return Math.max(0, Math.floor(videoDuration));
    }, [videoDuration]);

    const clampDuration = useCallback((value) => {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) {
            return 0;
        }

        return Math.max(0, Math.min(maxAllowedDuration, Math.round(parsed)));
    }, [maxAllowedDuration]);

    useEffect(() => {
        setRequestedDuration((previous) => clampDuration(previous));
    }, [clampDuration]);

    const requestedMinutes = Math.floor(requestedDuration / 60);
    const requestedSecondsPart = requestedDuration % 60;

    const updateVideoMetadata = useCallback((videoFile) => {
        const metadataUrl = URL.createObjectURL(videoFile);
        const video = document.createElement('video');
        video.preload = 'metadata';

        video.onloadedmetadata = () => {
            const duration = Number(video.duration) || 0;
            setVideoDuration(duration);

            if (duration > 0) {
                const durationFloor = Math.floor(duration);
                const suggested = Math.min(durationFloor, Math.max(0, Math.round(durationFloor * 0.25)));
                setRequestedDuration(suggested);
            } else {
                setRequestedDuration(0);
            }

            URL.revokeObjectURL(metadataUrl);
        };

        video.onerror = () => {
            setVideoDuration(0);
            setRequestedDuration(0);
            URL.revokeObjectURL(metadataUrl);
        };

        video.src = metadataUrl;
    }, []);

    const analyzeVideoQuality = useCallback((videoFile) => {
        const video = document.createElement('video');
        video.preload = 'metadata';

        video.onloadedmetadata = () => {
            const width = video.videoWidth || 0;
            const height = video.videoHeight || 0;
            const aspectRatio = width > 0 && height > 0 ? width / height : 0;

            // Determine available quality options based on source resolution
            const availableQualities = [];
            
            if (width >= 3840 && height >= 2160) {
                // 4K source - all options available
                availableQualities.push(
                    { value: 'uhd', label: '2160p', desc: 'Ultra HD', recommended: true },
                    { value: 'qhd', label: '1440p', desc: 'High', recommended: true },
                    { value: 'high', label: '1080p', desc: 'Best', recommended: true },
                    { value: 'medium', label: '720p', desc: 'Balanced', recommended: false },
                    { value: 'low', label: '480p', desc: 'Fast', recommended: false }
                );
            } else if (width >= 2560 && height >= 1440) {
                // 1440p source
                availableQualities.push(
                    { value: 'qhd', label: '1440p', desc: 'High', recommended: true },
                    { value: 'high', label: '1080p', desc: 'Best', recommended: true },
                    { value: 'medium', label: '720p', desc: 'Balanced', recommended: true },
                    { value: 'low', label: '480p', desc: 'Fast', recommended: false }
                );
            } else if (width >= 1920 && height >= 1080) {
                // 1080p source
                availableQualities.push(
                    { value: 'high', label: '1080p', desc: 'Best', recommended: true },
                    { value: 'medium', label: '720p', desc: 'Balanced', recommended: true },
                    { value: 'low', label: '480p', desc: 'Fast', recommended: false }
                );
            } else if (width >= 1280 && height >= 720) {
                // 720p source
                availableQualities.push(
                    { value: 'medium', label: '720p', desc: 'Balanced', recommended: true },
                    { value: 'low', label: '480p', desc: 'Fast', recommended: true }
                );
            } else if (width >= 854 && height >= 480) {
                // 480p source
                availableQualities.push(
                    { value: 'low', label: '480p', desc: 'Fast', recommended: true }
                );
            } else {
                // Low resolution source
                availableQualities.push(
                    { value: 'low', label: '480p', desc: 'Fast', recommended: true }
                );
            }

            setSuggestedQualities(availableQualities);
            
            // Set default quality to the highest recommended option
            const recommendedOption = availableQualities.find(q => q.recommended);
            if (recommendedOption) {
                setVideoQuality(recommendedOption.value);
            }
        };

        video.onerror = () => {
            // Fallback to default qualities if metadata fails
            setSuggestedQualities(QUALITY_OPTIONS.map(q => ({ ...q, recommended: q.value === 'high' })));
        };

        video.src = URL.createObjectURL(videoFile);
    }, []);

    const clearSelectedFile = useCallback(() => {
        setFile(null);
        setVideoDuration(0);
        setUploadProgress(0);
        setStatusMessage('');
        setStatusType('info');
        setRequestedDuration(0);

        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, []);

    const handleFileSelection = useCallback((selectedFile) => {
        if (!selectedFile || !selectedFile.type.startsWith('video/')) {
            setStatusType('error');
            setStatusMessage('Please choose a valid video file.');
            return;
        }

        setFile(selectedFile);
        setStatusType('info');
        setStatusMessage('File selected. Analyzing video quality...');
        setUploadProgress(0);

        updateVideoMetadata(selectedFile);
        analyzeVideoQuality(selectedFile);
    }, [updateVideoMetadata]);

    const handleDrop = useCallback((event) => {
        event.preventDefault();
        setIsDragging(false);

        const droppedFile = event.dataTransfer.files?.[0];
        handleFileSelection(droppedFile);
    }, [handleFileSelection]);

    const handleDurationSecondsInput = useCallback((event) => {
        setRequestedDuration(clampDuration(event.target.value));
    }, [clampDuration]);

    const handleDurationMinutesInput = useCallback((event) => {
        const rawMinutes = Number(event.target.value);
        const minutes = Number.isFinite(rawMinutes) ? Math.max(0, Math.floor(rawMinutes)) : 0;
        const total = (minutes * 60) + requestedSecondsPart;
        setRequestedDuration(clampDuration(total));
    }, [clampDuration, requestedSecondsPart]);

    const handleDurationClockSecondsInput = useCallback((event) => {
        const rawSeconds = Number(event.target.value);
        const seconds = Number.isFinite(rawSeconds)
            ? Math.max(0, Math.min(59, Math.floor(rawSeconds)))
            : 0;
        const total = (requestedMinutes * 60) + seconds;
        setRequestedDuration(clampDuration(total));
    }, [clampDuration, requestedMinutes]);

    const handleUploadAndTranscribe = useCallback(async () => {
        if (!file) {
            setStatusType('error');
            setStatusMessage('Select a video file first.');
            return;
        }

        setStatusType('info');
        setStatusMessage('Uploading video...');
        setUploadProgress(0);
        setIsProcessing?.(true);

        try {
            const uploadResult = await uploadVideo(file, (progressValue) => {
                const safeProgress = Math.max(0, Math.min(100, Number(progressValue) || 0));
                const mappedProgress = Math.round(safeProgress * 0.65);
                setUploadProgress(mappedProgress);
                if (safeProgress < 100) {
                    setStatusMessage('Uploading video...');
                } else {
                    setStatusMessage('Upload complete. Optimizing format on server...');
                }
            });

            setUploadProgress((prev) => Math.max(prev, 70));
            setStatusMessage('Upload validated. Generating transcript...');

            previewUrlRef.current = URL.createObjectURL(file);

            // Fetch real video metadata after upload with retry mechanism
            let realMetadata = null;
            try {
                realMetadata = await fetchVideoMetadataWithRetry(uploadResult.file_id);
            } catch (error) {
                console.warn('Could not fetch video metadata:', error);
            }

            onVideoUpload?.({
                file_id: uploadResult.file_id,
                fileId: uploadResult.file_id,
                url: previewUrlRef.current,
                name: file.name,
                size: file.size,
                duration: realMetadata?.duration || videoDuration,
                subtitle_url: uploadResult.subtitle_url || null,
                quality: videoQuality,
                target_duration: requestedDuration,
                aspect_ratio: selectedPlatform, // Add selected aspect ratio
                title: file.name.replace(/\.[^/.]+$/, ""),
                genre: 'Entertainment',
                releaseYear: new Date().getFullYear().toString(),
                starring: 'Unknown',
                metadata: realMetadata
            });

            setUploadProgress((prev) => Math.max(prev, 72));
            setStatusMessage('Running backend transcription...');
            const transcriptionResult = await transcribeVideo(uploadResult.file_id);
            setUploadProgress((prev) => Math.max(prev, 96));

            const transcriptText = String(
                transcriptionResult?.text
                || transcriptionResult?.transcription
                || ''
            );
            const safeSegments = Array.isArray(transcriptionResult?.segments)
                ? transcriptionResult.segments
                : [];
            const derivedWordCount = transcriptText
                ? transcriptText.split(/\s+/).filter(Boolean).length
                : 0;

            onTranscriptionComplete?.({
                transcript: String(transcriptionResult?.transcription || transcriptText),
                text: transcriptText,
                segments: safeSegments,
                duration: Number(transcriptionResult?.duration) || videoDuration || 0,
                confidence: Number(transcriptionResult?.confidence) || 0,
                wordCount: Number(transcriptionResult?.wordCount) || derivedWordCount,
                language: String(transcriptionResult?.language || 'unknown')
            });

            setStatusType('success');
            setStatusMessage('Upload and transcription complete.');
            setUploadProgress(100);
        } catch (error) {
            const message = error?.message || 'Failed to upload or transcribe video.';
            setStatusType('error');
            setStatusMessage(message);
            onError?.(message);
        } finally {
            setIsProcessing?.(false);
        }
    }, [
        file,
        onError,
        onTranscriptionComplete,
        onVideoUpload,
        requestedDuration,
        setIsProcessing,
        videoDuration,
        videoQuality,
        selectedPlatform
    ]);

    const handlePlatformChange = useCallback((event) => {
        const newPlatform = event.target.value;
        setSelectedPlatform(newPlatform);
        
        // If not original (custom), set duration to platform's duration
        if (newPlatform !== 'original') {
            const platform = PLATFORM_OPTIONS.find(p => p.value === newPlatform);
            if (platform && platform.duration !== 'Custom') {
                // Parse duration from format like "15-90s" or "≤60s" or "15s-10min"
                const durationStr = platform.duration;
                let targetDuration = 0;
                
                if (durationStr.includes('-')) {
                    // Range format like "15-90s" or "15s-10min"
                    const parts = durationStr.split('-');
                    if (parts.length === 2) {
                        const minPart = parts[0].trim();
                        const maxPart = parts[1].trim();
                        
                        // Extract number from min part
                        const minMatch = minPart.match(/(\d+)/);
                        if (minMatch) {
                            targetDuration = parseInt(minMatch[1]);
                        }
                    }
                } else if (durationStr.includes('≤')) {
                    // Max format like "≤60s"
                    const match = durationStr.match(/≤(\d+)/);
                    if (match) {
                        targetDuration = parseInt(match[1]);
                    }
                } else if (durationStr.includes('min')) {
                    // Minutes format like "10min"
                    const match = durationStr.match(/(\d+)min/);
                    if (match) {
                        targetDuration = parseInt(match[1]) * 60;
                    }
                } else if (durationStr.includes('s')) {
                    // Seconds format like "60s"
                    const match = durationStr.match(/(\d+)s/);
                    if (match) {
                        targetDuration = parseInt(match[1]);
                    }
                }
                
                // Ensure target duration doesn't exceed source duration
                const maxDuration = Math.max(0, Math.floor(videoDuration));
                const clampedDuration = Math.min(targetDuration, maxDuration);
                
                setRequestedDuration(clampedDuration);
            }
        }
    }, [videoDuration]);

    return (
        <div className="upload-container">
            <div
                className={`upload-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={(event) => {
                    event.preventDefault();
                    setIsDragging(true);
                }}
                onDragLeave={(event) => {
                    event.preventDefault();
                    setIsDragging(false);
                }}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        fileInputRef.current?.click();
                    }
                }}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/*"
                    className="file-input"
                    onChange={(event) => handleFileSelection(event.target.files?.[0])}
                />

                {!file ? (
                    <div className="upload-placeholder">
                        <div className="upload-icon">
                            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M12 16V4M12 4l-4 4M12 4l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <div className="upload-text">
                            <span className="upload-text-main">Drop a video here or click to browse</span>
                            <span className="upload-text-sub">MP4, MOV, AVI and other common formats</span>
                        </div>
                        <button type="button" className="browse-button">Choose File</button>
                    </div>
                ) : (
                    <div className="selected-file">
                        <div className="file-preview">
                            <div className="file-icon">
                                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M4 5a2 2 0 0 1 2-2h6l4 4h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    <path d="M10 12l5 3-5 3v-6z" fill="currentColor" />
                                </svg>
                            </div>
                            <div className="file-info">
                                <div className="file-name">{file.name}</div>
                                <div className="file-size">
                                    {formatFileSize(file.size)}
                                    {videoDuration > 0 ? ` | ${formatDurationDisplay(videoDuration)}` : ''}
                                </div>
                            </div>
                            <button
                                type="button"
                                className="remove-file"
                                onClick={(event) => {
                                    event.stopPropagation();
                                    clearSelectedFile();
                                }}
                                aria-label="Remove selected file"
                            >
                                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M6 18L18 6M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {file && (
                <div className="horizontal-controls">
                    <div className="control-panel duration-panel">
                        <div className="panel-header">
                            <div className="panel-icon">⏱️</div>
                            <div>
                                <div className="panel-title">Duration Settings</div>
                                <div className="panel-subtitle">Configure output length and timing</div>
                            </div>
                        </div>
                        <div className="duration-controls">
                            <div className="duration-metrics">
                                <div className="duration-metric">
                                    <div className="duration-metric-label">Source</div>
                                    <div className="duration-metric-value">{formatDurationDisplay(videoDuration)}</div>
                                </div>
                                <div className="duration-metric">
                                    <div className="duration-metric-label">Target</div>
                                    <div className="duration-metric-value">{formatDurationDisplay(requestedDuration)}</div>
                                </div>
                            </div>

                            <div className="slider-section">
                                <div className="slider-header">
                                    <span className="slider-title">Target Duration</span>
                                    <span className="slider-value">{formatDurationDisplay(requestedDuration)}</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max={String(maxAllowedDuration)}
                                    value={requestedDuration}
                                    onChange={(event) => setRequestedDuration(clampDuration(event.target.value))}
                                    className="duration-slider"
                                    disabled={isBusy || maxAllowedDuration <= 0}
                                />
                                <div className="duration-labels">
                                    <span>0s</span>
                                    <span>{formatDurationDisplay(maxAllowedDuration)}</span>
                                </div>
                            </div>

                            <div className="input-controls">
                                <div className="input-group">
                                    <label className="input-label">Total Seconds</label>
                                    <input
                                        type="number"
                                        min="0"
                                        max={maxAllowedDuration}
                                        value={requestedDuration}
                                        onChange={handleDurationSecondsInput}
                                        className="input-field"
                                        disabled={isBusy || maxAllowedDuration <= 0}
                                    />
                                </div>
                                <div className="input-group">
                                    <label className="input-label">Minutes : Seconds</label>
                                    <div className="duration-clock-row">
                                        <input
                                            type="number"
                                            min="0"
                                            max={Math.max(0, Math.floor(maxAllowedDuration / 60))}
                                            value={requestedMinutes}
                                            onChange={handleDurationMinutesInput}
                                            className="input-field"
                                            disabled={isBusy || maxAllowedDuration <= 0}
                                        />
                                        <span className="duration-clock-sep">:</span>
                                        <input
                                            type="number"
                                            min="0"
                                            max="59"
                                            value={requestedSecondsPart}
                                            onChange={handleDurationClockSecondsInput}
                                            className="input-field"
                                            disabled={isBusy || maxAllowedDuration <= 0}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="control-panel quality-panel">
                        <div className="panel-header">
                            <div className="panel-icon">🎬</div>
                            <div>
                                <div className="panel-title">Output Settings</div>
                                <div className="panel-subtitle">Configure platform and quality</div>
                            </div>
                        </div>
                        <div className="quality-controls">
                            <div className="platform-selector">
                                <div className="platform-controls">
                                    <div className="platform-group">
                                        <label className="platform-label">Platform Preset</label>
                                        <select
                                            className="platform-select"
                                            value={selectedPlatform}
                                            onChange={handlePlatformChange}
                                            disabled={isBusy}
                                        >
                                            {PLATFORM_OPTIONS.map((platform) => (
                                                <option key={platform.value} value={platform.value}>
                                                    {platform.label} ({platform.duration})
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            </div>
                            
                            <div className="quality-options">
                                {(suggestedQualities.length > 0 ? suggestedQualities : QUALITY_OPTIONS).map((option) => (
                                    <label
                                        key={option.value}
                                        className={`quality-option ${videoQuality === option.value ? 'selected' : ''} ${option.recommended ? 'recommended' : ''}`}
                                    >
                                        <input
                                            type="radio"
                                            name="video-quality"
                                            value={option.value}
                                            checked={videoQuality === option.value}
                                            onChange={(event) => setVideoQuality(event.target.value)}
                                            disabled={isBusy}
                                        />
                                        <span className="quality-option-label">{option.label}</span>
                                        <span className="quality-option-desc">{option.desc}</span>
                                        {option.recommended && (
                                            <span className="quality-badge">Recommended</span>
                                        )}
                                    </label>
                                ))}
                            </div>
                            
                            <div className="platform-info">
                                <div className="platform-current">
                                    <div className="platform-info-item">
                                        <span className="platform-info-label">Platform</span>
                                        <span className="platform-info-value">
                                            {PLATFORM_OPTIONS.find(p => p.value === selectedPlatform)?.label}
                                        </span>
                                    </div>
                                    <div className="platform-info-item">
                                        <span className="platform-info-label">Duration</span>
                                        <span className="platform-info-value">
                                            {PLATFORM_OPTIONS.find(p => p.value === selectedPlatform)?.duration}
                                        </span>
                                    </div>
                                    <div className="platform-info-item">
                                        <span className="platform-info-label">Aspect Ratio</span>
                                        <span className="platform-info-value">
                                            {PLATFORM_OPTIONS.find(p => p.value === selectedPlatform)?.aspectRatio}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {isBusy && (
                <div className="progress-container">
                    <div className="progress-header">
                        <span>Processing</span>
                        <span>{uploadProgress}%</span>
                    </div>
                    <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
                    </div>
                </div>
            )}

            {statusMessage && (
                <div className={`status-message status-${statusType}`}>
                    <span className="status-icon">i</span>
                    <span>{statusMessage}</span>
                </div>
            )}

            <div className="action-buttons">
                <button
                    type="button"
                    className="primary-button"
                    onClick={handleUploadAndTranscribe}
                    disabled={!file || isBusy}
                >
                    {isBusy ? <span className="button-spinner" /> : null}
                    <span>{isBusy ? 'Working...' : 'Upload and Analyze'}</span>
                </button>

                <button
                    type="button"
                    className="secondary-button"
                    onClick={clearSelectedFile}
                    disabled={isBusy || !file}
                >
                    Clear
                </button>
            </div>
        </div>
    );
};

VideoUpload.displayName = 'VideoUpload';

export default memo(VideoUpload);
