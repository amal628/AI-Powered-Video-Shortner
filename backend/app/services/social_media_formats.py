# backend/app/services/social_media_formats.py
"""
Social Media Format Presets for Video Shortening

This module defines format specifications for various social media platforms
to ensure output videos are optimized for each platform's requirements.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import warnings

warnings.filterwarnings("ignore")


class PlatformType(Enum):
    """Supported social media platforms."""
    INSTAGRAM_REELS = "instagram_reels"
    INSTAGRAM_STORY = "instagram_story"
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    WHATSAPP_STATUS = "whatsapp_status"
    FACEBOOK_STORY = "facebook_story"
    FACEBOOK_REELS = "facebook_reels"
    SNAPCHAT_SPOTLIGHT = "snapchat_spotlight"
    TWITTER_FLEETS = "twitter_fleets"
    LINKEDIN_STORIES = "linkedin_stories"
    GENERIC_VERTICAL = "generic_vertical"
    GENERIC_SQUARE = "generic_square"
    CUSTOM = "custom"


@dataclass
class SocialMediaFormat:
    """Format specification for a social media platform."""
    name: str
    display_name: str
    description: str
    aspect_ratio: tuple  # (width, height) ratio
    max_duration: float  # in seconds
    min_duration: float  # in seconds
    recommended_duration: float  # optimal duration
    resolution: tuple  # (width, height) in pixels
    fps: int
    video_bitrate: str
    audio_bitrate: str
    codec: str
    audio_codec: str
    max_file_size_mb: int
    icon: str  # emoji icon for UI
    color: str  # brand color for UI


# Platform-specific format definitions
SOCIAL_MEDIA_FORMATS: Dict[PlatformType, SocialMediaFormat] = {
    PlatformType.INSTAGRAM_REELS: SocialMediaFormat(
        name="instagram_reels",
        display_name="Instagram Reels",
        description="Vertical videos for Instagram Reels feed",
        aspect_ratio=(9, 16),
        max_duration=90.0,
        min_duration=3.0,
        recommended_duration=15.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=100,
        icon="📸",
        color="#E4405F"
    ),
    PlatformType.INSTAGRAM_STORY: SocialMediaFormat(
        name="instagram_story",
        display_name="Instagram Story",
        description="Vertical videos for Instagram Stories",
        aspect_ratio=(9, 16),
        max_duration=60.0,
        min_duration=3.0,
        recommended_duration=15.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=30,
        icon="📱",
        color="#E4405F"
    ),
    PlatformType.TIKTOK: SocialMediaFormat(
        name="tiktok",
        display_name="TikTok",
        description="Vertical videos for TikTok feed",
        aspect_ratio=(9, 16),
        max_duration=180.0,  # Can be up to 10 min, but 3 min recommended
        min_duration=5.0,
        recommended_duration=30.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="5M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=287,
        icon="🎵",
        color="#000000"
    ),
    PlatformType.YOUTUBE_SHORTS: SocialMediaFormat(
        name="youtube_shorts",
        display_name="YouTube Shorts",
        description="Vertical short videos for YouTube",
        aspect_ratio=(9, 16),
        max_duration=60.0,
        min_duration=5.0,
        recommended_duration=30.0,
        resolution=(1080, 1920),
        fps=60,
        video_bitrate="6M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=256,
        icon="▶️",
        color="#FF0000"
    ),
    PlatformType.WHATSAPP_STATUS: SocialMediaFormat(
        name="whatsapp_status",
        display_name="WhatsApp Status",
        description="Videos for WhatsApp Status updates",
        aspect_ratio=(9, 16),
        max_duration=30.0,
        min_duration=3.0,
        recommended_duration=15.0,
        resolution=(720, 1280),
        fps=30,
        video_bitrate="2M",
        audio_bitrate="128k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=16,
        icon="💬",
        color="#25D366"
    ),
    PlatformType.FACEBOOK_STORY: SocialMediaFormat(
        name="facebook_story",
        display_name="Facebook Story",
        description="Vertical videos for Facebook Stories",
        aspect_ratio=(9, 16),
        max_duration=60.0,
        min_duration=3.0,
        recommended_duration=15.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=50,
        icon="📘",
        color="#1877F2"
    ),
    PlatformType.FACEBOOK_REELS: SocialMediaFormat(
        name="facebook_reels",
        display_name="Facebook Reels",
        description="Vertical short videos for Facebook Reels",
        aspect_ratio=(9, 16),
        max_duration=90.0,
        min_duration=3.0,
        recommended_duration=30.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=100,
        icon="📘",
        color="#1877F2"
    ),
    PlatformType.SNAPCHAT_SPOTLIGHT: SocialMediaFormat(
        name="snapchat_spotlight",
        display_name="Snapchat Spotlight",
        description="Vertical videos for Snapchat Spotlight",
        aspect_ratio=(9, 16),
        max_duration=60.0,
        min_duration=5.0,
        recommended_duration=15.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=50,
        icon="👻",
        color="#FFFC00"
    ),
    PlatformType.TWITTER_FLEETS: SocialMediaFormat(
        name="twitter_fleets",
        display_name="Twitter/X Stories",
        description="Vertical videos for Twitter/X",
        aspect_ratio=(9, 16),
        max_duration=140.0,
        min_duration=5.0,
        recommended_duration=30.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=512,
        icon="🐦",
        color="#1DA1F2"
    ),
    PlatformType.LINKEDIN_STORIES: SocialMediaFormat(
        name="linkedin_stories",
        display_name="LinkedIn Stories",
        description="Professional vertical videos for LinkedIn",
        aspect_ratio=(9, 16),
        max_duration=20.0,
        min_duration=3.0,
        recommended_duration=10.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=50,
        icon="💼",
        color="#0A66C2"
    ),
    PlatformType.GENERIC_VERTICAL: SocialMediaFormat(
        name="generic_vertical",
        display_name="Generic Vertical (9:16)",
        description="Universal vertical format for any platform",
        aspect_ratio=(9, 16),
        max_duration=60.0,
        min_duration=5.0,
        recommended_duration=30.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=100,
        icon="📱",
        color="#6B7280"
    ),
    PlatformType.GENERIC_SQUARE: SocialMediaFormat(
        name="generic_square",
        display_name="Generic Square (1:1)",
        description="Square format for feed posts",
        aspect_ratio=(1, 1),
        max_duration=60.0,
        min_duration=5.0,
        recommended_duration=30.0,
        resolution=(1080, 1080),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=100,
        icon="⬜",
        color="#6B7280"
    ),
    PlatformType.CUSTOM: SocialMediaFormat(
        name="custom",
        display_name="Custom",
        description="Custom format with user-defined duration",
        aspect_ratio=(9, 16),
        max_duration=300.0,  # 5 minutes max
        min_duration=5.0,
        recommended_duration=60.0,
        resolution=(1080, 1920),
        fps=30,
        video_bitrate="4M",
        audio_bitrate="192k",
        codec="libx264",
        audio_codec="aac",
        max_file_size_mb=500,
        icon="⚙️",
        color="#8B5CF6"
    ),
}


def get_format(platform: PlatformType) -> SocialMediaFormat:
    """Get format specification for a platform."""
    return SOCIAL_MEDIA_FORMATS.get(platform, SOCIAL_MEDIA_FORMATS[PlatformType.GENERIC_VERTICAL])


def get_all_formats() -> Dict[PlatformType, SocialMediaFormat]:
    """Get all available format specifications."""
    return SOCIAL_MEDIA_FORMATS


def get_popular_formats() -> List[SocialMediaFormat]:
    """Get the most popular platform formats."""
    popular = [
        PlatformType.INSTAGRAM_REELS,
        PlatformType.TIKTOK,
        PlatformType.YOUTUBE_SHORTS,
        PlatformType.INSTAGRAM_STORY,
        PlatformType.WHATSAPP_STATUS,
        PlatformType.FACEBOOK_STORY,
    ]
    return [SOCIAL_MEDIA_FORMATS[p] for p in popular]


def get_format_by_name(name: str) -> Optional[SocialMediaFormat]:
    """Get format specification by platform name."""
    for platform_type, format_spec in SOCIAL_MEDIA_FORMATS.items():
        if format_spec.name == name or platform_type.value == name:
            return format_spec
    return None


def calculate_target_duration(
    video_duration: float,
    platform: PlatformType,
    custom_duration: Optional[float] = None
) -> float:
    """
    Calculate the optimal target duration for a video.
    
    Args:
        video_duration: Original video duration in seconds
        platform: Target platform
        custom_duration: Optional custom duration override
        
    Returns:
        Target duration in seconds
    """
    format_spec = get_format(platform)
    
    if custom_duration:
        # Respect custom duration but clamp to platform limits
        return max(
            format_spec.min_duration,
            min(custom_duration, format_spec.max_duration, video_duration)
        )
    
    # Calculate based on recommended duration
    target = min(format_spec.recommended_duration, video_duration)
    
    # If video is shorter than recommended, use the video duration
    if video_duration < format_spec.recommended_duration:
        target = video_duration
    # If video is much longer, cap at max duration
    elif video_duration > format_spec.max_duration * 2:
        target = format_spec.max_duration
    
    # Ensure within bounds
    target = max(format_spec.min_duration, min(target, format_spec.max_duration))
    
    return target


def get_ffmpeg_scale_filter(
    original_width: int,
    original_height: int,
    target_format: SocialMediaFormat
) -> str:
    """
    Generate FFmpeg scale filter for platform-specific resolution.
    
    Handles cropping and scaling to fit the target aspect ratio.
    """
    target_width, target_height = target_format.resolution
    target_ratio = target_width / target_height
    original_ratio = original_width / original_height
    
    if abs(target_ratio - original_ratio) < 0.01:
        # Same aspect ratio, just scale
        return f"scale={target_width}:{target_height}"
    
    # Need to crop and scale
    if original_ratio > target_ratio:
        # Original is wider - crop sides
        new_width = int(original_height * target_ratio)
        x_offset = (original_width - new_width) // 2
        crop_filter = f"crop={new_width}:{original_height}:{x_offset}:0"
    else:
        # Original is taller - crop top/bottom (or just scale)
        new_height = int(original_width / target_ratio)
        y_offset = (original_height - new_height) // 2
        crop_filter = f"crop={original_width}:{new_height}:0:{y_offset}"
    
    scale_filter = f"scale={target_width}:{target_height}"
    return f"{crop_filter},{scale_filter}"


def get_platform_summary() -> List[Dict]:
    """Get a summary of all platforms for API responses."""
    return [
        {
            "name": fmt.name,
            "display_name": fmt.display_name,
            "description": fmt.description,
            "aspect_ratio": f"{fmt.aspect_ratio[0]}:{fmt.aspect_ratio[1]}",
            "max_duration": fmt.max_duration,
            "min_duration": fmt.min_duration,
            "recommended_duration": fmt.recommended_duration,
            "resolution": f"{fmt.resolution[0]}x{fmt.resolution[1]}",
            "icon": fmt.icon,
            "color": fmt.color
        }
        for fmt in SOCIAL_MEDIA_FORMATS.values()
    ]
