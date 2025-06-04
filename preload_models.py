import os
# This import will work if MeloTTS is installed via 'pip install -e ./MeloTTS'
from melo.api import TTS 

def run_preloading():
    # Ensure 'JP' is included if japanese.py is trying to load models
    # Add all languages you intend to support or that cause import-time downloads
    languages_to_preload = os.environ.get('SUPPORTED_LANGUAGES_BUILD', 'EN,ES,FR,JP,ZH,KR').upper().split(',')
    device = os.environ.get('PRELOAD_DEVICE', 'cpu') 

    print(f"Starting TTS model preloading for languages: {languages_to_preload} on device: {device}")

    for lang_code in languages_to_preload:
        lang_code = lang_code.strip()
        if not lang_code:
            continue
        try:
            print(f"Preloading model for language: {lang_code}...")
            # Initializing TTS class for each language should trigger the download
            # of all its components, including tokenizers from Hugging Face.
            TTS(language=lang_code, device=device) #
            print(f"Successfully preloaded/cached model for language: {lang_code}")
        except Exception as e:
            print(f"Error preloading model for language {lang_code}: {e}")
            # Depending on your needs, you might want to make the build fail here
            # raise

    print("TTS model preloading process finished.")

if __name__ == "__main__":
    run_preloading()