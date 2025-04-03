#!/usr/bin/env python
"""
Setup script for git commit template.
This script sets up the git commit template for the repository.
"""

import os
import subprocess
import sys


def main():
    """Set up the git commit template."""
    print("Setting up git commit template...")
    
    # Get the absolute path to the .gitmessage file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, ".gitmessage")
    
    # Set the commit template
    subprocess.run(["git", "config", "--local", "commit.template", template_path], check=True)
    
    print("Git commit template setup complete!")
    print("Your commit messages will now use the template in .gitmessage")


if __name__ == "__main__":
    main()
