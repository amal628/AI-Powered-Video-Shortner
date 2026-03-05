import React, { useState, useEffect } from 'react';
import { 
    getSubtitleStatus, 
    generateSubtitles, 
    extractEmbeddedSubtitles, 
    getSubtitleLanguages,
    downloadSubtitle,
    clearSubtitles
} from '../services/api';
import './SubtitleControls.css';

const SubtitleControls = ({ 
    fileId, 
    videoUrl, 
    onSubtitleToggle, 
    onSubtitleChange,
    currentSubtitleUrl,
    isProcessing,
    setIsProcessing
}) => {
    const [subtitleStatus, setSubtitleStatus] = useState(null);
    const [subtitleLanguages, setSubtitleLanguages] = useState(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [showSettings, setShowSettings] = useState(false);
    const [settings, setSettings] = useState({
        maxCharsPerLine: 42,
        includeVtt: true,
        includeWordLevel: false,
        targetLanguages: ['es', 'fr', 'hi']
    });

    useEffect(() => {
        if (fileId) {
            fetchSubtitleStatus();
            fetchSubtitleLanguages();
        }
    }, [fileId]);

    const fetchSubtitleStatus = async () => {
        try {
            const status = await getSubtitleStatus(fileId);
            setSubtitleStatus(status);
        } catch (error) {
            console.error('Error fetching subtitle status:', error);
        }
    };

    const fetchSubtitleLanguages = async () => {
        try {
            const languages = await getSubtitleLanguages(fileId);
            setSubtitleLanguages(languages);
        } catch (error) {
            console.error('Error fetching subtitle languages:', error);
        }
    };

    const handleGenerateSubtitles = async () => {
        if (!fileId) return;

        setIsGenerating(true);
        setIsProcessing(true);

        try {
            const result = await generateSubtitles(fileId, settings);
            console.log('Subtitles generated:', result);
            
            // Refresh status
            await fetchSubtitleStatus();
            await fetchSubtitleLanguages();

            // Auto-enable subtitles if generation was successful
            if (result.srt_path) {
                onSubtitleToggle(true);
                onSubtitleChange(result.srt_path);
            }
        } catch (error) {
            console.error('Error generating subtitles:', error);
        } finally {
            setIsGenerating(false);
            setIsProcessing(false);
        }
    };

    const handleExtractEmbedded = async () => {
        if (!fileId) return;

        setIsGenerating(true);
        setIsProcessing(true);

        try {
            const result = await extractEmbeddedSubtitles(fileId, 'en');
            console.log('Embedded subtitles extracted:', result);
            
            // Refresh status
            await fetchSubtitleStatus();
            await fetchSubtitleLanguages();

            // Auto-enable subtitles if extraction was successful
            if (result.formatted_file) {
                onSubtitleToggle(true);
                onSubtitleChange(result.formatted_file);
            }
        } catch (error) {
            console.error('Error extracting embedded subtitles:', error);
        } finally {
            setIsGenerating(false);
            setIsProcessing(false);
        }
    };

    const handleDownloadSubtitle = async (language = 'en') => {
        try {
            const result = await downloadSubtitle(fileId, language);
            console.log('Subtitle download info:', result);
            
            // Create download link
            const link = document.createElement('a');
            link.href = result.file_path;
            link.download = result.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            console.error('Error downloading subtitle:', error);
        }
    };

    const handleClearSubtitles = async () => {
        try {
            const result = await clearSubtitles(fileId);
            console.log('Subtitles cleared:', result);
            
            // Refresh status
            await fetchSubtitleStatus();
            await fetchSubtitleLanguages();
            
            // Disable subtitles
            onSubtitleToggle(false);
            onSubtitleChange(null);
        } catch (error) {
            console.error('Error clearing subtitles:', error);
        }
    };

    const handleSettingsChange = (key, value) => {
        setSettings(prev => ({
            ...prev,
            [key]: value
        }));
    };

    const toggleSettings = () => {
        setShowSettings(!showSettings);
    };

    if (!fileId) {
        return null;
    }

    return (
        <div className="subtitle-controls">
            <div className="subtitle-header">
                <h4>🎬 Subtitle Controls</h4>
                <button 
                    className="settings-toggle"
                    onClick={toggleSettings}
                    disabled={isGenerating || isProcessing}
                >
                    ⚙️ Settings
                </button>
            </div>

            {/* Settings Panel */}
            {showSettings && (
                <div className="subtitle-settings">
                    <div className="setting-group">
                        <label>Max Characters per Line</label>
                        <input
                            type="number"
                            value={settings.maxCharsPerLine}
                            onChange={(e) => handleSettingsChange('maxCharsPerLine', parseInt(e.target.value))}
                            min="20"
                            max="80"
                            disabled={isGenerating || isProcessing}
                        />
                    </div>
                    
                    <div className="setting-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={settings.includeVtt}
                                onChange={(e) => handleSettingsChange('includeVtt', e.target.checked)}
                                disabled={isGenerating || isProcessing}
                            />
                            Include VTT format
                        </label>
                    </div>
                    
                    <div className="setting-group">
                        <label>
                            <input
                                type="checkbox"
                                checked={settings.includeWordLevel}
                                onChange={(e) => handleSettingsChange('includeWordLevel', e.target.checked)}
                                disabled={isGenerating || isProcessing}
                            />
                            Generate word-level subtitles
                        </label>
                    </div>
                    
                    <div className="setting-group">
                        <label>Target Languages</label>
                        <div className="language-grid">
                            {['es', 'fr', 'de', 'hi', 'ta', 'te', 'ml', 'kn'].map(lang => (
                                <label key={lang} className="language-option">
                                    <input
                                        type="checkbox"
                                        checked={settings.targetLanguages.includes(lang)}
                                        onChange={(e) => {
                                            const newLangs = e.target.checked
                                                ? [...settings.targetLanguages, lang]
                                                : settings.targetLanguages.filter(l => l !== lang);
                                            handleSettingsChange('targetLanguages', newLangs);
                                        }}
                                        disabled={isGenerating || isProcessing}
                                    />
                                    {lang.toUpperCase()}
                                </label>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* Status Information */}
            {subtitleStatus && (
                <div className="subtitle-status">
                    <div className="status-item">
                        <span className="status-label">Embedded Subtitles:</span>
                        <span className={`status-value ${subtitleStatus.has_embedded ? 'available' : 'none'}`}>
                            {subtitleStatus.has_embedded ? 'Available' : 'None'}
                        </span>
                    </div>
                    
                    {subtitleStatus.available_tracks.length > 0 && (
                        <div className="status-item">
                            <span className="status-label">Available Tracks:</span>
                            <div className="track-list">
                                {subtitleStatus.available_tracks.map(track => (
                                    <span key={track.index} className="track-badge">
                                        {track.language.toUpperCase()} ({track.codec})
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    
                    {subtitleStatus.generated_files.length > 0 && (
                        <div className="status-item">
                            <span className="status-label">Generated Files:</span>
                            <div className="file-list">
                                {subtitleStatus.generated_files.map(file => (
                                    <span key={file} className="file-badge">
                                        {file.split('/').pop()}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Actions */}
            <div className="subtitle-actions">
                {/* Generate Subtitles */}
                <div className="action-group">
                    <h5>Generate Subtitles</h5>
                    <div className="action-buttons">
                        <button
                            className="action-button generate-btn"
                            onClick={handleGenerateSubtitles}
                            disabled={isGenerating || isProcessing}
                        >
                            {isGenerating ? 'Generating...' : 'Generate from Audio'}
                        </button>
                        
                        <button
                            className="action-button extract-btn"
                            onClick={handleExtractEmbedded}
                            disabled={isGenerating || isProcessing || !subtitleStatus?.has_embedded}
                        >
                            Extract Embedded
                        </button>
                    </div>
                </div>

                {/* Subtitle Languages */}
                {subtitleLanguages && (
                    <div className="action-group">
                        <h5>Available Subtitles</h5>
                        <div className="language-actions">
                            {subtitleLanguages.embedded_languages.map(lang => (
                                <button
                                    key={lang}
                                    className="language-button"
                                    onClick={() => handleDownloadSubtitle(lang)}
                                >
                                    📥 {lang.toUpperCase()} (Embedded)
                                </button>
                            ))}
                            
                            {subtitleLanguages.generated_languages.map(lang => (
                                <button
                                    key={lang}
                                    className="language-button"
                                    onClick={() => handleDownloadSubtitle(lang)}
                                >
                                    📥 {lang.toUpperCase()} (Generated)
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* Controls */}
                <div className="action-group">
                    <h5>Controls</h5>
                    <div className="control-buttons">
                        <button
                            className="control-button"
                            onClick={() => onSubtitleToggle(!currentSubtitleUrl)}
                            disabled={isGenerating || isProcessing}
                        >
                            {currentSubtitleUrl ? '🔇 Disable Subtitles' : '🔊 Enable Subtitles'}
                        </button>
                        
                        <button
                            className="control-button clear-btn"
                            onClick={handleClearSubtitles}
                            disabled={isGenerating || isProcessing}
                        >
                            🗑️ Clear All
                        </button>
                    </div>
                </div>
            </div>

            {/* Processing Indicator */}
            {(isGenerating || isProcessing) && (
                <div className="processing-indicator">
                    <div className="spinner"></div>
                    <span>Processing subtitles...</span>
                </div>
            )}
        </div>
    );
};

export default SubtitleControls;