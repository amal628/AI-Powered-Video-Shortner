// frontend/src/components/ShareButton.jsx
import { useState } from 'react';
import { getShareUrl } from '../services/api';
import './ShareButton.css';

const ShareButton = ({ filename, videoUrl }) => {
    const [loading, setLoading] = useState(false);

    const handleShare = async () => {
        // Need either filename or videoUrl to share
        if (!filename && !videoUrl) {
            console.warn('ShareButton: No filename or videoUrl provided');
            return;
        }

        setLoading(true);
        try {
            let shareUrl = null;

            // Prefer filename-based sharing (uses backend API for full URL)
            if (filename && typeof filename === 'string' && filename.trim()) {
                try {
                    console.log('Attempting to get share URL from backend for:', filename);
                    const data = await getShareUrl(filename);
                    shareUrl = data.share_url;
                } catch (err) {
                    console.warn('Backend share failed, falling back to direct URL:', err);
                    // Fallback: construct direct URL
                    const encodedFilename = encodeURIComponent(filename);
                    shareUrl = `${window.location.origin}/api/download/${encodedFilename}`;
                }
            } else if (videoUrl && typeof videoUrl === 'string') {
                // For trimmed videos or when no filename available
                console.log('Using videoUrl for sharing:', videoUrl);
                if (videoUrl.startsWith('/')) {
                    shareUrl = `${window.location.origin}${videoUrl}`;
                } else if (videoUrl.startsWith('http')) {
                    shareUrl = videoUrl;
                } else {
                    shareUrl = `${window.location.origin}/${videoUrl}`;
                }
            }

            if (!shareUrl) {
                throw new Error('Could not generate share URL');
            }

            console.log('Final share URL:', shareUrl);

            if (navigator.share) {
                await navigator.share({
                    title: 'Shortened Video',
                    text: 'Check out this amazing shortened video!',
                    url: shareUrl,
                });
                console.log('Share successful');
            } else {
                await navigator.clipboard.writeText(shareUrl);
                alert('Link copied to clipboard!');
            }
        } catch (err) {
            console.error('Share failed:', err);
            alert('Unable to share link. Please try again.' + (err.message ? ` [${err.message}]` : ''));
        } finally {
            setLoading(false);
        }
    };

    const isDisabled = loading || (!filename && !videoUrl);

    return (
        <button
            className="share-button"
            onClick={handleShare}
            disabled={isDisabled}
            title={isDisabled ? 'Process a video first' : 'Share this video'}
        >
            {loading ? 'Sharing...' : 'Share'}
        </button>
    );
};

export default ShareButton;
