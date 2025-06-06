# Use Python 3.9 as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Set standard environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Accept and set Hugging Face token (good practice for preloading models)
ARG HF_TOKEN_ARG
ENV HF_TOKEN=${HF_TOKEN_ARG}

# Define the NLTK data path and ensure NLTK uses it
ENV NLTK_DATA /app/nltk_data

# Install necessary system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies from your requirements.txt
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Clone MeloTTS repository, install it, and clean up the source
RUN git clone https://github.com/myshell-ai/MeloTTS.git \
    && cd MeloTTS \
    && pip install --no-cache-dir . \
    && python -m unidic download \
    && cd .. \
    && rm -rf MeloTTS

# --- NLTK Data Download ---
# Create the target directory for NLTK data
RUN mkdir -p $NLTK_DATA
# Download the specific, correct packages for the English tagger and tokenizer
RUN python -c "import nltk; nltk.download(['averaged_perceptron_tagger_eng', 'punkt'], download_dir='$NLTK_DATA')"

# Copy the model preloading script
COPY preload_models.py .
ARG SUPPORTED_LANGUAGES_BUILD="EN"
ENV SUPPORTED_LANGUAGES_BUILD=${SUPPORTED_LANGUAGES_BUILD}
ENV PRELOAD_DEVICE="cpu"
RUN python preload_models.py

# Copy your main application code
COPY main.py .

# Set the final entrypoint for Functions Framework
CMD exec functions-framework --target=melo_tts_gcs_trigger --port=8080