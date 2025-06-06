# preload_models.py
import os
from melo.api import TTS

# --- Add this import ---
from transformers import AutoModelForMaskedLM, AutoTokenizer

def preload_tts_models():
    # This part remains the same, preloading the main TTS synthesizer models
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
            # Optional: Uncomment the next line to make the build fail if a model is critical
            # raise
    print(f"--- [END] Preloading Main TTS Models ---")


def preload_hf_bert_models():
    # This new function preloads the supplementary BERT models used for text processing
    # The 'bert-base-uncased' model is used for English text feature extraction.
    # The 'tohoku-nlp/bert-base-japanese-v3' was from a previous error log for Japanese.
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
            # Optional: Uncomment the next line to make the build fail if a model is critical
            # raise
    print(f"--- [END] Preloading Hugging Face BERT models ---")


if __name__ == "__main__":
    # First, preload the main synthesizer models
    preload_tts_models()
    # Second, preload the supplementary BERT models
    preload_hf_bert_models()