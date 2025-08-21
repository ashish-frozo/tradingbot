#!/usr/bin/env python3
"""
Simple HTTP server that properly serves static files with correct MIME types
"""

import os
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import uvicorn
from production_server import app

class StaticFileHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/app/frontend/dist", **kwargs)
    
    def guess_type(self, path):
        """Override to ensure correct MIME types for JS files"""
        mimetype, encoding = mimetypes.guess_type(path)
        if path.endswith('.js'):
            mimetype = 'application/javascript'
        elif path.endswith('.css'):
            mimetype = 'text/css'
        elif path.endswith('.svg'):
            mimetype = 'image/svg+xml'
        return mimetype, encoding
    
    def do_GET(self):
        # Handle API routes by proxying to FastAPI
        if self.path.startswith('/api/') or self.path == '/health':
            # This is an API route, let FastAPI handle it
            self.send_response(302)
            self.send_header('Location', f'http://localhost:8002{self.path}')
            self.end_headers()
            return
        
        # Serve static files
        super().do_GET()

def run_fastapi():
    """Run FastAPI on port 8002"""
    uvicorn.run(app, host="0.0.0.0", port=8002)

def run_static_server():
    """Run static file server on port 8001"""
    httpd = HTTPServer(('0.0.0.0', 8001), StaticFileHandler)
    httpd.serve_forever()

if __name__ == "__main__":
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # Start static file server on main thread
    print("Starting static file server on port 8001")
    print("FastAPI server running on port 8002")
    run_static_server()
