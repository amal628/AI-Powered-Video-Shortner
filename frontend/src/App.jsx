import { useCallback, useState } from 'react';
import './App.css';
import DownloadButton from './components/DownloadButton';
import NarrativeAnalyzer from './components/NarrativeAnalyzer';
import ShareButton from './components/ShareButton';
import VideoPreview from './components/VideoPreview';
import VideoUpload from './components/VideoUpload';
import VideoMetadata from './components/VideoMetadata';

const WORKFLOW_STEPS = [
    {
        id: 'upload',
        title: 'Upload',
        description: 'Bring in your source clip and basic output settings.'
    },
    {
        id: 'analyze',
        title: 'Process',
        description: 'Generate a short video directly from selected duration and quality.'
    },
    {
        id: 'preview',
        title: 'Preview',
        description: 'Review, download, and share the generated short.'
    }
];

const formatDuration = (seconds) => {
    const safeSeconds = Number(seconds);
    if (!Number.isFinite(safeSeconds) || safeSeconds <= 0) {
        return '--';
    }

    if (safeSeconds < 60) {
        return `${Math.round(safeSeconds)}s`;
    }

    const mins = Math.floor(safeSeconds / 60);
    const secs = Math.round(safeSeconds % 60)
        .toString()
        .padStart(2, '0');
    return `${mins}:${secs}`;
};

