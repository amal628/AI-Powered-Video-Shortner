import { useCallback, useMemo, useState } from 'react';
import { downloadFile, getProcessingProgress, processVideo, segmentVideo } from '../services/api';
import './NarrativeAnalyzer.css';

const NarrativeAnalyzer = ({
    segments,
    videoUrl,
    fileId,
    targetDuration,
    quality,
    onVideoProcessingComplete,
    isProcessing,
    setIsProcessing,
    originalAspectRatio,
    onSegmentSelectionChange, // New prop for segment selection changes
    selectedSegments, // New prop for user-selected segments
    aiSuggestions, // New prop for AI suggestions
    onAiOverride, // New prop for AI override actions
    showAiSuggestions = true, // New prop to control AI suggestions visibility
    transcriptionPath // New prop for the transcription path
}) => {
    // Initialize state with props if provided
    const [userSelectedSegments, setUserSelectedSegments] = useState(selectedSegments || []);
    const [aiSuggestedSegments, setAiSuggestedSegments] = useState(aiSuggestions || []);
    const [aiOverrideMode, setAiOverrideMode] = useState(false);
    const [processingError, setProcessingError] = useState(null);
    const [processingProgress, setProcessingProgress] = useState(0);
    const [processingStatus, setProcessingStatus] = useState('');
    const [addSubtitles, setAddSubtitles] = useState(false);
    const [subtitleLanguage, setSubtitleLanguage] = useState('en');
    const [selectedPlatform, setSelectedPlatform] = useState('instagram_reels');
    const [selectedAspectRatio, setSelectedAspectRatio] = useState('9:16');
    const [showSegmentTimeline, setShowSegmentTimeline] = useState(true);
    const [detectedSegments, setDetectedSegments] = useState([]);

    const getStatusMessage = (status) => {
        const statusMessages = {
            pending: 'Waiting for processing to start...',
            starting: 'Initializing backend processing...',
            preparing: 'Preparing processing request...',
            server_processing: 'Backend is rendering your short video...',
            finalizing: 'Preparing final output URL...',
            completed: 'Video processing complete.',
            failed: 'Video processing failed.'
        };
        return statusMessages[status] || 'Processing...';
    };

    const formatDuration = (seconds) => {
        const safe = Number(seconds);
        if (!Number.isFinite(safe) || safe <= 0) {
            return '0:00';
        }
        const mins = Math.floor(safe / 60);
        const secs = Math.round(safe % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Handle segment preview
    const handlePreviewSegment = (start, end) => {
        if (onPreviewSegment) {
            onPreviewSegment(start, end);
        }
    };

    const handleSegmentVideo = useCallback(async () => {
        if (!videoUrl) {
            setProcessingError('Video preview URL is missing. Please upload again.');
            return;
        }

        if (!transcriptionPath) {
            setProcessingError('Transcription path is missing. Please upload again.');
            return;
        }

        setIsProcessing(true);
        setProcessingError(null);
        setProcessingProgress(0);
        setProcessingStatus(getStatusMessage('starting'));

        try {
            const result = await segmentVideo({
                video_path: videoUrl,
                transcription_path: transcriptionPath,
            });

            setDetectedSegments(result.segments);
            setProcessingStatus('Segmentation complete. Please select your segments.');

        } catch (error) {
            console.error('Video segmentation failed:', error);
            setProcessingError(`Video segmentation failed: ${error?.message || 'Unknown error'}`);
        } finally {
            setIsProcessing(false);
        }
    }, [videoUrl, transcriptionPath, setIsProcessing]);

    const handleSegmentVideo = useCallback(async () => {
        if (!videoUrl) {
            setProcessingError('Video preview URL is missing. Please upload again.');
            return;
        }

        if (!transcriptionPath) {
            setProcessingError('Transcription path is missing. Please upload again.');
            return;
        }

        setIsProcessing(true);
        setProcessingError(null);
        setProcessingProgress(0);
        setProcessingStatus(getStatusMessage('starting'));

        try {
            const result = await segmentVideo({
                video_path: videoUrl,
                transcription_path: transcriptionPath,
            });

            setDetectedSegments(result.segments);
            setProcessingStatus('Segmentation complete. Please select your segments.');

        } catch (error) {
            console.error('Video segmentation failed:', error);
            setProcessingError(`Video segmentation failed: ${error?.message || 'Unknown error'}`);
        } finally {
            setIsProcessing(false);
        }
    }, [videoUrl, transcriptionPath, setIsProcessing]);

    const handleGenerateVideo = useCallback(async () => {
        if (!videoUrl) {
            setProcessingError('Video preview URL is missing. Please upload again.');
            return;
        }

        if (!fileId) {
            setProcessingError('Missing file identifier. Please upload video again.');
            return;
        }

        // If AI override mode is active, use AI suggestions instead of user selections
        const segmentsToUse = aiOverrideMode ? aiSuggestedSegments : userSelectedSegments;
        if (!segmentsToUse || segmentsToUse.length === 0) {
            setProcessingError('Please select segments or enable AI override mode.');
            return;
        }

        // Update parent component with final selected segments
        onSegmentSelectionChange?.(segmentsToUse);

        setIsProcessing(true);
        setProcessingError(null);
        setProcessingProgress(0);
        setProcessingStatus(getStatusMessage('starting'));
        let progressPoller = null;

        const pullBackendProgress = async () => {
            try {
                const state = await getProcessingProgress(fileId);
                const numericProgress = Number(state?.progress);
                if (Number.isFinite(numericProgress)) {
                    const safeProgress = Math.max(0, Math.min(100, Math.round(numericProgress)));
                    setProcessingProgress(safeProgress);
                }

                const statusKey = String(state?.status || '').toLowerCase();
                const backendMessage = String(state?.message || '');
                if (backendMessage) {
                    setProcessingStatus(backendMessage);
                } else if (statusKey) {
                    setProcessingStatus(getStatusMessage(statusKey));
                }
            } catch (_) {
                // Ignore transient progress polling failures while processing request is active.
            }
        };

        try {
            const effectiveDuration = Number.isFinite(Number(targetDuration))
                ? Number(targetDuration)
                : undefined;

            await pullBackendProgress();
            progressPoller = window.setInterval(() => {
                pullBackendProgress();
            }, 900);

            const result = await processVideo(fileId, {
                target_duration: effectiveDuration,
                quality: quality || 'high',
                add_subtitles: addSubtitles,
                subtitle_language: addSubtitles ? subtitleLanguage : undefined,
                platform: selectedPlatform,
                aspect_ratio: selectedAspectRatio
            });

            const filename = result?.filename;
            if (!filename) {
                throw new Error('Backend did not return output filename.');
            }

            await pullBackendProgress();
            const finalVideoUrl = downloadFile(filename);

            onVideoProcessingComplete?.({
                url: finalVideoUrl,
                filename,
                actualDuration: result?.actual_duration,
                targetDuration: result?.target_duration,
                quality: result?.quality_used,
                subtitleUrl: result?.subtitle_url,
                hasSubtitles: addSubtitles,
                platform: selectedPlatform,
                aspectRatio: selectedAspectRatio,
                backendResponse: result
            });

            setProcessingProgress(100);
            setProcessingStatus(getStatusMessage('completed'));
        } catch (error) {
            console.error('Video processing failed:', error);
            setProcessingError(`Video processing failed: ${error?.message || 'Unknown error'}`);
        } finally {
            if (progressPoller) {
                window.clearInterval(progressPoller);
            }
            setIsProcessing(false);
        }
    }, [
        fileId,
        onVideoProcessingComplete,
        quality,
        setIsProcessing,
        targetDuration,
        videoUrl,
        addSubtitles,
        subtitleLanguage,
        selectedPlatform,
        selectedAspectRatio
    ]);

    // Calculate total duration for timeline visualization
    const totalDuration = useMemo(() => {
        if (!Array.isArray(segments) || segments.length === 0) return 0;
        return Math.max(...segments.map(s => s.end || 0));
    }, [segments]);

    const detectedSegmentPositions = useMemo(() => {
        if (!Array.isArray(detectedSegments) || detectedSegments.length === 0 || totalDuration <= 0) {
            return [];
        }

        return detectedSegments.map((segment, index) => {
            const start = segment.start || 0;
            const end = segment.end || 0;
            const duration = end - start;

            const left = (start / totalDuration) * 100;
            const width = (duration / totalDuration) * 100;

            return {
                ...segment,
                index,
                left,
                width,
                duration,
                displayText: segment.text ? segment.text.substring(0, 30) + '...' : `Segment ${index + 1}`
            };
        });
    }, [detectedSegments, totalDuration]);

    const detectedSegmentPositions = useMemo(() => {
        if (!Array.isArray(detectedSegments) || detectedSegments.length === 0 || totalDuration <= 0) {
            return [];
        }

        return detectedSegments.map((segment, index) => {
            const start = segment.start || 0;
            const end = segment.end || 0;
            const duration = end - start;

            const left = (start / totalDuration) * 100;
            const width = (duration / totalDuration) * 100;

            return {
                ...segment,
                index,
                left,
                width,
                duration,
                displayText: segment.text ? segment.text.substring(0, 30) + '...' : `Segment ${index + 1}`
            };
        });
    }, [detectedSegments, totalDuration]);

    // Format time for display
    const formatTime = (seconds) => {
        if (!Number.isFinite(seconds) || seconds <= 0) {
            return '0:00';
        }
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Calculate segment positions for timeline
    const segmentPositions = useMemo(() => {
        if (!Array.isArray(segments) || segments.length === 0 || totalDuration <= 0) {
            return [];
        }

        return segments.map((segment, index) => {
            const start = segment.start || 0;
            const end = segment.end || 0;
            const duration = end - start;

            const left = (start / totalDuration) * 100;
            const width = (duration / totalDuration) * 100;

            return {
                ...segment,
                index,
                left,
                width,
                duration,
                displayText: segment.text ? segment.text.substring(0, 30) + '...' : `Segment ${index + 1}`
            };
        });
    }, [segments, totalDuration]);

    // Calculate user-selected segment positions
    const userSelectedSegmentPositions = useMemo(() => {
        if (!Array.isArray(userSelectedSegments) || userSelectedSegments.length === 0 || totalDuration <= 0) {
            return [];
        }

        return userSelectedSegments.map((segment, index) => {
            const start = segment.start || 0;
            const end = segment.end || 0;
            const duration = end - start;

            const left = (start / totalDuration) * 100;
            const width = (duration / totalDuration) * 100;

            return {
                ...segment,
                index,
                left,
                width,
                duration,
                displayText: segment.text ? segment.text.substring(0, 30) + '...' : `User Segment ${index + 1}`,
                isUserSelected: true
            };
        });
    }, [userSelectedSegments, totalDuration]);

    // Calculate AI-suggested segment positions
    const aiSuggestedSegmentPositions = useMemo(() => {
        if (!Array.isArray(aiSuggestedSegments) || aiSuggestedSegments.length === 0 || totalDuration <= 0) {
            return [];
        }

        return aiSuggestedSegments.map((segment, index) => {
            const start = segment.start || 0;
            const end = segment.end || 0;
            const duration = end - start;

            const left = (start / totalDuration) * 100;
            const width = (duration / totalDuration) * 100;

            return {
                ...segment,
                index,
                left,
                width,
                duration,
                displayText: segment.text ? segment.text.substring(0, 30) + '...' : `AI Suggestion ${index + 1}`,
                isAiSuggested: true
            };
        });
    }, [aiSuggestedSegments, totalDuration]);

    return (
        <div className="narrative-analyzer">
            <div className="analyzer-header">
                <h4>Video Processing</h4>
                <div className="analysis-stats">
                    <span className="stat">{Array.isArray(segments) ? segments.length : 0} transcript segments</span>
                    <span className="stat">{formatDuration(targetDuration)} target duration</span>
                    <span className="stat">{formatDuration(totalDuration)} total duration</span>
                </div>
            </div>

            {/* Segment Timeline Visualization */}
            {Array.isArray(segments) && segments.length > 0 && (
                <div className="segment-timeline-section">
                    <div className="timeline-header">
                        <h5>Detected Segments</h5>
                        <button
                            className="timeline-toggle"
                            onClick={() => setShowSegmentTimeline(!showSegmentTimeline)}
                        >
                            {showSegmentTimeline ? 'Hide' : 'Show'} Timeline
                        </button>
                    </div>

                    {showSegmentTimeline && (
                        <div className="segment-timeline-container">
                            <div className="timeline-wrapper">
                                {/* Timeline Scale */}
                                <div className="timeline-scale">
                                    {Array.from({ length: 11 }, (_, i) => {
                                        const position = (i / 10) * 100;
                                        const time = (i / 10) * totalDuration;
                                        return (
                                            <div key={i} className="scale-marker" style={{ left: `${position}%` }}>
                                                <span className="scale-line"></span>
                                                <span className="scale-time">{formatTime(time)}</span>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Timeline Track */}
                                <div className="timeline-track">
                                    {/* Target Duration Marker */}
                                    {targetDuration && targetDuration > 0 && (
                                        <div
                                            className="target-duration-marker"
                                            style={{
                                                left: '0%',
                                                width: `${Math.min((targetDuration / totalDuration) * 100, 100)}%`
                                            }}
                                        >
                                            <span className="target-label">Target: {formatDuration(targetDuration)}</span>
                                        </div>
                                    )}

                                    {/* Detected Segments */}
                                    {detectedSegmentPositions.map((segment) => (
                                        <div
                                            key={segment.index}
                                            className="segment-marker detected"
                                            style={{
                                                left: `${segment.left}%`,
                                                width: `${segment.width}%`,
                                                backgroundColor: '#FFC107'
                                            }}
                                            title={`${formatTime(segment.start)} - ${formatTime(segment.end)} (${formatTime(segment.duration)})`}
                                            onClick={() => {
                                                // Add detected segment to user selections
                                                const updatedSegments = [...userSelectedSegments, segment];
                                                setUserSelectedSegments(updatedSegments);
                                                onSegmentSelectionChange?.(updatedSegments);
                                            }}
                                        >
                                            <div className="segment-content">
                                                <span className="segment-time">{formatTime(segment.start)}</span>
                                                <span className="segment-text">{segment.displayText}</span>
                                                <span className="segment-duration">{formatTime(segment.duration)}</span>
                                                <button className="add-segment-btn">+</button>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Detected Segments */}
                                    {detectedSegmentPositions.map((segment) => (
                                        <div
                                            key={segment.index}
                                            className="segment-marker detected"
                                            style={{
                                                left: `${segment.left}%`,
                                                width: `${segment.width}%`,
                                                backgroundColor: '#FFC107'
                                            }}
                                            title={`${formatTime(segment.start)} - ${formatTime(segment.end)} (${formatTime(segment.duration)})`}
                                            onClick={() => {
                                                // Add detected segment to user selections
                                                const updatedSegments = [...userSelectedSegments, segment];
                                                setUserSelectedSegments(updatedSegments);
                                                onSegmentSelectionChange?.(updatedSegments);
                                            }}
                                        >
                                            <div className="segment-content">
                                                <span className="segment-time">{formatTime(segment.start)}</span>
                                                <span className="segment-text">{segment.displayText}</span>
                                                <span className="segment-duration">{formatTime(segment.duration)}</span>
                                                <button className="add-segment-btn">+</button>
                                            </div>
                                        </div>
                                    ))}

                                    {/* User Selected Segments */}
                                    {userSelectedSegmentPositions.map((segment) => (
                                        <div
                                            key={segment.index}
                                            className="segment-marker user-selected"
                                            style={{
                                                left: `${segment.left}%`,
                                                width: `${segment.width}%`,
                                                backgroundColor: '#4CAF50'
                                            }}
                                            title={`${formatTime(segment.start)} - ${formatTime(segment.end)} (${formatTime(segment.duration)})`}
                                            onClick={() => {
                                                // Allow user to remove selected segment
                                                const updatedSegments = userSelectedSegments.filter(s =>
                                                    s.start !== segment.start || s.end !== segment.end
                                                );
                                                setUserSelectedSegments(updatedSegments);
                                                onSegmentSelectionChange?.(updatedSegments);
                                            }}
                                        >
                                            <div className="segment-content">
                                                <span className="segment-time">{formatTime(segment.start)}</span>
                                                <span className="segment-text">{segment.displayText}</span>
                                                <span className="segment-duration">{formatTime(segment.duration)}</span>
                                                <button className="remove-segment-btn">✕</button>
                                            </div>
                                        </div>
                                    ))}

                                    {/* AI Suggested Segments */}
                                    {showAiSuggestions && aiSuggestedSegmentPositions.map((segment) => (
                                        <div
                                            key={segment.index}
                                            className="segment-marker ai-suggested"
                                            style={{
                                                left: `${segment.left}%`,
                                                width: `${segment.width}%`,
                                                backgroundColor: '#2196F3',
                                                opacity: aiOverrideMode ? 1 : 0.5
                                            }}
                                            title={`${formatTime(segment.start)} - ${formatTime(segment.end)} (${formatTime(segment.duration)})`}
                                        >
                                            <div className="segment-content">
                                                <span className="segment-time">{formatTime(segment.start)}</span>
                                                <span className="segment-text">{segment.displayText}</span>
                                                <span className="segment-duration">{formatTime(segment.duration)}</span>
                                                {aiOverrideMode && (
                                                    <button
                                                        className="accept-suggestion-btn"
                                                        onClick={() => {
                                                            // Add AI suggestion to user selections
                                                            const updatedSegments = [...userSelectedSegments, segment];
                                                            setUserSelectedSegments(updatedSegments);
                                                            onSegmentSelectionChange?.(updatedSegments);
                                                        }}
                                                    >
                                                        ✓
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}

                                    {/* Original Segments (faded background) */}
                                    {segmentPositions.map((segment) => (
                                        <div
                                            key={segment.index}
                                            className="segment-marker original"
                                            style={{
                                                left: `${segment.left}%`,
                                                width: `${segment.width}%`,
                                                backgroundColor: `hsl(${(segment.index * 45) % 360}, 70%, 50%)`,
                                                opacity: 0.3
                                            }}
                                            title={`${formatTime(segment.start)} - ${formatTime(segment.end)} (${formatTime(segment.duration)})`}
                                        >
                                            <div className="segment-content">
                                                <span className="segment-time">{formatTime(segment.start)}</span>
                                                <span className="segment-text">{segment.displayText}</span>
                                                <span className="segment-duration">{formatTime(segment.duration)}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Segment Selection Controls */}
                    <div className="segment-controls">
                        <button
                            className={`control-btn ${aiOverrideMode ? 'active' : ''}`}
                            onClick={() => {
                                setAiOverrideMode(!aiOverrideMode);
                                if (aiOverrideMode) {
                                    // When disabling AI override, clear AI suggestions
                                    setAiSuggestedSegments([]);
                                } else {
                                    // When enabling AI override, generate AI suggestions
                                    if (onAiOverride) {
                                        onAiOverride().then(suggestions => {
                                            setAiSuggestedSegments(suggestions || []);
                                        });
                                    }
                                }
                            }}
                        >
                            {aiOverrideMode ? 'Disable AI Override' : 'Enable AI Override'}
                        </button>
                        <button
                            className="control-btn"
                            onClick={handleSegmentVideo}
                            disabled={isProcessing}
                        >
                            Segment Video
                        </button>
                        <button
                            className="control-btn"
                            onClick={() => {
                                // Clear all user selections
                                setUserSelectedSegments([]);
                                onSegmentSelectionChange?.([]);
                            }}
                        >
                            Clear Selections
                        </button>
                    </div>

                    {/* Segment Details List */}
                    <div className="segment-details">
                        <h6>Segment Details</h6>
                        <div className="segment-list">
                            {/* User Selected Segments */}
                            {userSelectedSegmentPositions.slice(0, 10).map((segment) => (
                                <div key={segment.index} className="segment-item user-selected">
                                    <div className="segment-info">
                                        <span className="segment-index">#{segment.index + 1}</span>
                                        <span className="segment-time-range">
                                            {formatTime(segment.start)} - {formatTime(segment.end)}
                                        </span>
                                        <span className="segment-duration-badge">
                                            {formatTime(segment.duration)}
                                        </span>
                                    </div>
                                    <div className="segment-text-preview">
                                        {segment.text ? segment.text.substring(0, 60) + '...' : 'No transcript text available'}
                                    </div>
                                </div>
                            ))}

                            {/* AI Suggested Segments */}
                            {showAiSuggestions && aiOverrideMode && aiSuggestedSegmentPositions.slice(0, 10).map((segment) => (
                                <div key={segment.index} className="segment-item ai-suggested">
                                    <div className="segment-info">
                                        <span className="segment-index">AI #{segment.index + 1}</span>
                                        <span className="segment-time-range">
                                            {formatTime(segment.start)} - {formatTime(segment.end)}
                                        </span>
                                        <span className="segment-duration-badge">
                                            {formatTime(segment.duration)}
                                        </span>
                                    </div>
                                    <div className="segment-text-preview">
                                        {segment.text ? segment.text.substring(0, 60) + '...' : 'No transcript text available'}
                                    </div>
                                </div>
                            ))}

                            {/* Original Segments */}
                            {segmentPositions.slice(0, 10).map((segment) => (
                                <div key={segment.index} className="segment-item original">
                                    <div className="segment-info">
                                        <span className="segment-index">#{segment.index + 1}</span>
                                        <span className="segment-time-range">
                                            {formatTime(segment.start)} - {formatTime(segment.end)}
                                        </span>
                                        <span className="segment-duration-badge">
                                            {formatTime(segment.duration)}
                                        </span>
                                    </div>
                                    <div className="segment-text-preview">
                                        {segment.text ? segment.text.substring(0, 60) + '...' : 'No transcript text available'}
                                    </div>
                                </div>
                            ))}

                            {segmentPositions.length > 10 && (
                                <div className="segment-more">
                                    + {segmentPositions.length - 10} more segments
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            <div className="analysis-results">
                <div className="video-generation glass-card">
                    <h5>Generate Short Video</h5>
                    <div className="generation-info">
                        <p>
                            Processing with selected quality: <strong>{String(quality || 'high').toUpperCase()}</strong>
                        </p>
                        {originalAspectRatio && (
                            <div className="aspect-ratio-info">
                                <span className="aspect-ratio-label">Original Video Aspect Ratio:</span>
                                <span className="aspect-ratio-value">{originalAspectRatio}</span>
                            </div>
                        )}
                    </div>

                    {/* Subtitle Toggle Option */}
                    <div className="subtitle-option">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={addSubtitles}
                                onChange={(e) => setAddSubtitles(e.target.checked)}
                                disabled={isProcessing}
                            />
                            <span className="checkbox-custom"></span>
                            <span className="checkbox-text">Add subtitles to output</span>
                        </label>
                        <p className="subtitle-hint">
                            Burn transcript text directly into the video
                        </p>
                    </div>

                    {/* Platform Selection */}
                    <div className="platform-option">
                        <label className="platform-label">
                            Social Media Platform
                        </label>
                        <select
                            value={selectedPlatform}
                            onChange={(e) => {
                                setSelectedPlatform(e.target.value);
                                // Update aspect ratio based on platform using social_media_formats.py
                                const platformRatios = {
                                    'instagram_reels': '9:16',
                                    'instagram_story': '9:16',
                                    'youtube_shorts': '9:16',
                                    'whatsapp_status': '9:16',
                                    'facebook_story': '9:16',
                                    'facebook_reels': '9:16',
                                    'snapchat_spotlight': '9:16',
                                    'twitter_fleets': '9:16',
                                    'linkedin_stories': '9:16',
                                    'generic_vertical': '9:16',
                                    'generic_square': '1:1',
                                    'custom': '9:16'
                                };
                                setSelectedAspectRatio(platformRatios[e.target.value] || '9:16');
                            }}
                            disabled={isProcessing}
                            className="platform-select"
                        >
                            <option value="instagram_reels">📸 Instagram Reels</option>
                            <option value="youtube_shorts">▶️ YouTube Shorts</option>
                            <option value="instagram_story">📱 Instagram Story</option>
                            <option value="whatsapp_status">💬 WhatsApp Status</option>
                            <option value="facebook_story">📘 Facebook Story</option>
                            <option value="facebook_reels">📘 Facebook Reels</option>
                            <option value="snapchat_spotlight">👻 Snapchat Spotlight</option>
                            <option value="twitter_fleets">🐦 Twitter/X Stories</option>
                            <option value="linkedin_stories">💼 LinkedIn Stories</option>
                            <option value="generic_vertical">📱 Generic Vertical</option>
                            <option value="generic_square">⬜ Generic Square</option>
                            <option value="custom">⚙️ Custom</option>
                        </select>
                    </div>

                    {/* Aspect Ratio Selection */}
                    <div className="aspect-ratio-option">
                        <label className="aspect-ratio-label">
                            Aspect Ratio
                        </label>
                        <select
                            value={selectedAspectRatio}
                            onChange={(e) => setSelectedAspectRatio(e.target.value)}
                            disabled={isProcessing}
                            className="aspect-ratio-select"
                        >
                            <option value="9:16">9:16 (Portrait - Vertical)</option>
                            <option value="1:1">1:1 (Square)</option>
                            <option value="16:9">16:9 (Landscape)</option>
                            <option value="4:3">4:3 (Standard)</option>
                            <option value="21:9">21:9 (Cinematic)</option>
                        </select>
                    </div>

                    {/* Subtitle Language Selection */}
                    {addSubtitles && (
                        <div className="subtitle-language-option">
                            <label className="language-label">
                                Subtitle Language
                            </label>
                            <select
                                value={subtitleLanguage}
                                onChange={(e) => setSubtitleLanguage(e.target.value)}
                                disabled={isProcessing}
                                className="language-select"
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

                    {processingError && (
                        <div className="error-message">
                            <span>Warning</span>
                            <span>{processingError}</span>
                        </div>
                    )}

                    {isProcessing ? (
                        <div className="processing-status">
                            <div className="progress-container">
                                <div className="progress-bar">
                                    <div
                                        className="progress-fill"
                                        style={{ width: `${processingProgress}%` }}
                                    />
                                </div>
                                <span className="progress-text">{processingProgress}%</span>
                            </div>
                            <p className="processing-message">{processingStatus || 'Processing...'}</p>
                        </div>
                    ) : (
                        <button
                            className="generate-button"
                            onClick={handleGenerateVideo}
                        >
                            Generate Short Video
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default NarrativeAnalyzer;