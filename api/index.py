import sys
import os

# Add project root to Python path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app import create_app

# Vercel Python runtime looks for a variable named 'app' (WSGI)
app = create_app()