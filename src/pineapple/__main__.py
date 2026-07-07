"""
CLI entry point for ``python -m pineapple /path/to/project``.
"""

import sys
from pineapple.cli import main

if __name__ == "__main__":
    sys.exit(main())
