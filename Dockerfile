# Use Python 3.9 as the base image, aligning with MeloTTS's development environment
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables for Python to prevent .pyc files and for unbuffered logs
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Accept the Hugging Face token as a build argument
ARG HF_TOKEN_ARG
# Set it as an environment variable that Hugging Face libraries will automatically use
ENV HF_TOKEN=${HF_TOKEN_ARG}

# Define a consistent path for NLTK data and ensure NLTK uses it
ENV NLTK_DATA /app/nltk_data

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the local requirements file (for functions-framework, gcs-client, etc.)
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install huggingface_hub

# --- NLTK Version and Data Fix ---
# 1. Explicitly install a specific NLTK version (e.g., 3.7) that is more likely
#    to correctly use the pickle-based 'averaged_perceptron_tagger' data.
RUN echo "--- [FIX] Pinning NLTK version to 3.7 ---"
RUN pip install --upgrade nltk==3.7

# 2. Clone and install MeloTTS. This will use the already-installed NLTK 3.7.
# Using a non-editable install and removing the source is cleaner for the final image.
RUN git clone https://github.com/myshell-ai/MeloTTS.git \
    && cd MeloTTS \
    && pip install --no-cache-dir . \
    && python -m unidic download \
    && cd .. \
    && rm -rf MeloTTS

# 3. Download the NLTK data packages. The installed NLTK 3.7 will now use this data.
RUN echo "--- [FIX] Downloading NLTK data for NLTK v3.7 ---"
RUN python -m nltk.downloader -d $NLTK_DATA averaged_perceptron_tagger punkt
# --- End of NLTK Fix ---

# Copy the model preloading script
COPY preload_models.py .

# Run the model preloading script, which will use the HF_TOKEN if set
ARG SUPPORTED_LANGUAGES_BUILD="EN"
ENV SUPPORTED_LANGUAGES_BUILD=${SUPPORTED_LANGUAGES_BUILD}
ENV PRELOAD_DEVICE="cpu"
RUN python preload_models.py

# Copy the main application code
COPY main.py .

# Set the entrypoint for Functions Framework
CMD exec functions-framework --target=melo_tts_gcs_trigger --port=8080