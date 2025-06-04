# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables for Python to prevent it from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Set Python to run in unbuffered mode, which is recommended for Docker logs
ENV PYTHONUNBUFFERED 1

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main application code (main.py)
COPY main.py .

# Set the entrypoint for Functions Framework
# The FUNCTION_TARGET environment variable will be set by Cloud Run to copy_txt_file_gcs
# Default port for Cloud Run is 8080
CMD exec functions-framework --target=copy_txt_file_gcs --port=8080