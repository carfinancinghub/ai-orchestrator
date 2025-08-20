"""
Path: app/__init__.py
Package marker.
"""
from __future__ import annotations
from .server import app  # re-export for `uvicorn app:app`
