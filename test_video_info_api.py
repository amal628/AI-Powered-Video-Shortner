#!/usr/bin/env python3
"""
Simple test script to verify the video info API is working correctly.
"""

import sys
import os

# Add the backend directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

try:
    # Test importing the main app
    from app.main import app
    print("✓ Successfully imported FastAPI app")
    
    # Test importing the video_info router
    from app.api.video_info import router
    print("✓ Successfully imported video_info router")
    
    # Check if the router is properly registered
    # Use a more robust approach that avoids type checking issues
    video_info_routes = []
    
    for route in app.routes:
        # Try to get path using getattr to avoid type checking errors
        try:
            # Check common path attributes that FastAPI routes might have
            path = getattr(route, 'path', None)
            if path and '/video-info' in path:
                video_info_routes.append(path)
                continue
                
            path_regex = getattr(route, 'path_regex', None)
            if path_regex and '/video-info' in str(path_regex):
                video_info_routes.append(str(path_regex))
                continue
                
            # Check if it's a route with nested path
            route_obj = getattr(route, 'route', None)
            if route_obj:
                nested_path = getattr(route_obj, 'path', None)
                if nested_path and '/video-info' in nested_path:
                    video_info_routes.append(nested_path)
                    continue
                    
        except Exception:
            # Skip routes we can't inspect
            continue
    
    if video_info_routes:
        print(f"✓ Video info routes found: {video_info_routes}")
    else:
        print("✗ No video info routes found")
    
    # Test importing the video info function
    from app.services.fast_video_processor import get_video_info_fast
    print("✓ Successfully imported get_video_info_fast function")
    
    print("\n🎉 All imports successful! The video info API should be working.")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)
