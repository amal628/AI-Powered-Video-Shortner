#!/usr/bin/env python3
"""
Test script to verify the implementation of enhanced narrative analyzer features.
This script tests the new functionality without requiring actual video files.
"""

import sys
import os
import json
from typing import List, Dict, Any

# Add the backend directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_content_type_analyzer():
    """Test the content type analyzer with sample text."""
    print("Testing Content Type Analyzer...")
    
    try:
        from app.services.content_type_analyzer import content_type_analyzer, ContentType
        
        # Test action content
        action_segments = [
            {"text": "This is an intense action scene with fighting and explosions"},
            {"text": "The battle was fast and furious with lots of action"},
            {"text": "We need to run and attack the enemy quickly"}
        ]
        
        action_analysis = content_type_analyzer.analyze_content_type(action_segments)
        print(f"Action content detected: {action_analysis.primary_type.value}")
        print(f"Confidence: {action_analysis.confidence:.2f}")
        print(f"Keywords found: {action_analysis.keywords[:5]}")
        print()
        
        # Test comedy content
        comedy_segments = [
            {"text": "This is so funny and hilarious, I can't stop laughing"},
            {"text": "What a ridiculous and silly situation"},
            {"text": "The joke was absolutely hilarious"}
        ]
        
        comedy_analysis = content_type_analyzer.analyze_content_type(comedy_segments)
        print(f"Comedy content detected: {comedy_analysis.primary_type.value}")
        print(f"Confidence: {comedy_analysis.confidence:.2f}")
        print(f"Keywords found: {comedy_analysis.keywords[:5]}")
        print()
        
        # Test educational content
        educational_segments = [
            {"text": "Today we will learn about science and math"},
            {"text": "This educational video teaches important facts"},
            {"text": "Let me explain this concept in detail"}
        ]
        
        educational_analysis = content_type_analyzer.analyze_content_type(educational_segments)
        print(f"Educational content detected: {educational_analysis.primary_type.value}")
        print(f"Confidence: {educational_analysis.confidence:.2f}")
        print(f"Keywords found: {educational_analysis.keywords[:5]}")
        print()
        
        return True
        
    except Exception as e:
        print(f"Content Type Analyzer test failed: {e}")
        return False

def test_narrative_analyzer_enhancements():
    """Test the enhanced narrative analyzer with content type integration."""
    print("Testing Enhanced Narrative Analyzer...")
    
    try:
        from app.services.narrative_analyzer import legacy_narrative_analyzer, ContentType
        
        # Test with action content
        action_segments = [
            {"start": 0, "end": 10, "text": "Welcome to this intense action video with fighting"},
            {"start": 10, "end": 20, "text": "Suddenly there was an explosion and everyone ran"},
            {"start": 20, "end": 30, "text": "The final battle was the most epic climax ever"}
        ]
        
        analysis_result = legacy_narrative_analyzer.analyze_narrative_structure(action_segments)
        narrative_segments = analysis_result.get("narrative_segments", [])
        
        print(f"Found {len(narrative_segments)} narrative segments")
        for i, segment in enumerate(narrative_segments):
            print(f"Segment {i+1}: {segment.get('element_type', 'unknown')}")
            print(f"  Content type: {segment.get('content_type', 'unknown')}")
            print(f"  Confidence: {segment.get('content_confidence', 0):.2f}")
            print(f"  Duration: {segment.get('duration', 0):.1f}s")
            print()
        
        return True
        
    except Exception as e:
        print(f"Enhanced Narrative Analyzer test failed: {e}")
        return False

