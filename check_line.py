#!/usr/bin/env python3
import os

# Change to the correct directory
os.chdir('backend/app/services')

# Read the file and check line 694
with open('narrative_analyzer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Line 694 is index 693 (0-based)
if len(lines) > 693:
    print(f"Line 694: {lines[693].strip()}")
else:
    print(f"File only has {len(lines)} lines")