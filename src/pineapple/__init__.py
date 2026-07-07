"""
pineapple — Smart framework detection, Dockerfile generation & container builds.

Scans any project directory, detects the framework and language,
and generates a production-ready Dockerfile — zero dependencies,
pure Python stdlib.

Usage:
    pineapple /path/to/project
    pineapple generate /path/to/project --output Dockerfile
    pineapple generate /path/to/project --build
    pineapple verify docker
    pineapple --version
"""

__version__ = "1.0.0"
