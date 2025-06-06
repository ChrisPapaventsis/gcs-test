# preload_models.py
import os
from melo.api import TTS

# Add this import for downloading Hugging Face transformers
from transformers import AutoModelForMaskedLM, AutoTokenizer

def preload_tts_models():
    """
    This function preloads the main MeloTTS synthesizer models.
    """
    languages_to_preload = os.environ.get('SUPPORTED_LANGUAGES_BUILD', 'EN').upper().split(',')
    device = os.environ.get('PRELOAD_DEVICE', 'cpu') 

    print(f"--- [START] Preloading Main TTS Models for languages: {languages_to_preload} ---")
    for lang_code in languages_to_preload:
        lang_code = lang_code.strip()
        if not lang_code:
            continue
        try:
            print(f"Preloading TTS model for language: {lang_code}...")
            TTS(language=lang_code, device=device)
            print(f"Successfully preloaded TTS model for language: {lang_code}")
        except Exception as e:
            print(f"ERROR: Could not preload TTS model for language {lang_code}: {e}")
            # To ensure a stable build, you might want to fail if a critical model can't be downloaded
            # raise e
    print(f"--- [END] Preloading Main TTS Models ---")


def preload_hf_bert_models():
    """
    This new function preloads the supplementary BERT models used for text processing.
    """
    # Add all BERT models MeloTTS might use here.
    # 'bert-base-uncased' is for English.
    # 'tohoku-nlp/bert-base-japanese-v3' was from a previous NLTK-related error for Japanese.
    models_to_preload = [
        "bert-base-uncased",
        "tohoku-nlp/bert-base-japanese-v3" 
    ]
    
    print(f"--- [START] Preloading Hugging Face BERT models: {models_to_preload} ---")
    for model_id in models_to_preload:
        try:
            print(f"Preloading {model_id}...")
            # Downloading both the model and the tokenizer ensures all necessary files are cached
            AutoModelForMaskedLM.from_pretrained(model_id)
            AutoTokenizer.from_pretrained(model_id)
            print(f"Successfully preloaded {model_id}.")
        except Exception as e:
            print(f"ERROR: Could not preload Hugging Face model {model_id}. Error: {e}")
            # To ensure a stable build, you might want to fail if a model is critical
            # raise e
    print(f"--- [END] Preloading Hugging Face BERT models ---")


if __name__ == "__main__":
    # Execute both preloading functions
    preload_tts_models()
    preload_hf_bert_models()