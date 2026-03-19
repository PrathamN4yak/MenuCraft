"""
MenuCraft — Vercel Entry Point
Vercel looks for a WSGI-compatible app in api/index.py
"""
import sys
import os

# Make sure backend/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app

# Create the Flask app — sets up DB tables + seeds initial data
app = create_app()

# Vercel needs the WSGI handler to be named 'app'
# (It calls app(environ, start_response) directly)
handler = app