import functions_framework
import os
import warnings
import tempfile
import re # For parsing GCS URI
from cloudevents.http import CloudEvent # For type hinting

# Import GCS client library
from google.cloud import storage

# --- [NNPACK FIX] Add these lines to disable NNPACK ---
import torch
if hasattr(torch, 'backends') and hasattr(torch.backends, 'nnpack') and hasattr(torch.backends.nnpack, 'enabled'):
    print("Attempting to disable NNPACK...")
    try:
        torch.backends.nnpack.enabled = False
        print("NNPACK disabled.")
    except Exception as e:
        print(f"Could not disable NNPACK: {e}")
else:
    print("NNPACK backend control not found in this PyTorch version.")
# --- [END OF NNPACK FIX] ---

# Import MeloTTS API
# This assumes MeloTTS is installed via 'pip install -e .' in the Dockerfile
from melo.api import TTS #

# --- GCS Client Initialization ---
try:
    storage_client = storage.Client()
except Exception as e:
    print(f"Failed to initialize Google Cloud Storage client: {e}")
    storage_client = None

# --- Configuration ---
# Output GCS bucket from environment variable
OUTPUT_GCS_BUCKET_NAME = os.environ.get('OUTPUT_GCS_BUCKET_NAME')

# Hardcoded TTS parameters for now (as requested)
TARGET_LANGUAGE = 'EN'
TARGET_SPEED = 1.0
DEVICE = 'cpu' # 'cpu' is typical for Cloud Run without GPU

# --- Global Cache for TTS Model ---
# To avoid re-initializing the model on every invocation for a warm instance
tts_model_cache = {}

def get_tts_model(language, device):
    if language in tts_model_cache:
        print(f"Using cached TTS model for language: {language}")
        return tts_model_cache[language]
    
    print(f"Initializing TTS model for language: {language}, device: {device}. This might take a moment on first cold start...")
    # Models should be downloaded by MeloTTS to a cache path during this initialization
    # if not preloaded in the Docker image (which we are deferring).
    model = TTS(language=language, device=device) #
    tts_model_cache[language] = model
    print(f"TTS model for {language} initialized.")
    return model

# --- GCS Helper Functions (from your previous version) ---
def read_text_from_gcs(bucket_name: str, blob_name: str) -> str:
    if not storage_client:
        raise RuntimeError("Google Cloud Storage client is not available.")
    
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            raise FileNotFoundError(f"File not found in GCS: {gcs_uri}")
            
        file_content_bytes = blob.download_as_bytes()
        return file_content_bytes.decode('utf-8').strip()
    except storage.exceptions.NotFound:
        raise FileNotFoundError(f"File not found in GCS: {gcs_uri}")
    except storage.exceptions.Forbidden as e:
        raise PermissionError(f"Permission denied accessing GCS file: {gcs_uri}. Ensure the service account has 'Storage Object Viewer'. Original error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to read file from GCS '{gcs_uri}': {type(e).__name__} - {e}")

def upload_to_gcs(local_file_path: str, bucket_name: str, destination_blob_name: str):
    if not storage_client:
        raise RuntimeError("Google Cloud Storage client is not available for upload.")
    if not bucket_name:
        # Ensure the specific environment variable key is checked for better error message
        if not os.environ.get('article-sound-files'):
             raise ValueError("OUTPUT_GCS_BUCKET_NAME environment variable (expected as 'article-sound-files') is not set.")
        else: # Should not happen if os.environ.get worked before, but as a safeguard
            raise ValueError("Output GCS bucket name is not configured.")

    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        print(f"Successfully uploaded '{local_file_path}' to 'gs://{bucket_name}/{destination_blob_name}'")
    except storage.exceptions.Forbidden as e:
        raise PermissionError(f"Permission denied uploading to GCS bucket '{bucket_name}'. Ensure the service account has 'Storage Object Creator' role. Original error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to upload file to GCS 'gs://{bucket_name}/{destination_blob_name}': {type(e).__name__} - {e}")

