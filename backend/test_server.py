#!/usr/bin/env python3
"""
Minimal test server to debug Railway deployment issues
"""

from fastapi import FastAPI
import uvicorn
import os

app = FastAPI(title="Test Server", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "Test server is working!", "status": "ok"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "message": "Minimal test server"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting test server on port {port}")
    uvicorn.run("test_server:app", host="0.0.0.0", port=port, reload=False)
