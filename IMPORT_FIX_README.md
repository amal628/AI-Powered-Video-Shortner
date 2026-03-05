# Import Error Fix for test_video_info_api.py

This document explains how to resolve the import errors in `test_video_info_api.py`.

## Problem

The test file was unable to import modules from the backend app:
- `Import "app.main" could not be resolved`
- `Import "app.api.video_info" could not be resolved` 
- `Import "app.services.fast_video_processor" could not be resolved`

## Solutions

### Option 1: Set PYTHONPATH (Recommended)

Set the PYTHONPATH environment variable to include the current directory:

**Windows (Command Prompt):**
```cmd
set PYTHONPATH=.
python test_video_info_api.py
```

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "."
python test_video_info_api.py
```

**Linux/Mac:**
```bash
export PYTHONPATH=.
python test_video_info_api.py
```

### Option 2: Use the provided batch file

Run the included batch file which sets the PYTHONPATH automatically:
```cmd
run_test.bat
```

### Option 3: VS Code Configuration

The `.vscode/settings.json` file has been configured to resolve Pylance import errors:
- Added `./backend` to `python.analysis.extraPaths`
- Added `./backend` to `python.autoComplete.extraPaths`

## Files Modified

1. **test_video_info_api.py** - Already had proper path setup
2. **.vscode/settings.json** - Added Python path configuration for VS Code
3. **run_test.bat** - Batch file for easy testing on Windows

## Verification

The test should now run successfully and output:
```
✓ Successfully imported FastAPI app
✓ Successfully imported video_info router
✓ Video info routes found: ['/api/video-info/{file_id}', '/api/video-info/{file_id}']
✓ Successfully imported get_video_info_fast function

🎉 All imports successful! The video info API should be working.
```

## Alternative: Relative Imports

If you move the test file inside the app directory (e.g., `app/tests/test_video_info_api.py`), you can use relative imports:

```python
from ..main import app
from ..api.video_info import router
from ..services.fast_video_processor import get_video_info_fast
```

Then run as a module:
```bash
python -m app.tests.test_video_info_api