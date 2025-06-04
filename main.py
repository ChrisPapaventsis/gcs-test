import functions_framework
import os
from google.cloud import storage
from cloudevents.http import CloudEvent # For type hinting

# --- GCS Client Initialization ---
try:
    storage_client = storage.Client()
except Exception as e:
    print(f"Failed to initialize Google Cloud Storage client: {e}")
    storage_client = None # Function will fail if GCS is needed

# --- Configuration from Environment Variables ---
# This should be set in your Cloud Run service configuration
OUTPUT_GCS_BUCKET_NAME = os.environ.get('article-sound-files')

@functions_framework.cloud_event
def copy_txt_file_gcs(cloud_event: CloudEvent):
    """
    Cloud Event Function triggered by a GCS file upload.
    If the uploaded file is a .txt file, it copies it to another GCS bucket.
    """
    if not storage_client:
        print("Error: GCS client not initialized. Cannot proceed.")
        raise RuntimeError("GCS client failed to initialize.")

    if not OUTPUT_GCS_BUCKET_NAME:
        print("Error: OUTPUT_GCS_BUCKET_NAME environment variable is not set. Cannot determine output location.")
        raise ValueError("Missing OUTPUT_GCS_BUCKET_NAME configuration.")

    # --- 1. Extract file information from the CloudEvent ---
    event_data = cloud_event.data
    input_bucket_name = event_data.get("bucket")
    input_blob_name = event_data.get("name")

    if not input_bucket_name or not input_blob_name:
        print(f"Error: Malformed CloudEvent data. Missing 'bucket' or 'name'. Data: {event_data}")
        # Ack the event to prevent retries for a malformed event
        return ('Malformed event data', 200)

    print(f"Received event for file: gs://{input_bucket_name}/{input_blob_name}")

    # --- 2. Filter for specific file types (e.g., .txt) ---
    if not input_blob_name.lower().endswith(".txt"):
        print(f"File {input_blob_name} is not a .txt file. Skipping processing.")
        return ('Not a TXT file, skipping.', 200) # Ack the event

    try:
        # --- 3. Get source and destination bucket objects ---
        source_bucket = storage_client.bucket(input_bucket_name)
        destination_bucket = storage_client.bucket(OUTPUT_GCS_BUCKET_NAME)
        
        source_blob = source_bucket.blob(input_blob_name)

        if not source_blob.exists():
            print(f"Error: Source file gs://{input_bucket_name}/{input_blob_name} not found.")
            # Ack the event, as retrying won't help if the file doesn't exist
            return (f'Source file not found.', 200)

        # --- 4. Define destination blob name (can be same as source) ---
        # You could add logic here to change the name or path in the destination bucket if needed.
        destination_blob_name = input_blob_name 

        # --- 5. Copy the blob ---
        blob_copy = source_bucket.copy_blob(
            source_blob, destination_bucket, destination_blob_name
        )
        print(f"Successfully copied gs://{input_bucket_name}/{input_blob_name} to gs://{destination_bucket.name}/{blob_copy.name}")
        
        return ('File copied successfully.', 200)

    except storage.exceptions.NotFound:
        print(f"Error: Bucket not found during copy operation. Input: {input_bucket_name}, Output: {OUTPUT_GCS_BUCKET_NAME}")
        # This could be a configuration error, might warrant a non-200 response if retries are desired for temporary issues.
        # For permanent "Not Found" on a bucket, retries won't help.
        raise # Fail the function
    except storage.exceptions.Forbidden as e:
        print(f"Error: Permission denied during GCS operation: {e}. Ensure the service account has necessary roles (e.g., 'Storage Object Viewer' on source, 'Storage Object Creator' on destination).")
        raise # Fail the function
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}\n{traceback.format_exc()}")
        # This will cause the function invocation to be marked as failed,
        # and it might be retried depending on Cloud Run/Eventarc settings.
        raise