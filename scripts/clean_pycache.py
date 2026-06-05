#!/usr/bin/env python3
"""
scripts/clean_pycache.py — Automation script to clean up __pycache__, .pytest_cache, and compiled files.
"""

import shutil
from pathlib import Path

def clean_project():
    root = Path(__file__).resolve().parent.parent
    print(f"Starting cleanup from root: {root}")
    
    clean_targets = ["__pycache__", ".pytest_cache"]
    file_extensions = [".pyc", ".pyo"]
    
    removed_dirs = 0
    removed_files = 0
    
    # We traverse the project directory
    for path in root.glob("**/*"):
        # Skip virtual env directories to avoid slow scans or deleting venv caches
        if ".venv" in path.parts:
            continue
            
        if path.is_dir() and path.name in clean_targets:
            try:
                shutil.rmtree(path)
                print(f"Removed directory: {path.relative_to(root)}")
                removed_dirs += 1
            except Exception as e:
                print(f"Error removing directory {path}: {e}")
                
        elif path.is_file() and path.suffix in file_extensions:
            try:
                path.unlink()
                print(f"Removed file: {path.relative_to(root)}")
                removed_files += 1
            except Exception as e:
                print(f"Error removing file {path}: {e}")
                
    print(f"\nCleanup finished! Removed {removed_dirs} directories and {removed_files} files.")

if __name__ == "__main__":
    clean_project()