@functions_framework.cloud_event
def melo_tts_gcs_trigger(cloud_event: CloudEvent):
    """
    Cloud Event Function for Text-to-Speech triggered by a GCS file upload.
    Processes the uploaded text file, converts it to WAV using MeloTTS,
    and saves the audio to another GCS bucket.
    """
    if not storage_client:
        print("Error: GCS client not initialized. Cannot proceed.")
        raise RuntimeError("GCS client failed to initialize.")

    if not OUTPUT_GCS_BUCKET_NAME:
        print("Error: OUTPUT_GCS_BUCKET_NAME environment variable (expected as 'article-sound-files') is not set. Cannot determine output location.")
        raise ValueError("Missing OUTPUT_GCS_BUCKET_NAME configuration (expected as 'article-sound-files').")

    event_data = cloud_event.data
    input_bucket_name = event_data.get("bucket")
    input_blob_name = event_data.get("name")

    if not input_bucket_name or not input_blob_name:
        print(f"Error: Malformed CloudEvent data. Missing 'bucket' or 'name'. Data: {event_data}")
        return ('Malformed event data', 200)

    print(f"Received event for file: gs://{input_bucket_name}/{input_blob_name}")

    if not input_blob_name.lower().endswith(".txt"):
        print(f"File {input_blob_name} is not a .txt file. Skipping processing.")
        return ('Not a TXT file, skipping.', 200)

    text_content = None
    try:
        text_content = read_text_from_gcs(input_bucket_name, input_blob_name)
    except Exception as e:
        print(f"Error reading source GCS file gs://{input_bucket_name}/{input_blob_name}: {e}")
        return (f"Error processing input file: {e}", 500 if isinstance(e, RuntimeError) else 200)

    if not text_content:
        print(f"Error: The file gs://{input_bucket_name}/{input_blob_name} is empty or could not be read.")
        return (f'Empty or unreadable input file.', 200)

    temp_output_path = None
    try:
        # --- Initialize TTS model (uses cache) ---
        model = get_tts_model(TARGET_LANGUAGE, DEVICE)
        
        # --- Determine Speaker ID for default English ---
        speaker_ids_map = model.hps.data.spk2id #
        selected_speaker_id_for_tts = None
        
        # Try to find a standard default English speaker name
        default_english_speaker_name = 'EN-Default' # A common convention
        if speaker_ids_map and default_english_speaker_name in speaker_ids_map:
            selected_speaker_id_for_tts = speaker_ids_map[default_english_speaker_name]
            print(f"Using default speaker: {default_english_speaker_name} (ID: {selected_speaker_id_for_tts})")
        elif speaker_ids_map and len(speaker_ids_map) > 0 : # If 'EN-Default' not found, use the first available
            first_available_speaker_name = list(speaker_ids_map.keys())[0]
            selected_speaker_id_for_tts = speaker_ids_map[first_available_speaker_name]
            print(f"Warning: Speaker '{default_english_speaker_name}' not found. Using first available speaker: {first_available_speaker_name} (ID: {selected_speaker_id_for_tts})")
        else: # Fallback if no speakers are defined in the map or map is empty
            selected_speaker_id_for_tts = 0 # Defaulting to speaker ID 0 as a last resort
            print(f"Warning: No speaker map found or it's empty for language {TARGET_LANGUAGE}. Defaulting to speaker ID 0.")

        print(f"Text for TTS (first 100 chars): \"{text_content[:100]}...\"")
        print(f"TTS settings: Lang={TARGET_LANGUAGE}, SpeakerID(model internal)={selected_speaker_id_for_tts}, Speed={TARGET_SPEED}")

        # --- Perform TTS ---
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            temp_output_path = tmpfile.name
        
        model.tts_to_file(
            text=text_content, 
            speaker_id=selected_speaker_id_for_tts,
            output_path=temp_output_path, 
            speed=TARGET_SPEED,
            quiet=False # Set to False initially for more verbose TTS logs if needed for debugging
        ) #
        print(f"TTS audio generated successfully at: {temp_output_path}")

        # --- Upload the audio file to the output GCS bucket ---
        base_name = os.path.splitext(input_blob_name)[0]
        output_blob_name = f"{base_name}.wav"

        upload_to_gcs(temp_output_path, OUTPUT_GCS_BUCKET_NAME, output_blob_name)
        
        print(f"Processing complete for gs://{input_bucket_name}/{input_blob_name}. Output: gs://{OUTPUT_GCS_BUCKET_NAME}/{output_blob_name}")
        return ('Processing successful', 200)

    except Exception as e:
        import traceback
        print(f"An unexpected error occurred during TTS processing: {e}\n{traceback.format_exc()}")
        raise # Fail the function for potential retry
    finally:
        # --- Clean up the temporary file ---
        if temp_output_path and os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
                print(f"Temporary file {temp_output_path} removed.")
            except Exception as e_remove:
                print(f"Error removing temporary file {temp_output_path}: {e_remove}")