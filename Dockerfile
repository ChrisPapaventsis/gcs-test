# Use Python 3.9 runtime as requested
FROM python:3.9-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Accept and set Hugging Face token
ARG HF_TOKEN_ARG
ENV HF_TOKEN=${HF_TOKEN_ARG}

# Define and create the NLTK data path
ENV NLTK_DATA /app/nltk_data
RUN mkdir -p $NLTK_DATA

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    libsndfile1 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies from requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install huggingface_hub

# --- NLTK Version and Data Fixes ---

# 1. Explicitly install a recent, specific NLTK version for consistency
RUN echo "--- [FIX] Installing specific NLTK version ---"
RUN pip install --upgrade nltk==3.8.1

# 2. Clone and install MeloTTS
RUN git clone https://github.com/myshell-ai/MeloTTS.git \
    && cd MeloTTS \
    && pip install --no-cache-dir . \
    && python -m unidic download \
    && cd .. \
    && rm -rf MeloTTS

# 3. Download the NLTK data using the now-installed NLTK
RUN echo "--- [FIX] Downloading NLTK data ---"
RUN python -m nltk.downloader -d $NLTK_DATA averaged_perceptron_tagger punkt

# 4. Debug: List the contents of the unzipped directory to verify
RUN echo "--- [DEBUG] Listing contents of unzipped tagger directory ---"
RUN ls -lR $NLTK_DATA/taggers/averaged_perceptron_tagger || echo "WARNING: Tagger directory not found."

# 5. Create symlinks for the directory AND then for the files if they exist
RUN echo "--- [FIX] Creating NLTK directory and file symlinks ---" && \
    # Create directory symlink (averaged_perceptron_tagger_eng -> averaged_perceptron_tagger)
    if [ -d "$NLTK_DATA/taggers/averaged_perceptron_tagger" ] && [ ! -e "$NLTK_DATA/taggers/averaged_perceptron_tagger_eng" ]; then \
    ln -s "$NLTK_DATA/taggers/averaged_perceptron_tagger" "$NLTK_DATA/taggers/averaged_perceptron_tagger_eng"; \
    echo "Created directory symlink for averaged_perceptron_tagger_eng."; \
    fi && \
    # Now, inside the symlinked directory, create file symlinks if the base JSON files exist
    if [ -d "$NLTK_DATA/taggers/averaged_perceptron_tagger_eng" ]; then \
    cd "$NLTK_DATA/taggers/averaged_perceptron_tagger_eng" && \
    if [ -f "averaged_perceptron_tagger.weights.json" ]; then \
    ln -s "averaged_perceptron_tagger.weights.json" "averaged_perceptron_tagger_eng.weights.json"; \
    ln -s "averaged_perceptron_tagger.tagdict.json" "averaged_perceptron_tagger_eng.tagdict.json"; \
    ln -s "averaged_perceptron_tagger.classes.json" "averaged_perceptron_tagger_eng.classes.json"; \
    echo "Created file symlinks for JSON files."; \
    else \
    echo "WARNING: Base JSON files (e.g., averaged_perceptron_tagger.weights.json) not found. File symlinks not created."; \
    fi; \
    fi

# --- End of NLTK fixes ---

# ... (rest of your Dockerfile: preload_models.py, COPY main.py, CMD) ...
COPY preload_models.py .
ARG SUPPORTED_LANGUAGES_BUILD="EN"
ENV SUPPORTED_LANGUAGES_BUILD=${SUPPORTED_LANGUAGES_BUILD}
ENV PRELOAD_DEVICE="cpu"
RUN python preload_models.py
COPY main.py .
CMD exec functions-framework --target=melo_tts_gcs_trigger --port=8080