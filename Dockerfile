# Use Python 3.10 slim image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Remove build dependencies
RUN apt-get purge -y --auto-remove gcc build-essential

# Copy application code
COPY . .

# Create temp folder with proper permissions
RUN mkdir -p /app/temp_folder && \
    chmod 777 /app/temp_folder

# Expose Flask port
EXPOSE 5000

# Run the application
CMD ["python", "noor.py"]
