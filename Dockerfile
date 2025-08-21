# Use Python base image with nginx
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js and nginx
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    nginx \
    supervisor \
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

# Copy backend files
WORKDIR /app
COPY backend/ ./backend/
COPY Dhan_Tradehull_V2.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expose port
EXPOSE 8001

# Set environment variables
ENV PYTHONPATH=/app
ENV NODE_ENV=production

# Start the Railway-optimized server
CMD ["python", "backend/railway_server.py"]
