# Use Python base image for simpler deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install frontend dependencies
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Switch back to app directory
WORKDIR /app

# Copy backend requirements and install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/
COPY Dhan_Tradehull_V2.py ./

# Expose port
EXPOSE 8001

# Set environment variables
ENV PYTHONPATH=/app
ENV NODE_ENV=production

# Start the FastAPI server
CMD ["python", "backend/production_server.py"]
