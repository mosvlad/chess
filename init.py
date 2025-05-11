#!/usr/bin/env python3
"""
Initialize directory structure for Chess Online
"""

import os
import sys


def create_directories():
    """Create necessary directories for the application"""
    directories = [
        "templates",
        "static",
        "static/css",
        "static/js",
        "static/images"
    ]

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
        else:
            print(f"Directory already exists: {directory}")


def main():
    print("Chess Online - Directory Initialization")
    print("=" * 35)

    create_directories()

    print("\nDirectory structure created successfully!")
    print("\nNext steps:")
    print("1. Place your template files in the 'templates' directory")
    print("2. Place your static files (CSS, JS, images) in the 'static' directory")
    print("3. Run the application with: python main.py")


if __name__ == "__main__":
    main()