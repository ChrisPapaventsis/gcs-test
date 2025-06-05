# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables for Python to prevent it from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Set Python to run in unbuffered mode, which is recommended for Docker logs
ENV PYTHONUNBUFFERED 1

# Accept the Hugging Face token as a build argument
ARG HF_TOKEN_ARG
# Set it as an environment variable that Hugging Face libraries will use
ENV HF_TOKEN=${HF_TOKEN_ARG}

# Define the NLTK data path and ensure NLTK uses it
ENV NLTK_DATA /app/nltk_data

# Install system dependencies: git for cloning, build-essential for some Python packages, libsndfile1 for audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install huggingface_hub to ensure CLI tools are available if needed,
# and for libraries to robustly pick up the token.
# Usually a dependency of transformers, but doesn't hurt to ensure.
RUN pip install huggingface_hub

# Clone MeloTTS repository and install it along with its dependencies
# This will use the requirements.txt and setup.py from the MeloTTS repo
RUN git clone https://github.com/myshell-ai/MeloTTS.git \
    && cd MeloTTS \
    && pip install --no-cache-dir -e . \
    && python -m unidic download \
    && python -m nltk.downloader averaged_perceptron_tagger punkt \
    && cd ..
# && rm -rf MeloTTS

# Download necessary NLTK data packages to the defined NLTK_DATA path
# Create the directory first to ensure it exists
RUN mkdir -p $NLTK_DATA
RUN echo "Downloading NLTK packages to $NLTK_DATA..."
RUN python -m nltk.downloader -d $NLTK_DATA averaged_perceptron_tagger punkt

# Create a symbolic link
RUN if [ -d "$NLTK_DATA/taggers/averaged_perceptron_tagger" ]; then \
    ln -s "$NLTK_DATA/taggers/averaged_perceptron_tagger" "$NLTK_DATA/taggers/averaged_perceptron_tagger_eng"; \
    echo "Created symlink: $NLTK_DATA/taggers/averaged_perceptron_tagger_eng -> $NLTK_DATA/taggers/averaged_perceptron_tagger"; \
    else \
    echo "Error: $NLTK_DATA/taggers/averaged_perceptron_tagger directory not found, cannot create symlink."; \
    exit 1; \
    fi

# Copy the model preloading script
COPY preload_models.py .

# Run the model preloading script
# Adjust the default list of languages as needed
ARG SUPPORTED_LANGUAGES_BUILD="EN" 
ENV SUPPORTED_LANGUAGES_BUILD=${SUPPORTED_LANGUAGES_BUILD}
ENV PRELOAD_DEVICE="cpu"
RUN python preload_models.py

# Copy the main application code (main.py)
COPY main.py .

# Set the entrypoint for Functions Framework
# The FUNCTION_TARGET environment variable will be set by Cloud Run to melo_tts_gcs_trigger
# Default port for Cloud Run is 8080
CMD exec functions-framework --target=melo_tts_gcs_trigger --port=8080