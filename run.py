#!/usr/bin/env python3
"""Entry point — run the LinkUp Flask development server on port 5001."""
import os
from dotenv import load_dotenv

load_dotenv()

# Default to 5001 for LinkUp
os.environ.setdefault('SERVER_PORT', '5001')

from backend.app import app, socketio

if __name__ == '__main__':
    port = int(os.environ.get('SERVER_PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