function App() {
    const [uploadedVideo, setUploadedVideo] = useState(null);
    const [transcriptionResult, setTranscriptionResult] = useState(null);
    const [processedVideo, setProcessedVideo] = useState(null);
    const [currentStep, setCurrentStep] = useState('upload'); // upload, analyze, preview
    const [error, setError] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [showWorkflow, setShowWorkflow] = useState(false);

    const handleVideoUpload = useCallback((videoData) => {
        setUploadedVideo(videoData);
        setCurrentStep('analyze');
        setError(null);
    }, []);

    const handleTranscriptionComplete = useCallback((result) => {
        setTranscriptionResult(result);
    }, []);

    const handleVideoProcessingComplete = useCallback((processedVideoData) => {
        const normalized =
            typeof processedVideoData === 'string'
                ? { url: processedVideoData }
                : (processedVideoData || {});

        const resolvedUrl = normalized.url || normalized.videoUrl || '';
        if (!resolvedUrl) {
            setError('Processed video URL is missing from pipeline response.');
            return;
        }

        setProcessedVideo({
            ...normalized,
            url: resolvedUrl,
            timestamp: Date.now()
        });
        setCurrentStep('preview');
    }, []);

    const handleError = useCallback((errorMessage) => {
        setError(errorMessage);
        setIsProcessing(false);
    }, []);

    const handleRetry = useCallback(() => {
        setError(null);
        setUploadedVideo(null);
        setTranscriptionResult(null);
        setProcessedVideo(null);
        setCurrentStep('upload');
        setIsProcessing(false);
    }, []);

    const handleStartOver = useCallback(() => {
        if (window.confirm('Are you sure you want to start over? This will clear all current progress.')) {
            handleRetry();
        }
    }, [handleRetry]);

    const getStepTitle = () => {
        switch (currentStep) {
            case 'upload':
                return 'Upload Source Video';
            case 'analyze':
                return 'Process Short Video';
            case 'preview':
                return 'Preview Final Short';
            default:
                return 'Video Shortener';
        }
    };

    const getStepDescription = () => {
        switch (currentStep) {
            case 'upload':
                return 'Upload a video file and configure the short output target.';
            case 'analyze':
                return 'Process the uploaded video into a short output using your selected duration and quality.';
            case 'preview':
                return 'Your generated short is ready for final review and distribution.';
            default:
                return 'Transform long videos into short clips with AI-assisted processing.';
        }
    };

    const currentStepIndex = WORKFLOW_STEPS.findIndex((step) => step.id === currentStep);
    const selectedSegmentsCount = transcriptionResult?.segments?.length ?? 0;
    const analyzedWords = transcriptionResult?.wordCount ?? 0;
    const configuredTargetDuration =
        processedVideo?.targetDuration
        ?? uploadedVideo?.target_duration;

    return (
        <div className="app">
            <header className="app-header">
                <div className="container">
                    <div className="header-content">
                        <div className="brand-block">
                            <span className="brand-tag">AI EDIT LAB</span>
                            <h1 className="text-gradient">AI Powered Video Shortner</h1>
                            <p>Turn long videos into short clips with fast, reliable AI processing.</p>
                        </div>
                        <div className="header-actions">
                            <div className="status-chip">
                                <span className="chip-label">Current Stage</span>
                                <strong>{getStepTitle()}</strong>
                            </div>
                            {currentStep !== 'upload' && (
                                <button
                                    className="retry-button"
                                    onClick={handleStartOver}
                                    disabled={isProcessing}
                                >
                                    Start Over
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </header>

            <main className="app-main">
                <div className="container">
                    {error && (
                        <div className="error-section fade-in">
                            <div className="error-card">
                                <div className="error-icon">!</div>
                                <div className="error-content">
                                    <h3>Something went wrong</h3>
                                    <p>{error}</p>
                                    <button className="retry-button" onClick={handleRetry}>
                                        Try Again
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    <section className="hero-panel fade-in">
                        <div className="hero-copy">
                            <h2>{getStepTitle()}</h2>
                            <p>{getStepDescription()}</p>
                        </div>
                        <div className="hero-metrics">
                            <div className="metric-card">
                                <span className="metric-title">Source Duration</span>
                                <strong>{formatDuration(uploadedVideo?.duration)}</strong>
                            </div>
                            <div className="metric-card">
                                <span className="metric-title">Selected Segments</span>
                                <strong>{selectedSegmentsCount || '--'}</strong>
                            </div>
                            <div className="metric-card">
                                <span className="metric-title">Target Duration</span>
                                <strong>{formatDuration(configuredTargetDuration)}</strong>
                            </div>
                            <div className="metric-card">
                                <span className="metric-title">Transcript Words</span>
                                <strong>{analyzedWords || '--'}</strong>
                            </div>
                        </div>
                    </section>

                    <section className="workspace-grid">
                        <aside className={`workflow-rail glass-card fade-in ${showWorkflow ? 'visible' : 'hidden'}`}>
                            <div className="workflow-header">
                                <h3>Workflow</h3>
                                <button 
                                    className="workflow-toggle"
                                    onClick={() => setShowWorkflow(!showWorkflow)}
                                    title="Toggle Workflow"
                                >
                                    {showWorkflow ? '✕' : '📋'}
                                </button>
                            </div>
                            <ol className="stepper">
                                {WORKFLOW_STEPS.map((step, index) => {
                                    const state =
                                        index < currentStepIndex
                                            ? 'done'
                                            : index === currentStepIndex
                                                ? 'active'
                                                : 'upcoming';
                                    return (
                                        <li key={step.id} className={`stepper-item ${state}`}>
                                            <div className="step-badge">{index + 1}</div>
                                            <div className="step-copy">
                                                <h4>{step.title}</h4>
                                                <p>{step.description}</p>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ol>
                        </aside>

                        <section className="workspace-stage fade-in">
                            {currentStep === 'upload' && (
                                <div className="stage-card upload-section">
                                    <VideoUpload
                                        onVideoUpload={handleVideoUpload}
                                        onTranscriptionComplete={handleTranscriptionComplete}
                                        onError={handleError}
                                        isProcessing={isProcessing}
                                        setIsProcessing={setIsProcessing}
                                    />
                                </div>
                            )}

                            {currentStep === 'analyze' && uploadedVideo && (
                                <div className="analysis-section">
                                    <div className="results-grid-wide">
                                        <article className="result-card-wide">
                                            <h4>Source Video</h4>
                                            <VideoPreview
                                                videoUrl={uploadedVideo.url}
                                                transcript={transcriptionResult?.transcript}
                                                title="Original Video"
                                                showMetadata={true}
                                                metadata={{
                                                    title: uploadedVideo.title || 'Video Title',
                                                    language: transcriptionResult?.language || 'English',
                                                    genre: uploadedVideo.genre || 'Entertainment',
                                                    releaseYear: uploadedVideo.releaseYear || '2024',
                                                    starring: uploadedVideo.starring || 'Unknown',
                                                    duration: uploadedVideo?.metadata?.duration || uploadedVideo?.duration,
                                                    resolution: uploadedVideo?.metadata?.resolution,
                                                    codec: uploadedVideo?.metadata?.codec,
                                                    file_size: uploadedVideo?.metadata?.file_size,
                                                    width: uploadedVideo?.metadata?.width,
                                                    height: uploadedVideo?.metadata?.height,
                                                    fps: uploadedVideo?.metadata?.fps,
                                                    aspect_ratio: uploadedVideo?.metadata?.aspect_ratio,
                                                    audio_codec: uploadedVideo?.metadata?.audio_codec,
                                                    file_size_bytes: uploadedVideo?.metadata?.file_size_bytes
                                                }}
                                            />
                                        </article>

                                        <article className="result-card-wide">
                                            <NarrativeAnalyzer
                                                segments={transcriptionResult?.segments}
                                                videoUrl={uploadedVideo.url}
                                                fileId={uploadedVideo.file_id || uploadedVideo.fileId}
                                                targetDuration={uploadedVideo.target_duration}
                                                quality={uploadedVideo.quality}
                                                onVideoProcessingComplete={handleVideoProcessingComplete}
                                                isProcessing={isProcessing}
                                                setIsProcessing={setIsProcessing}
                                                originalAspectRatio={uploadedVideo.aspectRatio || '16:9'}
                                            />
                                        </article>
                                    </div>
                                </div>
                            )}

                            {currentStep === 'preview' && processedVideo && (
                                <div className="results-section">
                                    <div className="success-banner">
                                        <div className="success-icon">OK</div>
                                        <div className="success-content">
                                            <h3>Your short video is ready</h3>
                                            <p>
                                                The AI pipeline completed successfully.
                                                <span className="duration-info">
                                                    {configuredTargetDuration
                                                        ? ` (Target: ${Math.round(configuredTargetDuration)}s)`
                                                        : ' Processing complete'}
                                                </span>
                                            </p>
                                        </div>
                                    </div>

                                    <div className="results-grid-wide">
                                        <article className="result-card-wide">
                                            <h4>Source Video</h4>
                                            <VideoPreview
                                                videoUrl={uploadedVideo.url}
                                                transcript={transcriptionResult?.transcript}
                                                title="Original Video"
                                            />
                                        </article>

                                        <article className="result-card-wide">
                                            <h4>Generated Short</h4>
                                            <VideoPreview
                                                videoUrl={processedVideo.url}
                                                title="Short Video"
                                                showSubtitles={processedVideo.hasSubtitles || false}
                                                aspectRatio={processedVideo.aspectRatio || 'auto'}
                                            />
                                        </article>
                                    </div>

                                    <div className="action-buttons">
                                        <DownloadButton
                                            videoUrl={processedVideo.url}
                                            fileName={processedVideo.filename || 'shortened_video.mp4'}
                                        />
                                        <ShareButton
                                            filename={processedVideo.filename}
                                            videoUrl={processedVideo.url}
                                        />
                                    </div>
                                </div>
                            )}
                        </section>
                    </section>

                    {isProcessing && (
                        <aside className="loading-section fade-in">
                            <div className="loading-spinner"></div>
                            <div className="loading-text">
                                <p>Running AI processing pipeline...</p>
                                <p className="text-muted">This can take a short while for longer videos.</p>
                            </div>
                        </aside>
                    )}
                </div>
            </main>

            <footer className="app-footer">
                <div className="container">
                    <div className="footer-content">
                        <p>AI Powered Video Shortner | AI-assisted short video processing pipeline</p>
                    </div>
                </div>
            </footer>
        </div>
    );
}

export default App;
