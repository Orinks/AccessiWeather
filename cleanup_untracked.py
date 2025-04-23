#!/usr/bin/env python
"""
Cleanup script to remove untracked files from the AccessiWeather project.
"""

import os
import shutil

# Files to be removed
files_to_remove = [
    "build_with_existing_spec.ps1",
    "clean_pycache.py",
    "collected_modules.txt",
    "docs/testing_threading.md",
    "installer/build_installer_fixed.ps1",
    "installer/build_installer_updated.ps1",
    "run_exit_handler_tests.py",
    "run_exit_manual_test.py",
    "test_files.txt",
]

def cleanup_files():
    """Remove the untracked files from the project."""
    # Get the project root directory (where this script is located)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Starting cleanup of untracked files...\n")
    
    for file_path in files_to_remove:
        full_path = os.path.join(root_dir, file_path)
        
        if os.path.exists(full_path):
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                    print(f"Removed directory: {file_path}")
                else:
                    os.remove(full_path)
                    print(f"Removed file: {file_path}")
            except Exception as e:
                print(f"Error removing {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")
    
    print("\nCleanup complete!")
    print("\nTo verify, run: git status")

if __name__ == "__main__":
    # Ask for confirmation before proceeding
    confirm = input("This will remove all listed untracked files. Continue? (y/n): ")
    if confirm.lower() == 'y':
        cleanup_files()
    else:
        print("Cleanup cancelled.")
