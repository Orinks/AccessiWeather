#!/usr/bin/env python3
"""
Script to automatically fix common Flake8 whitespace and formatting issues.
"""

import os
import re


def fix_whitespace_issues(directory="."):
    """
    Fix common whitespace and formatting issues in Python files.

    This addresses:
    - W293: Blank line contains whitespace
    - W291: Trailing whitespace on non-blank lines
    - W292: No newline at end of file
    - E302/E305: Incorrect number of blank lines between functions/classes

    Args:
        directory: Directory to process (recursively)
    """
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Store original content to check if changes were made
                original_content = content

                # Fix W293: Blank line contains whitespace
                content = re.sub(r"^\s+$", "", content, flags=re.MULTILINE)

                # Fix W291: Trailing whitespace on non-blank lines
                content = re.sub(r"[ \t]+$", "", content, flags=re.MULTILINE)

                # Fix W292: No newline at end of file
                if not content.endswith("\n"):
                    content += "\n"

                # Fix E302/E305: Function/class spacing
                # This is a simplistic approach and might need manual review

                # Add two blank lines before function/class definitions
                content = re.sub(
                    r"(\n[^\n]+)\n([^\n]*def |[^\n]*class )",
                    r"\1\n\n\n\2",
                    content,
                )

                # Remove extra blank lines (more than 2 consecutive)
                content = re.sub(r"\n\n\n\n+", r"\n\n\n", content)

                if content != original_content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"Fixed formatting in {filepath}")


if __name__ == "__main__":
    fix_whitespace_issues("src")
    fix_whitespace_issues("tests")
    # Also fix this script itself
    fix_whitespace_issues(".")
    print("Formatting fixes complete!")
