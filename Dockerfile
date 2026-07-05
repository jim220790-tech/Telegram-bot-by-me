FROM python:3.10-slim-bookworm

# Install system dependencies for yt-dlp and ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY bot.py .

# Create a directory for downloads
RUN mkdir -p downloads

# Expose health check port
EXPOSE 10000

# Command to run the bot
CMD ["python", "bot.py"]