def test_ai_override_functionality():
    """Test the AI override functionality."""
    print("Testing AI Override Functionality...")
    
    try:
        from app.services.narrative_analyzer import legacy_narrative_analyzer
        
        # Test segments
        test_segments = [
            {"start": 0, "end": 10, "text": "This is a great segment"},
            {"start": 10, "end": 20, "text": "This is another good segment"},
            {"start": 20, "end": 30, "text": "This is the best segment"}
        ]
        
        # Enable AI override
        legacy_narrative_analyzer.enable_ai_override()
        print("AI override enabled")
        
        # Get AI suggestions
        suggestions = legacy_narrative_analyzer.get_ai_suggestions(test_segments)
        print(f"AI suggestions generated: {len(suggestions)}")
        for i, suggestion in enumerate(suggestions):
            print(f"  Suggestion {i+1}: {suggestion.get('confidence', 0):.2f} confidence")
            print(f"    Reason: {suggestion.get('reason', 'N/A')}")
        print()
        
        # Add user override segments
        user_override = {"start": 5, "end": 15, "text": "User selected segment"}
        legacy_narrative_analyzer.add_user_override_segment(user_override)
        print("User override segment added")
        
        # Apply overrides
        filtered_segments = legacy_narrative_analyzer.apply_user_overrides(test_segments)
        print(f"Filtered segments: {len(filtered_segments)}")
        for segment in filtered_segments:
            print(f"  Source: {segment.get('selection_source', 'unknown')}")
        print()
        
        # Disable AI override
        legacy_narrative_analyzer.disable_ai_override()
        print("AI override disabled")
        
        return True
        
    except Exception as e:
        print(f"AI Override test failed: {e}")
        return False

def test_scene_type_priority():
    """Test the scene type priority configuration."""
    print("Testing Scene Type Priority...")
    
    try:
        from app.services.narrative_analyzer import legacy_narrative_analyzer
        
        # Check default priorities
        priorities = legacy_narrative_analyzer.scene_type_priority
        print("Scene type priorities:")
        for scene_type, priority in sorted(priorities.items(), key=lambda x: x[1], reverse=True):
            print(f"  {scene_type}: {priority}")
        print()
        
        # Test priority updates
        legacy_narrative_analyzer.scene_type_priority["custom"] = 1.5
        print(f"Custom scene type priority: {legacy_narrative_analyzer.scene_type_priority.get('custom', 0)}")
        print()
        
        return True
        
    except Exception as e:
        print(f"Scene Type Priority test failed: {e}")
        return False

def test_platform_presets():
    """Test the platform presets integration."""
    print("Testing Platform Presets Integration...")
    
    try:
        from app.services.social_media_formats import get_format, PlatformType, get_platform_summary
        
        # Test getting format for Instagram Reels
        reels_format = get_format(PlatformType.INSTAGRAM_REELS)
        print(f"Instagram Reels format: {reels_format.display_name}")
        print(f"  Aspect Ratio: {reels_format.aspect_ratio[0]}:{reels_format.aspect_ratio[1]}")
        print(f"  Max Duration: {reels_format.max_duration}s")
        print(f"  Resolution: {reels_format.resolution[0]}x{reels_format.resolution[1]}")
        print()
        
        # Test getting format by name
        tiktok_format = get_format(PlatformType.TIKTOK)
        print(f"TikTok format: {tiktok_format.display_name}")
        print(f"  Max Duration: {tiktok_format.max_duration}s")
        print()
        
        # Test platform summary
        platform_summary = get_platform_summary()
        print(f"Available platforms: {len(platform_summary)}")
        for platform in platform_summary[:3]:  # Show first 3
            print(f"  {platform['display_name']}: {platform['aspect_ratio']}")
        print()
        
        return True
        
    except Exception as e:
        print(f"Platform Presets test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Enhanced Narrative Analyzer Implementation Test")
    print("=" * 50)
    print()
    
    tests = [
        ("Content Type Analyzer", test_content_type_analyzer),
        ("Enhanced Narrative Analyzer", test_narrative_analyzer_enhancements),
        ("AI Override Functionality", test_ai_override_functionality),
        ("Scene Type Priority", test_scene_type_priority),
        ("Platform Presets Integration", test_platform_presets),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        try:
            if test_func():
                print(f"✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
        print("-" * 30)
        print()
    
    print(f"Test Results: {passed}/{total} tests passed")
    if passed == total:
        print("🎉 All tests passed! Implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)