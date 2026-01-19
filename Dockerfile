FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Node.js LTS
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js from NodeSource (LTS version)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    which node && \
    node --version

# Create a non-root user for running the application
RUN useradd -m -u 1000 appuser

# Copy requirements and install Python packages as root (before user switch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Ensure proper ownership of /app for appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user for runtime
USER appuser

# Default command (overridden by docker-compose)
CMD ["bash"]
