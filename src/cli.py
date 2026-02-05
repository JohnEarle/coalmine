#!/usr/bin/env python
"""
Coalmine CLI - Backward compatibility wrapper.

This file is kept for backward compatibility. The actual CLI implementation
has been refactored into the src.cli package with modular command handlers.

Usage remains unchanged:
    python src/cli.py <command> [args...]
"""
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import run

if __name__ == "__main__":
    run()
