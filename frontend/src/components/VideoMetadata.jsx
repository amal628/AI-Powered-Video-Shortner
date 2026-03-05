import React from 'react';
import './VideoMetadata.css';

const formatDuration = (seconds) => {
    if (!seconds || seconds <= 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const formatDurationDetailed = (seconds) => {
    if (!seconds || seconds <= 0) return '0:00';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
};

const VideoMetadata = ({ 
    title = 'Video Title',
    language = 'English',
    genre = 'Entertainment',
    releaseYear = '2024',
    starring = 'Unknown',
    duration = 0,
    resolution = '1920x1080',
    metadata = null
}) => {
    // Use real metadata if available, otherwise fall back to props
    const displayDuration = metadata?.duration 
        ? formatDurationDetailed(metadata.duration) 
        : formatDurationDetailed(duration);
    
    const displayResolution = metadata?.resolution || resolution;
    const displayCodec = metadata?.codec || 'Unknown';
    const displayFileSize = metadata?.file_size || 'Unknown';
    const displayFps = metadata?.fps || 'Unknown';
    const displayAspectRatio = metadata?.aspect_ratio || 'Unknown';
    const displayAudioCodec = metadata?.audio_codec || 'Unknown';
    const displayWidth = metadata?.width;
    const displayHeight = metadata?.height;
    
    // Language name mapping
    const languageNames = {
        "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu",
        "ml": "Malayalam", "kn": "Kannada", "es": "Spanish", "fr": "French",
        "de": "German", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
        "ar": "Arabic", "pt": "Portuguese", "ru": "Russian", "it": "Italian",
        "unknown": "Unknown"
    };
    
    const displayLanguage = languageNames[language?.toLowerCase()] || language || 'English';
    
    return (
        <div className="video-metadata">
            <div className="metadata-header">
                <h4>Video Information</h4>
            </div>
            <div className="metadata-grid">
                <div className="metadata-item">
                    <span className="metadata-label">Title</span>
                    <span className="metadata-value">{title}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Language</span>
                    <span className="metadata-value">{displayLanguage}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Genre</span>
                    <span className="metadata-value">{genre}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Release Year</span>
                    <span className="metadata-value">{releaseYear}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Starring</span>
                    <span className="metadata-value">{starring}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Duration</span>
                    <span className="metadata-value">{displayDuration}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Resolution</span>
                    <span className="metadata-value">{displayResolution}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Video Codec</span>
                    <span className="metadata-value">{displayCodec}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">File Size</span>
                    <span className="metadata-value">{displayFileSize}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Frame Rate</span>
                    <span className="metadata-value">{displayFps}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Aspect Ratio</span>
                    <span className="metadata-value">{displayAspectRatio}</span>
                </div>
                <div className="metadata-item">
                    <span className="metadata-label">Audio Codec</span>
                    <span className="metadata-value">{displayAudioCodec}</span>
                </div>
            </div>
        </div>
    );
};

export default VideoMetadata;
